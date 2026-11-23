import { executeAction } from "./actions.js";
import { installShopperLink } from "./shopper-link.js";
import { matchesShopperContext, shopperContext } from "./shopper-context.js";
import { recordEvaluationTiming } from "./evaluation-metrics.js";
import { validatePublicOrigin } from "./public-origins.js";
import { SnapshotBuilder, type SnapshotBuilderOptions } from "./snapshot.js";
import { parseAction, type Action, type ActionResult } from "./types.js";
import {
  documentIsBusy,
  observeDocument,
  settleDocument,
} from "./observation.js";

const PENDING_NAVIGATION_KEY = "shopping-copilot.pending-navigation";
const ACTION_LEDGER_KEY = "shopping-copilot.action-ledger";

export interface StorageLike {
  getItem(key: string): string | null;
  removeItem(key: string): void;
  setItem(key: string, value: string): void;
}

export interface BridgeRuntimeOptions extends SnapshotBuilderOptions {
  document: Document;
  panelOrigin: string;
  storage: StorageLike;
  currentUrl: () => string;
  navigate: (url: URL) => void;
  post: (message: unknown) => void;
  settle?: () => Promise<void>;
}

type BridgeMessage =
  | { type: "action"; action: unknown }
  | { type: "cancel_task"; task_id: string }
  | { type: "request_snapshot" };

interface ActionLedger {
  activeTaskId: string | null;
  completedActionIds: string[];
  highestSequenceByTask: Record<string, number>;
  retiredTaskIds: string[];
}

function emptyLedger(): ActionLedger {
  return {
    activeTaskId: null,
    completedActionIds: [],
    highestSequenceByTask: {},
    retiredTaskIds: [],
  };
}

function isBridgeMessage(value: unknown): value is BridgeMessage {
  if (typeof value !== "object" || value === null || !("type" in value))
    return false;
  if (value.type === "request_snapshot") return true;
  if (value.type === "cancel_task")
    return "task_id" in value && typeof value.task_id === "string";
  return value.type === "action" && "action" in value;
}

function readLedger(storage: StorageLike): ActionLedger {
  const stored = storage.getItem(ACTION_LEDGER_KEY);
  if (stored === null) return emptyLedger();
  try {
    const parsed = JSON.parse(stored) as Partial<ActionLedger>;
    const highestSequenceByTask = parsed.highestSequenceByTask ?? {};
    const knownTaskIds = Object.keys(highestSequenceByTask);
    return {
      activeTaskId: parsed.activeTaskId ?? knownTaskIds.at(-1) ?? null,
      completedActionIds: parsed.completedActionIds ?? [],
      highestSequenceByTask,
      retiredTaskIds: parsed.retiredTaskIds ?? knownTaskIds.slice(0, -1),
    };
  } catch {
    return emptyLedger();
  }
}

function acceptAction(storage: StorageLike, action: Action): boolean {
  const ledger = readLedger(storage);
  if (ledger.retiredTaskIds.includes(action.task_id)) return false;
  if (ledger.activeTaskId === null) {
    if (action.sequence_number !== 1) return false;
    ledger.activeTaskId = action.task_id;
  } else if (ledger.activeTaskId !== action.task_id) {
    if (action.sequence_number !== 1) return false;
    ledger.retiredTaskIds = [...ledger.retiredTaskIds, ledger.activeTaskId];
    ledger.activeTaskId = action.task_id;
  }
  const highestSequence = ledger.highestSequenceByTask[action.task_id] ?? 0;
  if (
    ledger.completedActionIds.includes(action.action_id) ||
    action.sequence_number <= highestSequence
  ) {
    return false;
  }
  ledger.highestSequenceByTask[action.task_id] = action.sequence_number;
  ledger.completedActionIds = [
    ...ledger.completedActionIds.slice(-99),
    action.action_id,
  ];
  storage.setItem(ACTION_LEDGER_KEY, JSON.stringify(ledger));
  return true;
}

function retireTask(storage: StorageLike, taskId: string): void {
  const ledger = readLedger(storage);
  if (!ledger.retiredTaskIds.includes(taskId))
    ledger.retiredTaskIds.push(taskId);
  if (ledger.activeTaskId === taskId) ledger.activeTaskId = null;
  storage.setItem(ACTION_LEDGER_KEY, JSON.stringify(ledger));
}

