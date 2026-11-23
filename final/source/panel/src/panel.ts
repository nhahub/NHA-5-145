import {
  parseAction,
  type Action,
  type ActionResult,
  type Snapshot,
} from "../../bridge/src/types.js";

export const AGENT_EVENT_TYPES = [
  "task_started",
  "narration",
  "action",
  "suggestions",
  "done",
  "cancelled",
  "error",
  "plan_created",
  "plan_step_started",
  "plan_step_finished",
  "plan_paused",
  "plan_resumed",
  "plan_finished",
] as const;

export type PlanStepOutcome = "done" | "failed" | "skipped";
export type PlanOutcome = "done" | "failed" | "cancelled";
export type PlanPauseReason = "question" | "confirmation";

export type AgentEvent =
  | { type: "task_started"; data: { task_id: string } }
  | { type: "narration"; data: { text: string } }
  | { type: "action"; data: { action: Action } }
  | { type: "suggestions"; data: SuggestionResult }
  | { type: "done"; data: { summary: string; language: "ar" | "en" } }
  | { type: "cancelled"; data: Record<string, never> }
  | { type: "error"; data: { message: string } }
  | {
      type: "plan_created";
      data: {
        plan_id: string;
        language: "ar" | "en";
        steps: Array<{ position: number; text: string }>;
        skipped: string[];
      };
    }
  | {
      type: "plan_step_started";
      data: { plan_id: string; position: number; task_id: string };
    }
  | {
      type: "plan_step_finished";
      data: { plan_id: string; position: number; outcome: PlanStepOutcome };
    }
  | {
      type: "plan_paused";
      data: { plan_id: string; position: number; reason: PlanPauseReason };
    }
  | { type: "plan_resumed"; data: { plan_id: string; position: number } }
  | {
      type: "plan_finished";
      data: { plan_id: string; outcome: PlanOutcome; report: string };
    };

export interface Suggestion {
  id: string;
  label: "exact_match" | "alternative" | "styling_suggestion";
  name: string;
  price: string;
  currency: "EGP";
  reason: string;
  unmet: string[];
}

export interface SuggestionResult {
  exact_count: number | null;
  suggestions: Suggestion[];
}

function parseSuggestionResult(
  data: Record<string, unknown>,
): SuggestionResult {
  if (
    data.exact_count !== null &&
    (!Number.isSafeInteger(data.exact_count) ||
      (data.exact_count as number) < 0)
  )
    throw new TypeError("Invalid exact match count");
  if (!Array.isArray(data.suggestions) || data.suggestions.length > 3)
    throw new TypeError("Invalid suggestion list");
  const suggestions = data.suggestions.map((value: unknown) => {
    const item = eventData(value);
    const label = eventString(item, "label");
    if (!["exact_match", "alternative", "styling_suggestion"].includes(label))
      throw new TypeError("Invalid suggestion label");
    if (eventString(item, "currency") !== "EGP")
      throw new TypeError("Invalid suggestion currency");
    if (
      !Array.isArray(item.unmet) ||
      !item.unmet.every((part) => typeof part === "string")
    )
      throw new TypeError("Invalid unmet requirements");
    return {
      id: eventString(item, "id"),
      label: label as Suggestion["label"],
      name: eventString(item, "name"),
      price: eventString(item, "price"),
      currency: "EGP" as const,
      reason: eventString(item, "reason"),
      unmet: item.unmet as string[],
    };
  });
  return { exact_count: data.exact_count as number | null, suggestions };
}

function eventData(payload: unknown): Record<string, unknown> {
  if (typeof payload !== "object" || payload === null || Array.isArray(payload))
    throw new TypeError("Agent event data must be an object");
  return payload as Record<string, unknown>;
}

function eventString(data: Record<string, unknown>, key: string): string {
  const value = data[key];
  if (typeof value !== "string")
    throw new TypeError(`Agent event data.${key} must be a string`);
  return value;
}

function eventPosition(data: Record<string, unknown>, max = 3): number {
  const value = data.position;
  if (
    !Number.isSafeInteger(value) ||
    (value as number) < 1 ||
    (value as number) > max
  )
    throw new TypeError(
      `Agent event data.position must be an integer 1-${max}`,
    );
  return value as number;
}

function eventOneOf<T extends string>(
  data: Record<string, unknown>,
  key: string,
  allowed: readonly T[],
): T {
  const value = eventString(data, key);
  if (!(allowed as readonly string[]).includes(value))
    throw new TypeError(`Agent event data.${key} is not supported`);
  return value as T;
}

function eventPlanId(data: Record<string, unknown>): string {
  const planId = eventString(data, "plan_id");
  if (planId === "") throw new TypeError("Agent event data.plan_id is empty");
  return planId;
}

function parsePlanSteps(
  value: unknown,
): Array<{ position: number; text: string }> {
  if (!Array.isArray(value) || value.length < 2 || value.length > 3)
    throw new TypeError("Agent event data.steps must list 2 or 3 steps");
  return value.map((entry: unknown, index: number) => {
    const step = eventData(entry);
    const position = eventPosition(step, value.length);
    if (position !== index + 1)
      throw new TypeError("Agent event data.steps must be in order");
    return { position, text: eventString(step, "text") };
  });
}

function parseSkippedWords(value: unknown): string[] {
  if (
    !Array.isArray(value) ||
    value.length > 6 ||
    !value.every((word: unknown) => typeof word === "string")
  )
    throw new TypeError("Agent event data.skipped must list up to 6 strings");
  return value as string[];
}

