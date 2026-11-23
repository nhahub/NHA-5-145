import type { Action, ActionResult, Snapshot } from "../../bridge/src/types.js";

import {
  PanelController,
  type AgentEvent,
  type AgentTransport,
  type StorefrontChannel,
  type StorefrontMessage,
  type SessionPersistence,
  type SessionView,
} from "./panel.js";
import "./styles.css";
import { linkShopper } from "./shopper-link.js";
import { subscribeAgentStream } from "./event-stream.js";
import { requireAdmission } from "./admission.js";
import { PageMemory } from "./page-memory.js";

declare const __COPILOT_PUBLIC_ORIGINS__: {
  panel: string;
  store: string;
  agent: string;
};
const AGENT_ORIGIN = __COPILOT_PUBLIC_ORIGINS__.agent;
const STOREFRONT_ORIGIN = __COPILOT_PUBLIC_ORIGINS__.store;
if (window.location.origin !== __COPILOT_PUBLIC_ORIGINS__.panel)
  throw new Error("Panel was served on an unexpected origin");

let browserCsrf = "";
let shopperContext = "";
let interactionReady = false;
let lastInteraction = -Infinity;
function reportInteraction() {
  if (
    !shopperContext ||
    !interactionReady ||
    authorityLost ||
    document.visibilityState !== "visible"
  )
    return;
  const now = performance.now();
  if (now - lastInteraction < 30_000) return;
  lastInteraction = now;
  void agentFetch(`${AGENT_ORIGIN}/shopper/activity`, { method: "POST" }).catch(
    () => {},
  );
}
async function agentFetch(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: { ...options.headers, "x-csrf-token": browserCsrf },
  });
  if (response.status === 401 || response.status === 403)
    void handleAuthorityLoss();
  if (response.status === 429 || response.status === 503) {
    if (root) {
      let notice = root.querySelector<HTMLElement>("#admission-busy");
      if (!notice) {
        notice = document.createElement("p");
        notice.id = "admission-busy";
        notice.setAttribute("role", "alert");
        root.append(notice);
      }
      notice.textContent =
        "الخدمة مشغولة أو وصلت لحد الاستخدام. حاول لاحقًا. / Busy or usage limit reached. Try later.";
    }
  }
  return response;
}

class HttpAgentTransport implements AgentTransport {
  readonly #tabId: string;

  constructor(tabId: string) {
    this.#tabId = tabId;
  }

