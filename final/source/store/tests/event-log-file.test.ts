import { describe, expect, it } from "vitest";
import {
  chmodSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
  symlinkSync,
  utimesSync,
  writeFileSync,
} from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileSink, StoreEventLog } from "../src/event-log.js";

const posix = process.platform !== "win32";
const DAY_MS = 24 * 3600 * 1000;

/** A private folder (0700), like the host's systemd log folder. */
function withFolder(run: (directory: string) => Promise<void>) {
  return async () => {
    const parent = mkdtempSync(join(tmpdir(), "copilot-store-log-"));
    const directory = join(parent, "store");
    mkdirSync(directory, { mode: 0o700 });
    try {
      await run(directory);
    } finally {
      rmSync(parent, { recursive: true, force: true });
    }
  };
}

function records(file: string) {
  return readFileSync(file, "utf8")
    .trim()
    .split("\n")
    .map((line) => JSON.parse(line));
}

describe("Storefront host log file", () => {
  it(
    "appends one JSON line per record to events.jsonl",
    withFolder(async (directory) => {
      const sink = fileSink(directory);
      const events = new StoreEventLog(sink, "r1");
      events.cartChange("add", "ok", 200);
      events.cartChange("clear", "ok", 303);
      await sink.flush();

      expect(
        records(join(directory, "events.jsonl")).map((r) => r.change),
      ).toEqual(["add", "clear"]);
      expect(sink.failures).toBe(0);
    }),
  );

  it(
    "writes off the request path, so a record call returns before the disk",
    withFolder(async (directory) => {
      const sink = fileSink(directory);

      new StoreEventLog(sink).cartChange("add", "ok", 200);

      expect(existsSync(join(directory, "events.jsonl"))).toBe(false);
      await sink.flush();
      expect(existsSync(join(directory, "events.jsonl"))).toBe(true);
    }),
  );

  it(
    "drops and counts records once its queue is full",
    withFolder(async (directory) => {
      const sink = fileSink(directory, { capacity: 2 });
      const events = new StoreEventLog(sink);

      for (let i = 0; i < 5; i++) events.cartChange("add", "ok", 200);
      await sink.flush();

      expect(sink.failures).toBe(3);
      expect(records(join(directory, "events.jsonl"))).toHaveLength(2);
    }),
  );

  it(
    "rotates into two numbered backups and drops older records",
    withFolder(async (directory) => {
      const sink = fileSink(directory, { fileBytes: 400 });
      const events = new StoreEventLog(sink, "r1");
      for (let i = 0; i < 40; i++) events.cartChange("add", "ok", 200);
      await sink.flush();

      for (const name of ["events.jsonl", "events.jsonl.1", "events.jsonl.2"])
        expect(statSync(join(directory, name)).size).toBeLessThanOrEqual(400);
      expect(existsSync(join(directory, "events.jsonl.3"))).toBe(false);
    }),
  );

  it(
    "prunes files older than seven days when it writes",
    withFolder(async (directory) => {
      const old = join(directory, "events.jsonl.2");
      writeFileSync(old, "{}\n", { mode: 0o600 });
      const eightDaysAgo = (Date.now() - 8 * DAY_MS) / 1000;
      utimesSync(old, eightDaysAgo, eightDaysAgo);
      const sink = fileSink(directory);

      new StoreEventLog(sink).cartChange("add", "ok", 200);
      await sink.flush();

      expect(existsSync(old)).toBe(false);
      expect(existsSync(join(directory, "events.jsonl"))).toBe(true);
    }),
  );

  it.skipIf(!posix)(
    "creates the file readable by its owner only",
    withFolder(async (directory) => {
      const sink = fileSink(directory);
      new StoreEventLog(sink).cartChange("add", "ok", 200);
      await sink.flush();

      expect(statSync(join(directory, "events.jsonl")).mode & 0o777).toBe(
        0o600,
      );
    }),
  );

  it.skipIf(!posix)(
    "refuses to follow a link planted at the log path",
    withFolder(async (directory) => {
      const target = join(directory, "elsewhere");
      writeFileSync(target, "", { mode: 0o600 });
      symlinkSync(target, join(directory, "events.jsonl"));
      const sink = fileSink(directory);

      new StoreEventLog(sink).cartChange("add", "ok", 200);
      await sink.flush();

      expect(sink.failures).toBe(1);
      expect(readFileSync(target, "utf8")).toBe("");
    }),
  );

  it.skipIf(!posix)(
    "refuses to rotate a link planted as a backup",
    withFolder(async (directory) => {
      const target = join(directory, "elsewhere");
      writeFileSync(target, "keep\n", { mode: 0o600 });
      writeFileSync(join(directory, "events.jsonl"), "x".repeat(390) + "\n", {
        mode: 0o600,
      });
      symlinkSync(target, join(directory, "events.jsonl.1"));
      const sink = fileSink(directory, { fileBytes: 400 });

      new StoreEventLog(sink).cartChange("add", "ok", 200);
      await sink.flush();

      expect(sink.failures).toBe(1);
      expect(readFileSync(target, "utf8")).toBe("keep\n");
      expect(statSync(join(directory, "events.jsonl")).size).toBe(391);
    }),
  );

  it.skipIf(!posix)(
    "refuses a log file others can read",
    withFolder(async (directory) => {
      writeFileSync(join(directory, "events.jsonl"), "", { mode: 0o644 });
      chmodSync(join(directory, "events.jsonl"), 0o644);
      const sink = fileSink(directory);

      new StoreEventLog(sink).cartChange("add", "ok", 200);
      await sink.flush();

      expect(sink.failures).toBe(1);
      expect(readFileSync(join(directory, "events.jsonl"), "utf8")).toBe("");
    }),
  );

  it.skipIf(!posix)(
    "refuses a log folder others can open",
    withFolder(async (directory) => {
      chmodSync(directory, 0o755);
      const sink = fileSink(directory);

      new StoreEventLog(sink).cartChange("add", "ok", 200);
      await sink.flush();

      expect(sink.failures).toBe(1);
      expect(existsSync(join(directory, "events.jsonl"))).toBe(false);
    }),
  );
});