export function parseAgentEvent(type: string, payload: unknown): AgentEvent {
  if (!(AGENT_EVENT_TYPES as readonly string[]).includes(type))
    throw new TypeError(
      `Agent event type ${JSON.stringify(type)} is not supported`,
    );
  const data = eventData(payload);
  switch (type) {
    case "task_started":
      return { type, data: { task_id: eventString(data, "task_id") } };
    case "narration":
      return { type, data: { text: eventString(data, "text") } };
    case "action":
      return { type, data: { action: parseAction(data.action) } };
    case "suggestions":
      return { type, data: parseSuggestionResult(data) };
    case "done": {
      const language = eventString(data, "language");
      if (language !== "ar" && language !== "en")
        throw new TypeError("Agent event data.language must be ar or en");
      return {
        type,
        data: { summary: eventString(data, "summary"), language },
      };
    }
    case "cancelled":
      return { type, data: {} };
    case "error":
      return { type, data: { message: eventString(data, "message") } };
    case "plan_created":
      return {
        type,
        data: {
          plan_id: eventPlanId(data),
          language: eventOneOf(data, "language", ["ar", "en"] as const),
          steps: parsePlanSteps(data.steps),
          skipped: parseSkippedWords(data.skipped),
        },
      };
    case "plan_step_started":
      return {
        type,
        data: {
          plan_id: eventPlanId(data),
          position: eventPosition(data),
          task_id: eventString(data, "task_id"),
        },
      };
    case "plan_step_finished":
      return {
        type,
        data: {
          plan_id: eventPlanId(data),
          position: eventPosition(data),
          outcome: eventOneOf(data, "outcome", [
            "done",
            "failed",
            "skipped",
          ] as const),
        },
      };
    case "plan_paused":
      return {
        type,
        data: {
          plan_id: eventPlanId(data),
          position: eventPosition(data),
          reason: eventOneOf(data, "reason", [
            "question",
            "confirmation",
          ] as const),
        },
      };
    case "plan_resumed":
      return {
        type,
        data: { plan_id: eventPlanId(data), position: eventPosition(data) },
      };
    case "plan_finished":
      return {
        type,
        data: {
          plan_id: eventPlanId(data),
          outcome: eventOneOf(data, "outcome", [
            "done",
            "failed",
            "cancelled",
          ] as const),
          report: eventString(data, "report"),
        },
      };
    default:
      throw new TypeError(
        `Agent event type ${JSON.stringify(type)} is not supported`,
      );
  }
}

type PlanStepMark = "pending" | "running" | "paused" | PlanStepOutcome;

interface PlanView {
  planId: string;
  language: "ar" | "en";
  steps: Array<{ text: string; mark: PlanStepMark }>;
  skipped: string[];
  active: boolean;
}

export interface PlanState {
  plan_id: string;
  language: "ar" | "en";
  active: boolean;
  steps: Array<{
    position: number;
    text: string;
    status: Exclude<PlanStepMark, "paused">;
  }>;
  skipped: string[];
  paused?: PlanPauseReason | null;
}

const PLAN_LABELS = {
  ar: {
    heading: "الخطوات",
    skippedNote: "مش هعمل دول دلوقتي (الحد ٣ طلبات): ",
    separator: "، ",
    marks: {
      pending: ["○", "في الانتظار"],
      running: ["◐", "جاري التنفيذ"],
      paused: ["◷", "مستني ردك"],
      done: ["✓", "تمّت"],
      failed: ["✕", "لم تنجح"],
      skipped: ["–", "تم تخطّيها"],
    },
  },
  en: {
    heading: "Steps",
    skippedNote: "Not doing these now (limit is 3 requests): ",
    separator: ", ",
    marks: {
      pending: ["○", "Waiting"],
      running: ["◐", "In progress"],
      paused: ["◷", "Waiting for you"],
      done: ["✓", "Done"],
      failed: ["✕", "Failed"],
      skipped: ["–", "Skipped"],
    },
  },
} as const;

export type StorefrontMessage =
  | { type: "snapshot"; snapshot: Snapshot }
  | { type: "action_result"; result: ActionResult };

export interface SessionView {
  session_id: string;
  lease: "owned" | "takeover_required";
  event_cursor: number;
  conversation: Array<{ role: "shopper" | "copilot"; text: string }>;
  requires_reconciliation: boolean;
  plan?: PlanState | null;
  task: {
    task_id: string;
    status: string;
    pending_question: unknown | null;
    suggestions?: SuggestionResult | null;
    pause_message?: string | null;
  } | null;
}

export interface SessionPersistence {
  loadSessionId(): string | undefined;
  saveSessionId(sessionId: string): void;
  clearSession(): void;
  loadEventCursor(): number;
  saveEventCursor(cursor: number): void;
}

export interface AgentTransport {
  createSession(tabId?: string): Promise<string>;
  restoreSession(sessionId: string, tabId: string): Promise<SessionView>;
  reconcile(
    sessionId: string,
    tabId: string,
    snapshot: Snapshot,
  ): Promise<SessionView>;
  takeover(sessionId: string, tabId: string): Promise<SessionView>;
  subscribe(
    sessionId: string,
    handler: (event: AgentEvent) => void,
    after?: number,
    onCursor?: (cursor: number) => void,
  ): () => void;
  submitMessage(
    sessionId: string,
    text: string,
    snapshot: Snapshot,
  ): Promise<void>;
  submitActionResult(sessionId: string, result: ActionResult): Promise<void>;
  submitAnswer(
    sessionId: string,
    taskId: string,
    questionId: string,
    text: string,
    snapshot: Snapshot,
  ): Promise<"resumed" | "awaiting_login">;
  stop(sessionId: string): Promise<void>;
  retry(sessionId: string, taskId: string, snapshot: Snapshot): Promise<void>;
  speechAvailable(): Promise<boolean>;
  transcribeSpeech(audio: Blob, language: "ar" | "en"): Promise<string>;
}

export interface StorefrontChannel {
  sendAction(action: Action): void;
  cancelTask(taskId: string): void;
  requestSnapshot(): void;
}

interface BrowserSpeechRecognition {
  lang: string;
  onresult:
    | ((event: {
        results: ArrayLike<ArrayLike<{ transcript: string }>>;
      }) => void)
    | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  abort(): void;
}