  async createSession(tabId = this.#tabId): Promise<string> {
    const response = await agentFetch(`${AGENT_ORIGIN}/sessions`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-tab-id": this.#tabId,
      },
      body: JSON.stringify({ tab_id: tabId }),
    });
    if (!response.ok) throw new Error("Session creation failed");
    const payload = (await response.json()) as { session_id: string };
    return payload.session_id;
  }

  subscribe(
    sessionId: string,
    handler: (event: AgentEvent) => void,
    after = 0,
    onCursor?: (cursor: number) => void,
  ): () => void {
    return subscribeAgentStream(
      `${AGENT_ORIGIN}/sessions/${sessionId}/events?after=${after}&tab_id=${encodeURIComponent(this.#tabId)}`,
      handler,
      after,
      onCursor,
      undefined,
      () => {
        void handleAuthorityLoss();
      },
    );
  }

  async restoreSession(sessionId: string, tabId: string): Promise<SessionView> {
    const response = await agentFetch(
      `${AGENT_ORIGIN}/sessions/${sessionId}/state?tab_id=${encodeURIComponent(tabId)}`,
    );
    if (!response.ok)
      throw new Error(`Session restore failed with ${response.status}`);
    return (await response.json()) as SessionView;
  }

  async reconcile(
    sessionId: string,
    tabId: string,
    snapshot: Snapshot,
  ): Promise<SessionView> {
    return this.#postForView(
      `/sessions/${sessionId}/reconcile`,
      { snapshot },
      tabId,
    );
  }

  async takeover(sessionId: string, tabId: string): Promise<SessionView> {
    return this.#postForView(
      `/sessions/${sessionId}/takeover`,
      { tab_id: tabId },
      tabId,
    );
  }

  async submitMessage(
    sessionId: string,
    text: string,
    snapshot: Snapshot,
  ): Promise<void> {
    await this.#post(`/sessions/${sessionId}/messages`, { text, snapshot });
  }

  async speechAvailable(): Promise<boolean> {
    const response = await agentFetch(`${AGENT_ORIGIN}/speech/availability`);
    if (!response.ok) return false;
    const result = (await response.json()) as { available: boolean };
    return result.available === true;
  }

  async transcribeSpeech(audio: Blob, language: "ar" | "en"): Promise<string> {
    const response = await agentFetch(
      `${AGENT_ORIGIN}/speech/transcribe?language=${language}`,
      {
        method: "POST",
        headers: { "content-type": "audio/webm" },
        body: audio,
      },
    );
    if (!response.ok)
      throw new Error(`Speech transcription failed with ${response.status}`);
    const result = (await response.json()) as { text: string };
    return result.text;
  }

  async submitActionResult(
    sessionId: string,
    result: ActionResult,
  ): Promise<void> {
    await this.#post(`/sessions/${sessionId}/action-results`, result);
  }

  async submitAnswer(
    sessionId: string,
    taskId: string,
    questionId: string,
    text: string,
    snapshot: Snapshot,
  ): Promise<"resumed" | "awaiting_login"> {
    const response = await agentFetch(
      `${AGENT_ORIGIN}/sessions/${sessionId}/tasks/${taskId}/answers`,
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-tab-id": this.#tabId,
        },
        body: JSON.stringify({ question_id: questionId, text, snapshot }),
      },
    );
    if (!response.ok)
      throw new Error(`Agent request failed with ${response.status}`);
    const result = (await response.json()) as {
      status: "resumed" | "awaiting_login";
    };
    return result.status;
  }

  async stop(sessionId: string): Promise<void> {
    await this.#post(`/sessions/${sessionId}/stop`, {});
  }

  async retry(
    sessionId: string,
    taskId: string,
    snapshot: Snapshot,
  ): Promise<void> {
    await this.#post(`/sessions/${sessionId}/tasks/${taskId}/retry`, {
      snapshot,
    });
  }

  async #post(path: string, body: object): Promise<void> {
    const response = await agentFetch(`${AGENT_ORIGIN}${path}`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-tab-id": this.#tabId,
      },
      body: JSON.stringify(body),
    });
    if (!response.ok)
      throw new Error(`Agent request failed with ${response.status}`);
  }

  async #postForView(
    path: string,
    body: object,
    tabId: string,
  ): Promise<SessionView> {
    const response = await agentFetch(`${AGENT_ORIGIN}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-tab-id": tabId },
      body: JSON.stringify(body),
    });
    if (!response.ok)
      throw new Error(`Agent request failed with ${response.status}`);
    return (await response.json()) as SessionView;
  }
}

class WindowStorefrontChannel implements StorefrontChannel {
  readonly #frame: HTMLIFrameElement;

  constructor(frame: HTMLIFrameElement) {
    this.#frame = frame;
    this.#frame.addEventListener("load", () => this.requestSnapshot());
  }

  sendAction(action: Action): void {
    this.#frame.contentWindow?.postMessage(
      { type: "action", action, shopper_context: shopperContext },
      STOREFRONT_ORIGIN,
    );
  }

  requestSnapshot(): void {
    this.#frame.contentWindow?.postMessage(
      { type: "request_snapshot" },
      STOREFRONT_ORIGIN,
    );
  }

  cancelTask(taskId: string): void {
    this.#frame.contentWindow?.postMessage(
      { type: "cancel_task", task_id: taskId },
      STOREFRONT_ORIGIN,
    );
  }
}

const root = document.querySelector<HTMLElement>("#app");
const frame = document.querySelector<HTMLIFrameElement>("#storefront-frame");
if (root === null || frame === null)
  throw new Error("Panel shell is incomplete");
const spaVariant = new URL(window.location.href).searchParams.get("spa");
const pageMemory = new PageMemory(
  window.sessionStorage,
  STOREFRONT_ORIGIN,
  spaVariant,
);

const SESSION_KEY = "shopping-copilot.session-id";
const CURSOR_KEY = "shopping-copilot.event-cursor";
const TAB_KEY = "shopping-copilot.tab-id";
let tabId = window.sessionStorage.getItem(TAB_KEY);
if (tabId === null) {
  tabId = crypto.randomUUID();
  window.sessionStorage.setItem(TAB_KEY, tabId);
}
const persistence: SessionPersistence = {
  loadSessionId: () => window.localStorage.getItem(SESSION_KEY) ?? undefined,
  saveSessionId: (sessionId) =>
    window.localStorage.setItem(SESSION_KEY, sessionId),
  clearSession: () => {
    window.localStorage.removeItem(SESSION_KEY);
    window.localStorage.removeItem(CURSOR_KEY);
  },
  loadEventCursor: () => Number(window.localStorage.getItem(CURSOR_KEY) ?? "0"),
  saveEventCursor: (cursor) =>
    window.localStorage.setItem(CURSOR_KEY, String(cursor)),
};

const controller = new PanelController(
  root,
  new HttpAgentTransport(tabId),
  new WindowStorefrontChannel(frame),
  { persistence, tabId },
);
window.addEventListener("message", (event) => {
  if (
    event.origin !== STOREFRONT_ORIGIN ||
    event.source !== frame.contentWindow
  )
    return;
  const message = event.data as StorefrontMessage;
  if (
    event.data?.type === "shopper_activity" &&
    shopperContext &&
    event.data.shopper_context === shopperContext
  ) {
    reportInteraction();
    return;
  }
  if (event.data?.type === "shopper_reset") {
    controller.invalidateShopper();
    return;
  }
  if (message.type === "snapshot" || message.type === "action_result") {
    if (!shopperContext) return;
    if (event.data.shopper_context !== shopperContext) {
      controller.invalidateShopper();
      return;
    }
    pageMemory.remember(
      (message.type === "snapshot" ? message.snapshot : message.result.snapshot)
        ?.url,
    );
    controller.receiveStorefront(message);
  }
});
let authorityLost = false;
async function handleAuthorityLoss() {
  if (authorityLost) return;
  authorityLost = true;
  interactionReady = false;
  controller.invalidateShopper();
  try {
    await requireAdmission(root!, AGENT_ORIGIN, browserCsrf, true);
  } catch {
    // Identity/storage failure keeps the existing fail-closed reload state.
  } finally {
    const notice = document.createElement("div");
    notice.id = "admission-busy";
    notice.setAttribute("role", "alert");
    const text = document.createElement("p");
    text.textContent =
      "الاتصال توقف أو الخدمة مشغولة. انتظر قليلًا ثم أعد التحميل وراجع السلة. / Connection interrupted or busy. Wait, then reload and check your cart.";
    const retry = document.createElement("button");
    retry.id = "access-reload";
    retry.type = "button";
    retry.textContent = "إعادة تحميل / Reload";
    retry.addEventListener("click", () => window.location.reload());
    notice.append(text, retry);
    root!.querySelector("#admission-busy")?.remove();
    root!.append(notice);
  }
}

async function startLinked() {
  try {
    const begin = async () => {
      // Serialize the first Storefront navigation too: cookies are shared across tabs.
      frame!.src = pageMemory.startUrl();
      const linked = await linkShopper(frame!, AGENT_ORIGIN, STOREFRONT_ORIGIN);
      browserCsrf = linked.csrf;
      shopperContext = linked.context;
    };
    if (navigator.locks)
      await navigator.locks.request("copilot-shopper-link", begin);
    else throw new Error("A secure browser with Web Locks is required");
    // Code entry must not hold a cross-tab lock while waiting for the Shopper.
    await requireAdmission(root!, AGENT_ORIGIN, browserCsrf);
    await navigator.locks.request("copilot-shopper-link", () =>
      controller.start(),
    );
    interactionReady = true;
  } catch {
    const status = document.createElement("p");
    status.setAttribute("role", "alert");
    status.textContent =
      "تعذر ربط جلسة التسوق. أعد تحميل الصفحة للمحاولة. / Shopping session unavailable. Reload to retry.";
    root!.prepend(status);
  }
}
void startLinked();
for (const kind of ["pointerdown", "keydown"]) {
  document.addEventListener(kind, (event) => {
    if (event.isTrusted) reportInteraction();
  });
}