export class BridgeRuntime {
  readonly #options: BridgeRuntimeOptions;
  readonly #builder: SnapshotBuilder;
  readonly #storefrontOrigin: string;
  #stopObserving?: () => void;
  #observationPending = false;
  #lastSnapshot = "";
  #routeRevision = 0;

  constructor(options: BridgeRuntimeOptions) {
    this.#options = options;
    this.#builder = new SnapshotBuilder(options.document, options);
    this.#storefrontOrigin = new URL(options.currentUrl()).origin;
  }

  start(): void {
    if (this.#stopObserving) return;
    this.#stopObserving = observeDocument(
      this.#options.document,
      (route, committed) => {
        if (route) this.#routeRevision++;
        // Preserve committed manual choices for a message sent immediately afterward.
        // Loading/optimistic state still waits, and the settled pass catches later renders.
        if (committed && !documentIsBusy(this.#options.document))
          this.#options.post({
            type: "snapshot",
            snapshot: this.#builder.build(),
          });
        void this.#observeSettled();
      },
    );
    if (documentIsBusy(this.#options.document)) {
      void (
        this.#options.settle ?? (() => settleDocument(this.#options.document))
      )().then(() => {
        if (this.#stopObserving) this.#publishInitial();
      });
    } else this.#publishInitial();
  }

  #publishInitial(): void {
    const pending = this.#options.storage.getItem(PENDING_NAVIGATION_KEY);
    if (pending === null) {
      if (!documentIsBusy(this.#options.document))
        this.#options.post({
          type: "snapshot",
          snapshot: this.#builder.build(),
        });
      return;
    }

    this.#options.storage.removeItem(PENDING_NAVIGATION_KEY);
    const action = parseAction(JSON.parse(pending));
    const result: ActionResult = {
      v: 1,
      task_id: action.task_id,
      action_id: action.action_id,
      sequence_number: action.sequence_number,
      status: documentIsBusy(this.#options.document) ? "blocked" : "navigated",
      snapshot: this.#builder.build(),
    };
    this.#options.post({ type: "action_result", result });
  }

  async #observeSettled(): Promise<void> {
    if (this.#observationPending) return;
    this.#observationPending = true;
    try {
      await (
        this.#options.settle ?? (() => settleDocument(this.#options.document))
      )();
      if (!this.#stopObserving || documentIsBusy(this.#options.document))
        return;
      const snapshot = this.#builder.build();
      const serializationStarted = performance.now();
      const serialized = JSON.stringify(snapshot);
      recordEvaluationTiming("snapshot_serialization", serializationStarted);
      if (serialized !== this.#lastSnapshot) {
        this.#lastSnapshot = serialized;
        this.#options.post({ type: "snapshot", snapshot });
      }
    } finally {
      this.#observationPending = false;
    }
  }

  stop(): void {
    this.#stopObserving?.();
    this.#stopObserving = undefined;
  }

  async receive(origin: string, payload: unknown): Promise<void> {
    if (origin !== this.#options.panelOrigin || !isBridgeMessage(payload))
      return;
    if (payload.type === "request_snapshot") {
      if (documentIsBusy(this.#options.document)) await this.#observeSettled();
      else
        this.#options.post({
          type: "snapshot",
          snapshot: this.#builder.build(),
        });
      return;
    }
    if (payload.type === "cancel_task") {
      retireTask(this.#options.storage, payload.task_id);
      return;
    }
    const action = parseAction(payload.action);
    if (!acceptAction(this.#options.storage, action)) {
      const staleResult: ActionResult = {
        v: 1,
        task_id: action.task_id,
        action_id: action.action_id,
        sequence_number: action.sequence_number,
        status: "stale",
        snapshot: this.#builder.build(),
      };
      this.#options.post({ type: "action_result", result: staleResult });
      return;
    }
    let navigationStarted = false;
    const beforeUrl = this.#options.currentUrl();
    const beforeRevision = this.#routeRevision;
    const executionStarted = performance.now();
    let settleMs = 0;
    const result = await executeAction(action, {
      builder: this.#builder,
      currentUrl: this.#options.currentUrl,
      storefrontOrigin: this.#storefrontOrigin,
      navigate: async (url) => {
        navigationStarted = true;
        this.#options.storage.setItem(
          PENDING_NAVIGATION_KEY,
          JSON.stringify(action),
        );
        await this.#options.navigate(url);
      },
      armGuardedNavigation: (confirmed) => {
        navigationStarted = true;
        this.#options.storage.setItem(
          PENDING_NAVIGATION_KEY,
          JSON.stringify(confirmed),
        );
      },
      settle: async () => {
        const started = performance.now();
        try {
          await (
            this.#options.settle ??
            (() => settleDocument(this.#options.document))
          )();
        } finally {
          settleMs += performance.now() - started;
          recordEvaluationTiming("settle", started);
        }
      },
    });
    recordEvaluationTiming(
      "action_execute_excluding_settle",
      executionStarted + settleMs,
    );
    if (action.type === "navigate" && result.status === "blocked") {
      this.#options.storage.removeItem(PENDING_NAVIGATION_KEY);
      navigationStarted = false;
    }
    // A SPA retains this runtime. A document navigation delivers its result from start().
    if (
      navigationStarted &&
      (this.#options.currentUrl() !== beforeUrl ||
        this.#routeRevision !== beforeRevision)
    ) {
      const pending = this.#options.storage.getItem(PENDING_NAVIGATION_KEY);
      if (pending === JSON.stringify(action)) {
        this.#options.storage.removeItem(PENDING_NAVIGATION_KEY);
        this.#options.post({ type: "action_result", result });
      }
    } else if (!navigationStarted)
      this.#options.post({ type: "action_result", result });
  }

  snapshot() {
    return this.#builder.build();
  }
}

declare global {
  interface Window {
    __copilot?: {
      snapshot: () => ReturnType<BridgeRuntime["snapshot"]>;
      run: (action: Action) => Promise<void>;
    };
  }
}

if (typeof window !== "undefined" && window.parent !== window) {
  const publicOrigin = document.querySelector<HTMLMetaElement>(
    'meta[name="copilot-store-origin"]',
  )?.content;
  const panelValue = document.querySelector<HTMLMetaElement>(
    'meta[name="copilot-panel-origin"]',
  )?.content;
  if (!publicOrigin || !panelValue || publicOrigin !== window.location.origin)
    throw new Error(
      "Storefront public origin configuration is missing or mismatched",
    );
  const panelOrigin = validatePublicOrigin(
    panelValue,
    publicOrigin.startsWith("https:"),
  );
  if (panelOrigin === publicOrigin)
    throw new Error("Panel and Storefront origins must differ");
  document.addEventListener("shopper:reset", () => {
    window.parent.postMessage({ type: "shopper_reset" }, panelOrigin);
  });
  let lastInteraction = -Infinity;
  for (const kind of ["pointerdown", "keydown"]) {
    document.addEventListener(kind, (event) => {
      if (!event.isTrusted || document.visibilityState !== "visible") return;
      const now = performance.now();
      if (now - lastInteraction < 30_000) return;
      lastInteraction = now;
      window.parent.postMessage(
        { type: "shopper_activity", shopper_context: shopperContext(document) },
        panelOrigin,
      );
    });
  }
  installShopperLink(window, panelOrigin);
  const runtime = new BridgeRuntime({
    document,
    panelOrigin,
    storage: window.sessionStorage,
    currentUrl: () => window.location.href,
    navigate: (url) => {
      const navigation = (
        window as Window & {
          navigation?: {
            navigate: (url: string) => { finished: Promise<unknown> };
          };
        }
      ).navigation;
      if (navigation)
        return navigation.navigate(url.href).finished.then(() => undefined);
      window.location.assign(url);
    },
    post: (message) =>
      window.parent.postMessage(
        { ...(message as object), shopper_context: shopperContext(document) },
        panelOrigin,
      ),
  });
  window.addEventListener("message", (event) => {
    if (event.source !== window.parent) return;
    if (
      event.data?.type === "action" &&
      !matchesShopperContext(document, event.data.shopper_context)
    )
      return;
    void runtime.receive(event.origin, event.data);
  });
  window.__copilot = {
    snapshot: () => runtime.snapshot(),
    run: (action) => runtime.receive(panelOrigin, { type: "action", action }),
  };
  runtime.start();
}