const SPEECH_ERROR_MESSAGES: Record<string, { ar: string; en: string }> = {
  network: {
    ar: "خدمة التعرف على الصوت غير متاحة الآن. جرّب Chrome أو اكتب طلبك.",
    en: "Speech recognition is unavailable. Try Chrome or type your request.",
  },
  "not-allowed": {
    ar: "المتصفح أو النظام منع استخدام الميكروفون. راجع الأذونات ثم حاول ثانية.",
    en: "Microphone access was blocked. Check browser and system permissions, then retry.",
  },
  "service-not-allowed": {
    ar: "المتصفح منع خدمة التعرف على الصوت. جرّب Chrome أو اكتب طلبك.",
    en: "The browser blocked speech recognition. Try Chrome or type your request.",
  },
  "audio-capture": {
    ar: "تعذر الوصول للميكروفون. تأكد من توصيله وإعدادات الصوت ثم حاول ثانية.",
    en: "The microphone could not be accessed. Check its connection and audio settings.",
  },
  "no-speech": {
    ar: "لم أسمع كلامًا. حاول ثانية وتكلم بعد بدء الاستماع.",
    en: "No speech was heard. Try again and speak after listening starts.",
  },
  "language-not-supported": {
    ar: "لغة الصوت المحددة غير مدعومة في هذا المتصفح. جرّب لغة أخرى.",
    en: "The selected speech language is unsupported in this browser. Try another language.",
  },
};

export class PanelController {
  readonly #root: HTMLElement;
  readonly #agent: AgentTransport;
  readonly #storefront: StorefrontChannel;
  readonly #persistence: SessionPersistence | undefined;
  readonly #tabId: string;
  #sessionId: string | undefined;
  #shopperInvalid = false;
  #snapshotAuthorityReady = false;
  #snapshot: Snapshot | undefined;
  #unsubscribe: (() => void) | undefined;
  #activeTaskId: string | undefined;
  #submitting = false;
  readonly #cancelledTaskIds = new Set<string>();
  readonly #questionActionIds = new Set<string>();
  #reconnecting = false;
  #recoveryInFlight = false;
  #recoverySnapshot: Snapshot | undefined;
  #waitingForLoginUrl: string | undefined;
  #recognition: BrowserSpeechRecognition | undefined;
  #recorder: MediaRecorder | undefined;
  #speechVersion = 0;
  #plan: PlanView | undefined;

  constructor(
    root: HTMLElement,
    agent: AgentTransport,
    storefront: StorefrontChannel,
    options?: { persistence?: SessionPersistence; tabId?: string },
  ) {
    this.#root = root;
    this.#agent = agent;
    this.#storefront = storefront;
    this.#persistence = options?.persistence;
    this.#tabId = options?.tabId ?? "tab-local";
    this.#render();
  }

