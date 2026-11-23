/**
 * The Storefront's own event log: cart changes by type and errors by type.
 *
 * Records carry only fixed values (change type, outcome, status, error type, route
 * template), never a product, size, colour, quantity, payment field or message.
 * Anything outside the allow-list is dropped, so a future caller cannot leak free
 * text by accident. Locally records print to the terminal; on the host they go to a
 * private rotating file in the Storefront's own log folder. They never leave the
 * host: the Storefront has no AWS credentials.
 */
import { constants, type Stats } from "node:fs";
import { lstat, open, rename, unlink } from "node:fs/promises";
import { join } from "node:path";

export const CART_CHANGES = [
  "add",
  "quantity",
  "remove",
  "undo",
  "clear",
  "checkout",
] as const;
export const OUTCOMES = [
  "ok",
  "rejected",
  "unknown_product",
  "unavailable",
  "unconfirmed",
  "invalid_payment",
] as const;
export type CartChange = (typeof CART_CHANGES)[number];
export type Outcome = (typeof OUTCOMES)[number];

export type StoreRecord = {
  time: string;
  release: string;
  event: "cart_change" | "error";
  change?: CartChange;
  outcome?: Outcome;
  status?: number;
  error_type?: string;
  route?: string;
};

export interface EventSink {
  write(line: string): void;
}

const TOKEN = /^[A-Za-z0-9_.]{1,100}$/;
const RELEASE = /^[A-Za-z0-9_.-]{1,64}$/;
const ROUTE = /^[A-Za-z0-9_./:-]{1,200}$/;

export class StoreEventLog {
  failures = 0;
  readonly #release: string;

  constructor(
    private readonly sink: EventSink,
    release = "local",
  ) {
    this.#release = RELEASE.test(release) ? release : "local";
  }

  cartChange(change: CartChange, outcome: Outcome, status: number): void {
    if (
      !CART_CHANGES.includes(change) ||
      !OUTCOMES.includes(outcome) ||
      !Number.isInteger(status) ||
      status < 100 ||
      status > 599
    )
      return;
    this.#write({ event: "cart_change", change, outcome, status });
  }

  error(error: unknown, route?: unknown): void {
    const name =
      error instanceof Error && TOKEN.test(error.name) ? error.name : "Error";
    this.#write({
      event: "error",
      error_type: name,
      ...(typeof route === "string" && ROUTE.test(route) ? { route } : {}),
    });
  }

  #write(fields: Omit<StoreRecord, "time" | "release">): void {
    const record = {
      time: new Date().toISOString(),
      release: this.#release,
      ...fields,
    };
    try {
      this.sink.write(JSON.stringify(record));
    } catch {
      this.failures += 1; // a log failure must never break a shopper's request
    }
  }
}

/** Keeps records in memory, for tests. */
export function memorySink() {
  const lines: string[] = [];
  return {
    lines,
    get records(): StoreRecord[] {
      return lines.map((line) => JSON.parse(line) as StoreRecord);
    },
    write(line: string) {
      lines.push(line);
    },
  };
}

/** Prints records to the terminal, for local runs. */
export function streamSink(stream: NodeJS.WritableStream = process.stdout) {
  return {
    write(line: string) {
      stream.write(line + "\n");
    },
  };
}

export const HOST_DIRECTORY = "/var/log/shopping-copilot/store";
const NAMES = ["events.jsonl", "events.jsonl.1", "events.jsonl.2"];
const FILE_BYTES = Math.floor((5 * 1024 * 1024) / 3);
const RETENTION_MS = 7 * 24 * 3600 * 1000;
const POSIX = process.platform !== "win32";

/** True when a file or folder belongs to this process and others cannot use it. */
function privateTo(info: Stats, mask: number): boolean {
  return (
    !POSIX || (info.uid === process.getuid?.() && (info.mode & mask) === 0)
  );
}

function privateFile(info: Stats): boolean {
  return (
    info.isFile() &&
    !info.isSymbolicLink() &&
    info.nlink === 1 &&
    privateTo(info, 0o077)
  );
}

async function inspect(path: string): Promise<Stats | null> {
  try {
    return await lstat(path);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
}

export type FileSink = EventSink & {
  /** Records refused, dropped because the queue was full, or not written. */
  readonly failures: number;
  /** Resolves once every queued record has been written or counted as failed. */
  flush(): Promise<void>;
};

/**
 * Appends records to a private file in the background, rotating into two numbered
 * backups and pruning files older than seven days.
 *
 * Records are queued (bounded) and written by one async loop, so a slow or stalled
 * disk never holds up a request. Before each write the folder and every managed file
 * are checked: no links, a single-link regular file, owned by the Storefront, not
 * usable by others, the same rules as the host's other private log files.
 */
export function fileSink(
  directory: string,
  options: { fileBytes?: number; capacity?: number } = {},
): FileSink {
  const limit = options.fileBytes ?? FILE_BYTES;
  const capacity = options.capacity ?? 10_000;
  const path = (index: number) => join(directory, NAMES[index]);
  const flags =
    constants.O_WRONLY |
    constants.O_APPEND |
    constants.O_CREAT |
    (constants.O_NOFOLLOW ?? 0);
  const queue: Buffer[] = [];
  let draining: Promise<void> | null = null;
  let failures = 0;

  async function append(encoded: Buffer) {
    const folder = await lstat(directory);
    if (!folder.isDirectory() || !privateTo(folder, 0o077))
      throw new Error("Private log folder required");
    const files = await Promise.all(
      NAMES.map((_, index) => inspect(path(index))),
    );
    if (files.some((info) => info !== null && !privateFile(info)))
      throw new Error("Private log file required");
    const now = Date.now();
    for (const [index, info] of files.entries())
      if (info !== null && now - info.mtimeMs > RETENTION_MS) {
        await unlink(path(index));
        files[index] = null;
      }
    const current = files[0];
    if (current !== null && current.size + encoded.length > limit)
      for (let index = NAMES.length - 1; index > 0; index--)
        if (files[index - 1] !== null)
          await rename(path(index - 1), path(index));
    const handle = await open(path(0), flags, 0o600);
    try {
      if (!privateFile(await handle.stat()))
        throw new Error("Private log file required");
      const { bytesWritten } = await handle.write(encoded);
      if (bytesWritten !== encoded.length)
        throw new Error("Incomplete log write");
    } finally {
      await handle.close();
    }
  }

  async function drain() {
    try {
      while (queue.length > 0) {
        try {
          await append(queue[0]); // stays queued while written, so it counts
        } catch {
          failures += 1;
        } finally {
          queue.shift();
        }
      }
    } finally {
      draining = null;
    }
  }

  return {
    get failures() {
      return failures;
    },
    write(line: string) {
      const encoded = Buffer.from(line + "\n");
      if (encoded.length > limit || queue.length >= capacity) {
        failures += 1;
        return;
      }
      queue.push(encoded);
      draining ??= drain();
    },
    async flush() {
      while (draining !== null) await draining;
    },
  };
}