  async start(): Promise<void> {
    this.#snapshotAuthorityReady = false;
    const savedSessionId = this.#persistence?.loadSessionId();
    if (savedSessionId !== undefined) {
      this.#sessionId = savedSessionId;
      this.#reconnecting = true;
      this.#setInputEnabled(false);
      this.#setStatus("Reconnecting…");
      let state: SessionView;
      try {
        state = await this.#agent.restoreSession(savedSessionId, this.#tabId);
      } catch (error) {
        if (
          !(error instanceof Error) ||
          !/^Session restore failed with (404|410)$/.test(error.message)
        )
          throw error;
        this.#persistence?.clearSession();
        this.#reconnecting = false;
        await this.#startFreshSession();
        this.#appendMessage(
          "copilot",
          "انتهت جلسة المساعد السابقة. بدأت جلسة جديدة.",
        );
        return;
      }
      if (state.lease === "takeover_required") {
        this.#renderTakeover();
        this.#setStatus("This task is active in another tab");
        return;
      }
      this.#snapshotAuthorityReady = true;
      this.#storefront.requestSnapshot();
      return;
    }
    await this.#startFreshSession();
  }

  async #startFreshSession(): Promise<void> {
    this.#sessionId = await this.#agent.createSession(this.#tabId);
    this.#persistence?.saveSessionId(this.#sessionId);
    this.#subscribe(this.#persistence?.loadEventCursor() ?? 0);
    this.#snapshotAuthorityReady = true;
    this.#storefront.requestSnapshot();
    this.#setStatus("بانتظار اتصال المتجر…");
  }

  dispose(): void {
    this.#unsubscribe?.();
  }

  invalidateShopper(): void {
    this.#shopperInvalid = true;
    this.dispose();
    if (this.#activeTaskId) this.#storefront.cancelTask(this.#activeTaskId);
    this.#sessionId = undefined;
    // Keep the opaque saved session reference for refresh reconciliation.
    // A changed identity gets 404 on restore; it cannot resume this task.
    this.#setInputEnabled(false);
    this.#root
      .querySelectorAll<HTMLButtonElement>("button")
      .forEach((button) => {
        button.disabled = true;
      });
    this.#setStatus("");
  }

  receiveStorefront(message: StorefrontMessage): void {
    if (this.#shopperInvalid) return;
    if (message.type === "snapshot") {
      this.#snapshot = message.snapshot;
      if (!this.#snapshotAuthorityReady) return;
      if (
        this.#waitingForLoginUrl !== undefined &&
        message.snapshot.url !== this.#waitingForLoginUrl
      ) {
        this.#waitingForLoginUrl = undefined;
        const continueButton = this.#root.querySelector<HTMLButtonElement>(
          '[data-question-option="Continue"]',
        );
        if (continueButton !== null) continueButton.disabled = false;
        this.#root.querySelector("#login-wait-hint")?.remove();
        this.#setStatus(
          "اتغيرت صفحة المتجر. اختر متابعة للتحقق من سجل الطلبات.",
        );
      }
      if (this.#reconnecting && this.#sessionId !== undefined) {
        this.#recoverySnapshot = message.snapshot;
        if (!this.#recoveryInFlight) void this.#completeRecovery();
        return;
      }
      if (
        this.#sessionId !== undefined &&
        this.#activeTaskId === undefined &&
        !this.#submitting
      ) {
        this.#setInputEnabled(true);
        this.#setStatus("جاهز لاستقبال طلبك");
      }
      return;
    }
    this.#snapshot = message.result.snapshot;
    const questionKey = `${message.result.task_id}:${message.result.action_id}`;
    if (this.#questionActionIds.delete(questionKey)) return;
    if (this.#sessionId !== undefined) {
      void this.#agent
        .submitActionResult(this.#sessionId, message.result)
        .catch(() => {
          if (this.#activeTaskId !== message.result.task_id) return;
          this.#cancelledTaskIds.add(message.result.task_id);
          this.#storefront.cancelTask(message.result.task_id);
          this.#setTaskState("paused");
          this.#setInputEnabled(false);
          this.#root
            .querySelector<HTMLElement>("#pending-question")
            ?.replaceChildren();
          this.#setStatus(
            "تعذر تأكيد نتيجة الإجراء. راجع السلة قبل أي تعديل آخر، ثم اضغط إيقاف. لن أكرر الإجراء تلقائيًا.",
          );
        });
    }
  }

  async #completeRecovery(): Promise<void> {
    if (this.#sessionId === undefined) return;
    this.#recoveryInFlight = true;
    try {
      let state: SessionView | undefined;
      while (this.#recoverySnapshot !== undefined) {
        const snapshot = this.#recoverySnapshot;
        this.#recoverySnapshot = undefined;
        state = await this.#agent.reconcile(
          this.#sessionId,
          this.#tabId,
          snapshot,
        );
      }
      if (state === undefined) return;
      this.#restoreView(state);
      this.#subscribe(state.event_cursor);
      this.#reconnecting = false;
    } catch {
      this.#setStatus(
        "تعذر استعادة المهمة. أعد تحميل الصفحة للمحاولة مرة أخرى.",
      );
    } finally {
      this.#recoveryInFlight = false;
    }
  }

  #subscribe(after: number): void {
    if (this.#sessionId === undefined) return;
    this.#unsubscribe?.();
    this.#unsubscribe = this.#agent.subscribe(
      this.#sessionId,
      (event) => this.#receiveAgent(event),
      after,
      (cursor) => this.#persistence?.saveEventCursor(cursor),
    );
  }

  #restoreView(state: SessionView): void {
    const conversation =
      this.#root.querySelector<HTMLOListElement>("#conversation");
    conversation?.replaceChildren();
    const welcome = this.#root.querySelector<HTMLElement>(
      "#conversation-welcome",
    );
    if (welcome) welcome.hidden = state.conversation.length > 0;
    this.#root
      .querySelector<HTMLElement>("#pending-question")
      ?.replaceChildren();
    for (const message of state.conversation)
      this.#appendMessage(message.role, message.text);
    this.#renderSuggestions(state.task?.suggestions ?? null);
    this.#restorePlan(state.plan ?? null);
    const taskIsActive =
      state.task !== null &&
      state.task.status !== "completed" &&
      state.task.status !== "cancelled";
    this.#activeTaskId = taskIsActive ? state.task?.task_id : undefined;
    if (state.task?.status === "paused") this.#renderRetry();
    if (
      taskIsActive &&
      state.task?.pending_question !== null &&
      state.task?.pending_question !== undefined
    ) {
      const question = parseAction(state.task.pending_question);
      if (question.type === "ask_shopper") {
        this.#registerQuestion(question);
        this.#renderQuestion(question);
      }
    }
    this.#setStatus(
      state.task?.status === "paused" && state.task.pause_message
        ? state.task.pause_message
        : taskIsActive
          ? "Reconnected"
          : "Ready",
    );
    this.#setTaskState(state.task?.status ?? "idle");
    this.#setInputEnabled(!taskIsActive);
  }

  #restorePlan(plan: PlanState | null): void {
    // The checklist is rebuilt from the Session's own state: steps that never ran are never
    // shown as done, and the message box stays disabled while the plan is still active.
    this.#plan =
      plan === null
        ? undefined
        : {
            planId: plan.plan_id,
            language: plan.language,
            steps: plan.steps.map((step) => ({
              text: step.text,
              mark:
                step.status === "running" && plan.paused
                  ? "paused"
                  : step.status,
            })),
            skipped: plan.skipped,
            active: plan.active,
          };
    this.#renderPlan();
  }

  #renderTakeover(): void {
    const container =
      this.#root.querySelector<HTMLElement>("#pending-question");
    if (container === null) return;
    const button = this.#root.ownerDocument.createElement("button");
    button.id = "takeover-session";
    button.type = "button";
    button.textContent = "Take over this task";
    button.addEventListener("click", () => {
      if (this.#sessionId === undefined) return;
      void this.#agent.takeover(this.#sessionId, this.#tabId).then(() => {
        this.#snapshotAuthorityReady = true;
        container.replaceChildren();
        this.#setStatus("Reconnecting…");
        this.#storefront.requestSnapshot();
      });
    });
    container.replaceChildren(button);
    button.focus();
  }

  #receiveAgent(event: AgentEvent): void {
    if (this.#shopperInvalid) return;
    if (event.type === "task_started") {
      this.#setTaskState("active");
      this.#renderSuggestions(null);
      this.#submitting = false;
      this.#activeTaskId = event.data.task_id;
      this.#setInputEnabled(false);
    } else if (event.type === "narration") {
      this.#setStatus(event.data.text);
      this.#appendMessage("copilot", event.data.text);
    } else if (event.type === "suggestions") {
      this.#renderSuggestions(event.data);
    } else if (event.type === "action") {
      if (this.#cancelledTaskIds.has(event.data.action.task_id)) return;
      if (event.data.action.type === "ask_shopper") {
        this.#registerQuestion(event.data.action);
        this.#renderQuestion(event.data.action);
      } else {
        this.#storefront.sendAction(event.data.action);
      }
    } else if (event.type === "done") {
      this.#setTaskState("completed");
      this.#root
        .querySelector<HTMLElement>("#pending-question")
        ?.replaceChildren();
      this.#setStatus(
        event.data.language === "ar" ? "اكتملت المهمة" : "Task complete",
      );
      this.#appendMessage("copilot", event.data.summary);
      this.#activeTaskId = undefined;
      this.#setInputEnabled(true);
    } else if (event.type === "cancelled") {
      this.#setTaskState("cancelled");
      this.#root
        .querySelector<HTMLElement>("#pending-question")
        ?.replaceChildren();
      this.#setStatus("تم إيقاف المهمة");
      this.#activeTaskId = undefined;
      this.#setInputEnabled(true);
    } else if (event.type === "error") {
      this.#setTaskState("paused");
      this.#setStatus(event.data.message);
      this.#renderRetry();
      this.#setInputEnabled(false);
    } else if (event.type === "plan_created") {
      this.#plan = {
        planId: event.data.plan_id,
        language: event.data.language,
        steps: event.data.steps.map((step) => ({
          text: step.text,
          mark: "pending",
        })),
        skipped: event.data.skipped,
        active: true,
      };
      this.#renderPlan();
      this.#setInputEnabled(false);
    } else if (this.#plan?.planId !== event.data.plan_id) {
      // Plan events for an unknown plan are ignored.
      return;
    } else if (event.type === "plan_step_started") {
      const step = this.#plan.steps[event.data.position - 1];
      if (step === undefined) return;
      step.mark = "running";
      this.#renderPlan();
    } else if (event.type === "plan_paused") {
      const step = this.#plan.steps[event.data.position - 1];
      if (step === undefined) return;
      step.mark = "paused";
      this.#renderPlan();
    } else if (event.type === "plan_resumed") {
      const step = this.#plan.steps[event.data.position - 1];
      if (step === undefined) return;
      step.mark = "running";
      this.#renderPlan();
    } else if (event.type === "plan_step_finished") {
      const step = this.#plan.steps[event.data.position - 1];
      if (step === undefined) return;
      step.mark = event.data.outcome;
      this.#renderPlan();
    } else if (event.type === "plan_finished") {
      this.#plan.active = false;
      this.#renderPlan();
      // One report for every finished plan: what was done, what failed, what was skipped.
      this.#setStatus(event.data.report.split("\n")[0] ?? "");
      this.#appendMessage("copilot", event.data.report);
      this.#setInputEnabled(this.#activeTaskId === undefined);
    }
  }

  #renderPlan(): void {
    const container = this.#root.querySelector<HTMLElement>("#plan-checklist");
    if (container === null) return;
    const plan = this.#plan;
    if (plan === undefined) {
      container.replaceChildren();
      container.hidden = true;
      return;
    }
    const document = this.#root.ownerDocument;
    const labels = PLAN_LABELS[plan.language];
    // The checklist sits at the end of the chat; a chat that was following the newest
    // message keeps following when the checklist grows (or every later message stops).
    const scroll = this.#root.querySelector<HTMLElement>("#chat-scroll");
    const follow =
      scroll !== null &&
      scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 100;
    container.hidden = false;
    container.dir = plan.language === "ar" ? "rtl" : "ltr";
    container.lang = plan.language;
    const heading = document.createElement("h2");
    heading.className = "plan-heading";
    heading.textContent = labels.heading;
    const list = document.createElement("ol");
    list.className = "plan-steps";
    list.setAttribute("aria-label", labels.heading);
    plan.steps.forEach((step) => {
      const [symbol, word] = labels.marks[step.mark];
      const item = document.createElement("li");
      item.className = `plan-step plan-step-${step.mark}`;
      item.dataset.mark = step.mark;
      if (step.mark === "running" || step.mark === "paused")
        item.setAttribute("aria-current", "step");
      const mark = document.createElement("span");
      mark.className = "plan-mark";
      mark.setAttribute("aria-hidden", "true");
      mark.textContent = symbol;
      const text = document.createElement("span");
      text.className = "plan-text";
      text.textContent = step.text;
      const state = document.createElement("span");
      state.className = "plan-state";
      state.textContent = word;
      item.append(mark, text, state);
      list.append(item);
    });
    container.replaceChildren(heading, list);
    if (plan.skipped.length > 0) {
      const note = document.createElement("p");
      note.className = "plan-skipped-note";
      note.textContent =
        labels.skippedNote + plan.skipped.join(labels.separator);
      container.append(note);
    }
    if (scroll !== null && follow) scroll.scrollTop = scroll.scrollHeight;
  }

  #renderRetry(): void {
    const container =
      this.#root.querySelector<HTMLElement>("#pending-question");
    if (container === null || this.#activeTaskId === undefined) return;
    const button = this.#root.ownerDocument.createElement("button");
    button.id = "retry-task";
    button.type = "button";
    button.textContent = "حاول تاني / Retry";
    button.addEventListener("click", () => {
      if (
        this.#sessionId === undefined ||
        this.#activeTaskId === undefined ||
        this.#snapshot === undefined
      )
        return;
      container.replaceChildren();
      this.#setStatus("بحاول تاني…");
      void this.#agent.retry(
        this.#sessionId,
        this.#activeTaskId,
        this.#snapshot,
      );
    });
    container.replaceChildren(button);
    button.focus();
  }

  #render(): void {
    this.#root.innerHTML = `
      <section class="copilot-panel" aria-labelledby="copilot-title" dir="rtl">
        <header class="panel-header">
          <div class="panel-identity">
            <span class="copilot-mark" aria-hidden="true">م</span>
            <div><h1 id="copilot-title">مساعد التسوّق</h1>
            <p class="store-mark">ابحث، قارن، واختر براحتك</p></div>
          </div>
          <button id="stop-task" class="stop-button" type="button">إيقاف</button>
        </header>
        <div id="task-status" class="status-ribbon" role="status" aria-live="polite">جاري الاتصال…</div>
        <div id="chat-scroll" class="chat-scroll" tabindex="0" aria-label="سجل المحادثة والاقتراحات">
        <div id="conversation-welcome" class="conversation-welcome">
          <span class="welcome-mark" aria-hidden="true">م</span>
          <h2>إيه اللي بتدور عليه؟</h2>
          <p>قولّي محتاج إيه وميزانيتك،<br>ونشوف الاختيارات المناسبة سوا.</p>
          <div class="example-requests">
            <button type="button" data-example="عايز كوتشي كورة تحت 2000 جنيه">كوتشي في حدود ميزانيتي</button>
            <button type="button" data-example="افتح السلة">افتح السلة</button>
          </div>
        </div>
        <ol id="conversation" class="conversation" aria-label="المحادثة"></ol>
        <section id="plan-checklist" class="plan-checklist" aria-live="polite" hidden></section>
        <section id="suggestions" class="suggestions" aria-label="اقتراحات المنتجات" aria-live="polite"></section>
        <div id="pending-question"></div>
        </div>
        <form class="message-form">
          <label for="shopper-message">ماذا تبحث عنه؟</label>
          <div class="speech-controls"><label for="speech-language">لغة الكلام</label><select id="speech-language"><option value="ar-EG">العربية المصرية</option><option value="en-US">English</option></select><button id="speech-input" type="button" aria-label="ابدأ الإدخال الصوتي" aria-pressed="false">🎙 إدخال صوتي</button></div>
          <div id="speech-fallback-area" hidden><button id="speech-fallback" type="button" aria-pressed="false">🎙 تسجيل قصير عبر OpenRouter</button><p>بالضغط على الزر، يُرسل تسجيل صوتي (حتى 10 ثوانٍ) إلى OpenRouter للتفريغ. راجع النص قبل إرساله.</p></div>
          <div class="input-row">
            <input id="shopper-message" name="message" placeholder="اكتب طلبك هنا…" autocomplete="off" required disabled />
            <button type="submit" disabled>إرسال</button>
          </div>
        </form>
      </section>`;

    this.#root
      .querySelectorAll<HTMLButtonElement>("[data-example]")
      .forEach((button) => {
        button.addEventListener("click", () => {
          const input =
            this.#root.querySelector<HTMLInputElement>("#shopper-message");
          if (!input || input.disabled) return;
          input.value = button.dataset.example ?? "";
          input.focus();
        });
      });

    this.#root
      .querySelector<HTMLFormElement>("form")
      ?.addEventListener("submit", (event) => {
        event.preventDefault();
        const input =
          this.#root.querySelector<HTMLInputElement>("#shopper-message");
        const text = input?.value.trim() ?? "";
        if (
          text === "" ||
          this.#sessionId === undefined ||
          this.#snapshot === undefined
        )
          return;
        this.#appendMessage("shopper", text);
        this.#plan = undefined;
        this.#renderPlan();
        this.#setStatus("أفهم طلبك الآن…");
        this.#submitting = true;
        this.#setInputEnabled(false);
        void this.#agent
          .submitMessage(this.#sessionId, text, this.#snapshot)
          .catch(() => {
            if (this.#activeTaskId !== undefined) return;
            this.#submitting = false;
            this.#setStatus("تعذر إرسال الطلب. حاول تاني.");
            this.#setInputEnabled(true);
          });
      });

    const view = this.#root.ownerDocument.defaultView as
      | (Window & {
          SpeechRecognition?: new () => BrowserSpeechRecognition;
          webkitSpeechRecognition?: new () => BrowserSpeechRecognition;
          MediaRecorder?: typeof MediaRecorder;
        })
      | null;
    const SpeechRecognition =
      view?.SpeechRecognition ?? view?.webkitSpeechRecognition;
    const MediaRecorderConstructor = view?.MediaRecorder;
    const speechButton =
      this.#root.querySelector<HTMLButtonElement>("#speech-input");
    const fallbackArea = this.#root.querySelector<HTMLElement>(
      "#speech-fallback-area",
    );
    const fallbackButton =
      this.#root.querySelector<HTMLButtonElement>("#speech-fallback");
    const canRecord = Boolean(
      MediaRecorderConstructor && view?.navigator.mediaDevices?.getUserMedia,
    );
    const offerRecording = () => {
      if (!canRecord || !fallbackArea) return;
      void this.#agent
        .speechAvailable()
        .then((available) => {
          if (!available) {
            this.#setStatus(
              this.#root.querySelector<HTMLSelectElement>("#speech-language")
                ?.value === "en-US"
                ? "OpenRouter transcription is unavailable. Check the service connection and the API key's remaining audio allowance. You can type your request or try browser speech in Chrome."
                : "التفريغ عبر OpenRouter غير متاح. تحقّق من اتصال الخدمة والرصيد المتبقي للصوت في مفتاح API. يمكنك كتابة طلبك أو تجربة صوت المتصفح في Chrome.",
            );
            return;
          }
          fallbackArea.hidden = false;
          this.#setStatus(
            this.#root.querySelector<HTMLSelectElement>("#speech-language")
              ?.value === "en-US"
              ? "Browser speech is unavailable. You can use the short recording button and review the text."
              : "خدمة الصوت في المتصفح غير متاحة. يمكنك استخدام زر التسجيل القصير ثم مراجعة النص.",
          );
        })
        .catch(() => undefined);
    };
    if (!SpeechRecognition && speechButton) {
      speechButton.disabled = true;
      speechButton.title = "الإدخال الصوتي غير متاح في هذا المتصفح";
      offerRecording();
    }
    speechButton?.addEventListener("click", () => {
      if (!SpeechRecognition || speechButton.disabled) return;
      if (this.#recognition) {
        this.#recognition.abort();
        this.#recognition = undefined;
        speechButton.setAttribute("aria-pressed", "false");
        return;
      }
      const recognition = new SpeechRecognition();
      recognition.lang =
        this.#root.querySelector<HTMLSelectElement>("#speech-language")
          ?.value ?? "ar-EG";
      recognition.onresult = (event) => {
        const transcript = event.results[0]?.[0]?.transcript?.trim();
        const input =
          this.#root.querySelector<HTMLInputElement>("#shopper-message");
        if (transcript && input) {
          input.value = transcript;
          input.focus();
          this.#setStatus("راجع النص ثم اضغط إرسال.");
        }
      };
      recognition.onerror = (event) => {
        if (event.error === "aborted") return;
        if (event.error === "network" || event.error === "service-not-allowed")
          offerRecording();
        const locale = recognition.lang === "en-US" ? "en" : "ar";
        this.#setStatus(
          SPEECH_ERROR_MESSAGES[event.error]?.[locale] ??
            (locale === "en"
              ? "Speech recognition failed. You can type your request."
              : "تعذر التقاط الصوت. يمكنك كتابة طلبك."),
        );
      };
      recognition.onend = () => {
        if (this.#recognition === recognition) this.#recognition = undefined;
        speechButton.setAttribute("aria-pressed", "false");
      };
      this.#recognition = recognition;
      speechButton.setAttribute("aria-pressed", "true");
      this.#setStatus("أستمع الآن…");
      try {
        recognition.start();
      } catch {
        this.#recognition = undefined;
        speechButton.setAttribute("aria-pressed", "false");
        this.#setStatus("تعذر بدء الإدخال الصوتي. يمكنك كتابة طلبك.");
      }
    });

    fallbackButton?.addEventListener("click", () => {
      if (
        !canRecord ||
        !view ||
        !MediaRecorderConstructor ||
        fallbackButton.disabled
      )
        return;
      this.#recognition?.abort();
      this.#recognition = undefined;
      speechButton?.setAttribute("aria-pressed", "false");
      if (this.#recorder) {
        if (this.#recorder.state !== "inactive") this.#recorder.stop();
        return;
      }
      const version = ++this.#speechVersion;
      void (async () => {
        let stream: MediaStream | undefined;
        try {
          stream = await view.navigator.mediaDevices.getUserMedia({
            audio: true,
          });
          if (version !== this.#speechVersion) {
            stream.getTracks().forEach((track) => track.stop());
            return;
          }
          const recorder = new MediaRecorderConstructor(stream, {
            mimeType: "audio/webm",
          });
          const chunks: Blob[] = [];
          let recordingFailed = false;
          this.#recorder = recorder;
          fallbackButton.setAttribute("aria-pressed", "true");
          fallbackButton.textContent = "إيقاف التسجيل وإظهار النص";
          this.#setStatus("أسجل الآن…");
          recorder.ondataavailable = (event) => {
            if (event.data.size) chunks.push(event.data);
          };
          recorder.onerror = () => {
            recordingFailed = true;
            if (recorder.state !== "inactive") recorder.stop();
            this.#setStatus("تعذر التسجيل. يمكنك كتابة طلبك.");
          };
          const timer = view.setTimeout(() => {
            if (recorder.state !== "inactive") recorder.stop();
          }, 10_000);
          recorder.onstop = () => {
            view.clearTimeout(timer);
            stream?.getTracks().forEach((track) => track.stop());
            if (this.#recorder === recorder) this.#recorder = undefined;
            fallbackButton.setAttribute("aria-pressed", "false");
            fallbackButton.textContent = "🎙 تسجيل قصير عبر OpenRouter";
            if (version !== this.#speechVersion) return;
            if (recordingFailed) return;
            const audio = new Blob(chunks, { type: "audio/webm" });
            if (!audio.size || audio.size > 750_000) {
              this.#setStatus("التسجيل فارغ أو طويل جدًا. حاول ثانية.");
              return;
            }
            fallbackButton.disabled = true;
            this.#setStatus("أحول التسجيل إلى نص…");
            const language =
              this.#root.querySelector<HTMLSelectElement>("#speech-language")
                ?.value === "en-US"
                ? "en"
                : "ar";
            void this.#agent
              .transcribeSpeech(audio, language)
              .then((text) => {
                if (version !== this.#speechVersion) return;
                const input =
                  this.#root.querySelector<HTMLInputElement>(
                    "#shopper-message",
                  );
                if (input) {
                  input.value = text;
                  input.focus();
                  this.#setStatus("راجع النص ثم اضغط إرسال.");
                }
              })
              .catch(() => {
                if (version === this.#speechVersion)
                  this.#setStatus("تعذر تفريغ التسجيل. يمكنك كتابة طلبك.");
              })
              .finally(() => {
                fallbackButton.disabled = false;
              });
          };
          recorder.start();
        } catch {
          stream?.getTracks().forEach((track) => track.stop());
          if (version === this.#speechVersion) {
            this.#recorder = undefined;
            fallbackButton.setAttribute("aria-pressed", "false");
            fallbackButton.textContent = "🎙 تسجيل قصير عبر OpenRouter";
            this.#setStatus(
              "تعذر بدء التسجيل. راجع إذن الميكروفون أو اكتب طلبك.",
            );
          }
        }
      })();
    });

    this.#root
      .querySelector<HTMLButtonElement>("#stop-task")
      ?.addEventListener("click", () => {
        this.#recognition?.abort();
        this.#recognition = undefined;
        this.#speechVersion++;
        if (this.#recorder && this.#recorder.state !== "inactive")
          this.#recorder.stop();
        if (this.#sessionId === undefined) return;
        if (this.#activeTaskId !== undefined) {
          this.#cancelledTaskIds.add(this.#activeTaskId);
          this.#storefront.cancelTask(this.#activeTaskId);
        }
        void this.#agent.stop(this.#sessionId);
      });
  }

  #renderQuestion(action: Extract<Action, { type: "ask_shopper" }>): void {
    const container =
      this.#root.querySelector<HTMLElement>("#pending-question");
    if (container === null) return;
    this.#waitingForLoginUrl = undefined;
    container.replaceChildren();
    const card = this.#root.ownerDocument.createElement("section");
    card.className =
      action.kind === "confirmation"
        ? "question-card confirmation-card"
        : "question-card";
    card.setAttribute(
      "aria-label",
      action.kind === "confirmation"
        ? action.options.includes("تأكيد")
          ? "تأكيد إجراء مؤثر"
          : "Confirm Guarded Mutation"
        : "سؤال من مساعد التسوّق",
    );
    const question = this.#root.ownerDocument.createElement("p");
    question.textContent = action.question;
    card.append(question);
    const submitAnswer = (text: string) => {
      if (this.#sessionId === undefined || this.#snapshot === undefined) return;
      const currentUrl = this.#snapshot.url;
      const buttons = Array.from(card.querySelectorAll("button"));
      for (const button of buttons) button.disabled = true;
      void this.#agent
        .submitAnswer(
          this.#sessionId,
          action.task_id,
          action.action_id,
          text,
          this.#snapshot,
        )
        .then((status) => {
          if (!container.contains(card)) return;
          if (status === "resumed") {
            container.replaceChildren();
            return;
          }
          if (this.#snapshot?.url !== currentUrl) {
            for (const button of buttons) button.disabled = false;
            this.#setStatus(
              "اتغيرت صفحة المتجر. اختر متابعة للتحقق من سجل الطلبات.",
            );
            return;
          }
          this.#waitingForLoginUrl = currentUrl;
          for (const button of buttons)
            button.disabled = button.dataset.questionOption === "Continue";
          let hint = card.querySelector<HTMLElement>("#login-wait-hint");
          if (hint === null) {
            hint = this.#root.ownerDocument.createElement("p");
            hint.id = "login-wait-hint";
            hint.setAttribute("role", "status");
            card.append(hint);
          }
          hint.textContent =
            "سجّل الدخول بنفسك في المتجر أولًا، وبعد انتقال الصفحة اختَر متابعة. لن أقرأ بيانات الدخول.";
        })
        .catch(() => {
          if (!container.contains(card)) return;
          for (const button of buttons) button.disabled = false;
          this.#setStatus("تعذر إرسال إجابتك. حاول تاني أو أوقف المهمة.");
        });
    };
    for (const optionText of action.options) {
      const option = this.#root.ownerDocument.createElement("button");
      option.type = "button";
      option.textContent = optionText;
      option.dataset.questionOption = optionText;
      option.addEventListener("click", () => submitAnswer(optionText));
      card.append(option);
    }
    if (action.options.length === 0) {
      const form = this.#root.ownerDocument.createElement("form");
      form.id = "question-answer-form";
      const input = this.#root.ownerDocument.createElement("input");
      input.id = "question-answer-input";
      input.required = true;
      const arabic = /[\u0600-\u06ff]/u.test(action.question);
      input.setAttribute("aria-label", arabic ? "توضيح طلبك" : "Your answer");
      const submit = this.#root.ownerDocument.createElement("button");
      submit.type = "submit";
      submit.textContent = arabic ? "إرسال التوضيح" : "Send answer";
      form.append(input, submit);
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const text = input.value.trim();
        if (text !== "") submitAnswer(text);
      });
      card.append(form);
    }
    container.append(card);
    (card.querySelector("input") ?? card.querySelector("button"))?.focus();
  }

  #registerQuestion(action: Extract<Action, { type: "ask_shopper" }>): void {
    this.#questionActionIds.add(`${action.task_id}:${action.action_id}`);
    this.#storefront.sendAction(action);
  }

  #renderSuggestions(result: SuggestionResult | null): void {
    const container = this.#root.querySelector<HTMLElement>("#suggestions");
    if (container === null) return;
    const scroll = this.#root.querySelector<HTMLElement>("#chat-scroll");
    const follow =
      scroll !== null &&
      scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 100;
    container.replaceChildren();
    if (result === null) return;
    for (const suggestion of result.suggestions) {
      const article = this.#root.ownerDocument.createElement("article");
      article.className = `suggestion-card suggestion-${suggestion.label}`;
      article.dataset.productId = suggestion.id;
      article.dataset.matchKind = suggestion.label;
      const label = this.#root.ownerDocument.createElement("p");
      label.className = "suggestion-label";
      label.textContent = {
        exact_match: "مطابق / Exact Match",
        alternative: "بديل / Alternative",
        styling_suggestion: "تنسيق / Styling Suggestion",
      }[suggestion.label];
      const title = this.#root.ownerDocument.createElement("h2");
      title.textContent = suggestion.name;
      const price = this.#root.ownerDocument.createElement("p");
      price.className = "suggestion-price";
      price.textContent = `${suggestion.price} ${suggestion.currency}`;
      const reason = this.#root.ownerDocument.createElement("p");
      reason.className = "suggestion-reason";
      reason.textContent = suggestion.reason;
      article.append(label, title, price, reason);
      if (suggestion.unmet.length > 0) {
        const unmet = this.#root.ownerDocument.createElement("p");
        unmet.textContent = `غير متحقق / Unmet: ${suggestion.unmet.join(", ")}`;
        article.append(unmet);
      }
      container.append(article);
    }
    if (scroll && follow && container.firstElementChild) {
      scroll.scrollTop +=
        container.getBoundingClientRect().top -
        scroll.getBoundingClientRect().top;
    }
  }

  #setStatus(message: string): void {
    const status = this.#root.querySelector<HTMLElement>("#task-status");
    if (status !== null)
      status.textContent = this.#shopperInvalid
        ? "انقطع اتصال جلسة التسوق. أعد تحميل الصفحة وراجع السلة قبل المحاولة. / Shopping session disconnected. Reload and check your cart before retrying."
        : message;
  }

  #setTaskState(value: string): void {
    const status = this.#root.querySelector<HTMLElement>("#task-status");
    if (status !== null) status.dataset.taskState = value;
  }

  #setInputEnabled(enabled: boolean): void {
    enabled = enabled && !this.#shopperInvalid && this.#plan?.active !== true;
    const input =
      this.#root.querySelector<HTMLInputElement>("#shopper-message");
    if (input !== null) input.disabled = !enabled;
    const send =
      this.#root.querySelector<HTMLButtonElement>(".input-row button");
    if (send !== null) send.disabled = !enabled;
    const speech = this.#root.querySelector<HTMLButtonElement>("#speech-input");
    if (speech !== null && !speech.title) speech.disabled = !enabled;
  }

  #appendMessage(role: "shopper" | "copilot", message: string): void {
    const conversation =
      this.#root.querySelector<HTMLOListElement>("#conversation");
    if (conversation === null) return;
    const scroll = this.#root.querySelector<HTMLElement>("#chat-scroll");
    const follow =
      scroll !== null &&
      scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 100;
    const firstSuggestion =
      this.#root.querySelector<HTMLElement>(".suggestion-card");
    const suggestionOffset =
      scroll && firstSuggestion
        ? firstSuggestion.getBoundingClientRect().top -
          scroll.getBoundingClientRect().top
        : undefined;
    const welcome = this.#root.querySelector<HTMLElement>(
      "#conversation-welcome",
    );
    if (welcome) welcome.hidden = true;
    const item = this.#root.ownerDocument.createElement("li");
    item.className = `message message-${role}`;
    item.textContent = message;
    conversation.append(item);
    if (
      scroll &&
      role === "copilot" &&
      firstSuggestion &&
      suggestionOffset !== undefined &&
      suggestionOffset >= 0 &&
      suggestionOffset < scroll.clientHeight
    ) {
      // Keep the first recommendation visible when the completion summary is inserted above it.
      scroll.scrollTop +=
        firstSuggestion.getBoundingClientRect().top -
        scroll.getBoundingClientRect().top -
        suggestionOffset;
    } else if (scroll && (follow || role === "shopper")) {
      scroll.scrollTop = scroll.scrollHeight;
    }
  }
}
