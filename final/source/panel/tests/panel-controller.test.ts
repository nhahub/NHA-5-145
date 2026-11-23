import { JSDOM } from "jsdom";
import { describe, expect, it, vi } from "vitest";

import {
  PanelController,
  type AgentEvent,
  type AgentTransport,
  type StorefrontChannel,
  type SessionPersistence,
  type SessionView,
} from "../src/panel.js";

const snapshot = {
  v: 1 as const,
  url: "http://localhost:4000/",
  title: "المتجر التجريبي",
  lang: "ar",
  viewport: { w: 390, h: 844, scrollY: 0 },
  truncated: false,
  elements: [],
};

it("blocks late messages and snapshots after shopper authority is lost", async () => {
  const { controller, root, emit, actions } = setup();
  await controller.start();
  controller.receiveStorefront({ type: "snapshot", snapshot });
  controller.invalidateShopper();
  controller.receiveStorefront({ type: "snapshot", snapshot });
  emit({ type: "narration", data: { text: "late" } });
  expect(
    root.querySelector<HTMLInputElement>("#shopper-message")!.disabled,
  ).toBe(true);
  expect(root.querySelector("#task-status")!.textContent).toContain("Reload");
  expect(actions).toEqual([]);
});

function setup(options?: {
  savedSessionId?: string;
  restoredState?: SessionView;
  restoreError?: Error;
  restoreGate?: Promise<void>;
  answerStatus?: "resumed" | "awaiting_login";
  answerGate?: Promise<void>;
  reconcileGate?: Promise<void>;
  resultError?: Error;
  speechRecognition?: new () => {
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
  };
  mediaRecorder?: typeof MediaRecorder;
  getUserMedia?: () => Promise<MediaStream>;
  speechAvailable?: boolean;
}) {
  const dom = new JSDOM('<!doctype html><div id="app"></div>');
  if (options?.speechRecognition)
    Object.defineProperty(dom.window, "SpeechRecognition", {
      value: options.speechRecognition,
    });
  if (options?.mediaRecorder)
    Object.defineProperty(dom.window, "MediaRecorder", {
      value: options.mediaRecorder,
    });
  if (options?.getUserMedia)
    Object.defineProperty(dom.window.navigator, "mediaDevices", {
      value: { getUserMedia: options.getUserMedia },
    });
  const submitted: Array<{
    sessionId: string;
    text: string;
    snapshot: unknown;
  }> = [];
  const transcribed: Array<{ audio: Blob; language: string }> = [];
  const results: unknown[] = [];
  const stopped: string[] = [];
  const answers: unknown[] = [];
  const reconciliations: unknown[] = [];
  const takeovers: unknown[] = [];
  const retries: unknown[] = [];
  let eventHandler: ((event: AgentEvent) => void) | undefined;
  const agent: AgentTransport = {
    createSession: async () => "session-1",
    restoreSession: async () => {
      await options?.restoreGate;
      if (options?.restoreError !== undefined) throw options.restoreError;
      return (
        options?.restoredState ?? {
          session_id: options?.savedSessionId ?? "session-1",
          lease: "owned",
          event_cursor: 0,
          conversation: [],
          requires_reconciliation: false,
          task: null,
        }
      );
    },
    reconcile: async (sessionId, _tabId, currentSnapshot) => {
      reconciliations.push({ sessionId, snapshot: currentSnapshot });
      await options?.reconcileGate;
      return {
        session_id: sessionId,
        lease: "owned",
        event_cursor: 4,
        conversation: options?.restoredState?.conversation ?? [],
        requires_reconciliation: false,
        plan: options?.restoredState?.plan ?? null,
        task: options?.restoredState?.task ?? null,
      };
    },
    takeover: async (sessionId, tabId) => {
      takeovers.push({ sessionId, tabId });
      return { ...options!.restoredState!, lease: "owned" };
    },
    subscribe: (_sessionId, handler) => {
      eventHandler = handler;
      return () => undefined;
    },
    submitMessage: async (sessionId, text, currentSnapshot) => {
      submitted.push({ sessionId, text, snapshot: currentSnapshot });
    },
    transcribeSpeech: async (audio, language) => {
      transcribed.push({ audio, language });
      return "عايز كوتشي جري";
    },
    speechAvailable: async () => options?.speechAvailable ?? true,
    submitActionResult: async (_sessionId, result) => {
      results.push(result);
      if (options?.resultError) throw options.resultError;
    },
    submitAnswer: async (
      sessionId,
      taskId,
      questionId,
      text,
      currentSnapshot,
    ) => {
      answers.push({
        sessionId,
        taskId,
        questionId,
        text,
        snapshot: currentSnapshot,
      });
      await options?.answerGate;
      return options?.answerStatus ?? "resumed";
    },
    stop: async (sessionId) => {
      stopped.push(sessionId);
    },
    retry: async (sessionId, taskId, currentSnapshot) => {
      retries.push({ sessionId, taskId, snapshot: currentSnapshot });
    },
  };
  const actions: unknown[] = [];
  const cancelledTasks: string[] = [];
  let snapshotRequests = 0;
  const storefront: StorefrontChannel = {
    sendAction: (action) => actions.push(action),
    cancelTask: (taskId) => cancelledTasks.push(taskId),
    requestSnapshot: () => snapshotRequests++,
  };
  const root = dom.window.document.querySelector<HTMLElement>("#app")!;
  let savedSessionId = options?.savedSessionId;
  let savedCursor = 0;
  const persistence: SessionPersistence = {
    loadSessionId: () => savedSessionId,
    saveSessionId: (sessionId) => {
      savedSessionId = sessionId;
    },
    clearSession: () => {
      savedSessionId = undefined;
      savedCursor = 0;
    },
    loadEventCursor: () => savedCursor,
    saveEventCursor: (cursor) => {
      savedCursor = cursor;
    },
  };
  const controller = new PanelController(root, agent, storefront, {
    persistence,
    tabId: "tab-1",
  });
  return {
    dom,
    root,
    controller,
    submitted,
    transcribed,
    results,
    stopped,
    answers,
    actions,
    cancelledTasks,
    reconciliations,
    takeovers,
    retries,
    snapshotRequests: () => snapshotRequests,
    emit: (event: AgentEvent) => eventHandler?.(event),
  };
}

describe("PanelController", () => {
  it("does not enable shopping before linked session startup completes", async () => {
    const context = setup();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    expect(
      context.root.querySelector<HTMLInputElement>("#shopper-message")!
        .disabled,
    ).toBe(true);
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    expect(
      context.root.querySelector<HTMLInputElement>("#shopper-message")!
        .disabled,
    ).toBe(false);
  });
  it("shows uncertain delivery without replaying a cart change when result submission fails", async () => {
    const context = setup({ resultError: new Error("HTTP 422") });
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    context.emit({ type: "task_started", data: { task_id: "task-1" } });
    context.controller.receiveStorefront({
      type: "action_result",
      result: {
        v: 1,
        task_id: "task-1",
        action_id: "action-1",
        sequence_number: 1,
        status: "ok",
        snapshot,
      },
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(context.root.querySelector("#task-status")?.textContent).toContain(
      "راجع السلة",
    );
    expect(context.root.querySelector("#retry-task")).toBeNull();
    expect(context.results).toHaveLength(1);
    expect(context.cancelledTasks).toEqual(["task-1"]);
    expect(
      context.root.querySelector<HTMLButtonElement>("#stop-task")?.disabled,
    ).toBe(false);
  });
  it("fills an editable example without sending and hides the welcome after submission", async () => {
    const context = setup();
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    context.root.querySelector<HTMLButtonElement>("[data-example]")!.click();
    const input =
      context.root.querySelector<HTMLInputElement>("#shopper-message")!;
    expect(input.value).toBe("عايز كوتشي كورة تحت 2000 جنيه");
    expect(context.submitted).toHaveLength(0);
    expect(context.dom.window.document.activeElement).toBe(input);
    context.root.querySelector<HTMLButtonElement>(".input-row button")!.click();
    expect(context.submitted).toHaveLength(1);
    expect(
      context.root.querySelector<HTMLElement>("#conversation-welcome")!.hidden,
    ).toBe(true);
    expect(
      context.root.querySelector<HTMLButtonElement>(".input-row button")!
        .disabled,
    ).toBe(true);
    context.emit({ type: "done", data: { summary: "Done", language: "en" } });
    expect(
      context.root.querySelector<HTMLButtonElement>(".input-row button")!
        .disabled,
    ).toBe(false);
  });

  it("shows labelled grounded suggestions and restores them without a browser Action", async () => {
    const suggestions = {
      exact_count: 0,
      suggestions: [
        {
          id: "shoe-07",
          label: "alternative" as const,
          name: "راحة يومية",
          price: "1350",
          currency: "EGP" as const,
          reason: "بديل؛ لا يمكن تأكيد مناسبة الفرح.",
          unmet: ["suitable_for: formal_events"],
        },
      ],
    };
    const context = setup();
    await context.controller.start();
    context.emit({ type: "task_started", data: { task_id: "task-1" } });
    context.emit({ type: "suggestions", data: suggestions });
    context.emit({
      type: "done",
      data: { summary: "No exact match", language: "ar" },
    });
    expect(context.actions).toHaveLength(0);
    expect(
      context.root.querySelector('[data-product-id="shoe-07"]')?.textContent,
    ).toContain("Alternative");
    expect(
      context.root.querySelector('[data-product-id="shoe-07"]')?.textContent,
    ).toContain("formal_events");
    expect(
      context.root
        .querySelector("#task-status")
        ?.getAttribute("data-task-state"),
    ).toBe("completed");

    const restored = setup({
      savedSessionId: "session-1",
      restoredState: {
        session_id: "session-1",
        lease: "owned",
        event_cursor: 3,
        conversation: [{ role: "copilot", text: "No exact match" }],
        requires_reconciliation: false,
        task: {
          task_id: "task-1",
          status: "completed",
          pending_question: null,
          suggestions,
        },
      },
    });
    await restored.controller.start();
    restored.controller.receiveStorefront({ type: "snapshot", snapshot });
    await Promise.resolve();
    await Promise.resolve();
    expect(restored.root.querySelectorAll(".suggestion-card")).toHaveLength(1);
    expect(restored.actions).toHaveLength(0);
  });
  it("keeps a failed interpretation active and offers Retry and Stop", async () => {
    const context = setup();
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    context.emit({ type: "task_started", data: { task_id: "task-retry" } });
    context.emit({
      type: "error",
      data: { message: "Couldn't interpret the request." },
    });

    expect(
      context.root.querySelector<HTMLInputElement>("#shopper-message")
        ?.disabled,
    ).toBe(true);
    context.root.querySelector<HTMLButtonElement>("#retry-task")?.click();
    await Promise.resolve();
    expect(context.retries).toEqual([
      { sessionId: "session-1", taskId: "task-retry", snapshot },
    ]);
    expect(
      context.root.querySelector<HTMLButtonElement>("#stop-task"),
    ).not.toBeNull();
  });
  it("shows the task surface and submits a Shopper message with the current Snapshot", async () => {
    const context = setup();
    await context.controller.start();
    expect(context.snapshotRequests()).toBe(1);
    const input =
      context.root.querySelector<HTMLInputElement>("#shopper-message")!;
    expect(input.disabled).toBe(true);

    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    expect(input.disabled).toBe(false);

    input.value = "عاوز كوتشي للجري بأقل من ٢٠٠٠";
    context.root.querySelector<HTMLFormElement>("form")!.dispatchEvent(
      new context.dom.window.Event("submit", {
        bubbles: true,
        cancelable: true,
      }),
    );
    await Promise.resolve();

    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    expect(input.disabled).toBe(true);

    expect(context.root.querySelector('[role="status"]')).not.toBeNull();
    expect(context.root.querySelector("#stop-task")).not.toBeNull();
    expect(context.submitted).toEqual([
      { sessionId: "session-1", text: input.value, snapshot },
    ]);
    expect(context.root.querySelector("#conversation")?.textContent).toContain(
      input.value,
    );
  });

  it("relays ordered Agent Actions and matching Bridge results", async () => {
    const context = setup();
    await context.controller.start();
    const action = {
      v: 1 as const,
      type: "navigate" as const,
      task_id: "task-1",
      action_id: "action-1",
      sequence_number: 1,
      narration: "هفلتر المنتجات.",
      url: "/c/shoes?type=running&max_price=2000",
    };

    context.emit({ type: "narration", data: { text: action.narration } });
    context.emit({ type: "action", data: { action } });
    context.controller.receiveStorefront({
      type: "action_result",
      result: {
        v: 1,
        task_id: "task-1",
        action_id: "action-1",
        sequence_number: 1,
        status: "navigated",
        snapshot,
      },
    });
    await Promise.resolve();

    expect(context.root.querySelector('[role="status"]')?.textContent).toBe(
      action.narration,
    );
    expect(context.actions).toEqual([action]);
    expect(context.results).toHaveLength(1);
  });

  it("keeps Stop reachable and sends it to the active session", async () => {
    const context = setup();
    await context.controller.start();

    context.root.querySelector<HTMLButtonElement>("#stop-task")!.click();
    await Promise.resolve();

    expect(context.stopped).toEqual(["session-1"]);
  });

  it("renders a Shopper question and resumes it from a matching option", async () => {
    const context = setup();
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    context.emit({ type: "task_started", data: { task_id: "task-1" } });
    context.emit({
      type: "action",
      data: {
        action: {
          v: 1,
          type: "ask_shopper",
          task_id: "task-1",
          action_id: "question-1",
          sequence_number: 1,
          narration: "I need an EGP amount.",
          question: "What is your budget in EGP?",
          options: ["2000 EGP", "No budget"],
        },
      },
    });

    const option = context.root.querySelector<HTMLButtonElement>(
      '[data-question-option="2000 EGP"]',
    )!;
    expect(option).not.toBeNull();
    expect(context.dom.window.document.activeElement).toBe(option);
    option.click();
    await Promise.resolve();

    expect(context.actions).toEqual([
      expect.objectContaining({
        type: "ask_shopper",
        task_id: "task-1",
        action_id: "question-1",
        sequence_number: 1,
      }),
    ]);
    expect(context.answers).toEqual([
      {
        sessionId: "session-1",
        taskId: "task-1",
        questionId: "question-1",
        text: "2000 EGP",
        snapshot,
      },
    ]);
  });

  it("shows a distinct exact-effect Confirmation card and sends the chosen option", async () => {
    const context = setup();
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    context.emit({ type: "task_started", data: { task_id: "task-clear" } });
    context.emit({
      type: "action",
      data: {
        action: {
          v: 1,
          type: "ask_shopper",
          kind: "confirmation",
          task_id: "task-clear",
          action_id: "confirmation-1234567890abcdef1234567890abcdef",
          sequence_number: 1,
          narration: "Confirm this action.",
          question:
            "Confirm this action: Remove every item from the current cart. Continue?",
          options: ["Confirm", "Stop"],
        },
      },
    });

    const card = context.root.querySelector<HTMLElement>(".confirmation-card");
    expect(card?.getAttribute("aria-label")).toBe("Confirm Guarded Mutation");
    expect(card?.textContent).toContain(
      "Remove every item from the current cart",
    );
    card
      ?.querySelector<HTMLButtonElement>('[data-question-option="Confirm"]')
      ?.click();
    await Promise.resolve();
    expect(context.answers).toEqual([
      expect.objectContaining({
        questionId: "confirmation-1234567890abcdef1234567890abcdef",
        text: "Confirm",
      }),
    ]);
  });

  it("keeps the sign-in handoff visible without repeating Continue until the page changes", async () => {
    const context = setup({ answerStatus: "awaiting_login" });
    await context.controller.start();
    const login = {
      ...snapshot,
      url: "http://localhost:4000/login?next=%2Faccount%2Forders",
    };
    context.controller.receiveStorefront({ type: "snapshot", snapshot: login });
    context.emit({ type: "task_started", data: { task_id: "task-orders" } });
    context.emit({
      type: "action",
      data: {
        action: {
          v: 1,
          type: "ask_shopper",
          task_id: "task-orders",
          action_id: "question-login",
          sequence_number: 2,
          narration: "Sign in yourself first.",
          question: "After signing in, should I continue?",
          options: ["Continue", "Stop"],
        },
      },
    });

    context.root
      .querySelector<HTMLButtonElement>('[data-question-option="Continue"]')!
      .click();
    await Promise.resolve();
    await Promise.resolve();

    const continueButton = context.root.querySelector<HTMLButtonElement>(
      '[data-question-option="Continue"]',
    )!;
    expect(continueButton.disabled).toBe(true);
    expect(
      context.root.querySelector("#pending-question")?.textContent,
    ).toContain("سجّل الدخول");
    continueButton.click();
    expect(context.answers).toHaveLength(1);
    expect(
      context.root.querySelector<HTMLButtonElement>(
        '[data-question-option="Stop"]',
      )?.disabled,
    ).toBe(false);

    context.controller.receiveStorefront({
      type: "snapshot",
      snapshot: { ...snapshot, url: "http://localhost:4000/account/orders" },
    });
    expect(continueButton.disabled).toBe(false);
  });

  it("does not re-lock Continue if sign-in completes before the waiting response arrives", async () => {
    let releaseAnswer!: () => void;
    const answerGate = new Promise<void>((resolve) => {
      releaseAnswer = resolve;
    });
    const context = setup({ answerStatus: "awaiting_login", answerGate });
    await context.controller.start();
    context.controller.receiveStorefront({
      type: "snapshot",
      snapshot: {
        ...snapshot,
        url: "http://localhost:4000/login?next=%2Faccount%2Forders",
      },
    });
    context.emit({ type: "task_started", data: { task_id: "task-orders" } });
    context.emit({
      type: "action",
      data: {
        action: {
          v: 1,
          type: "ask_shopper",
          task_id: "task-orders",
          action_id: "question-login",
          sequence_number: 2,
          narration: "Sign in yourself first.",
          question: "After signing in, should I continue?",
          options: ["Continue", "Stop"],
        },
      },
    });
    const continueButton = context.root.querySelector<HTMLButtonElement>(
      '[data-question-option="Continue"]',
    )!;
    continueButton.click();
    context.controller.receiveStorefront({
      type: "snapshot",
      snapshot: { ...snapshot, url: "http://localhost:4000/account/orders" },
    });
    releaseAnswer();
    await Promise.resolve();
    await Promise.resolve();
    expect(continueButton.disabled).toBe(false);
  });

  it("registers a clarification in Bridge without treating its receipt as a Shopper answer", async () => {
    const context = setup();
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    context.emit({ type: "task_started", data: { task_id: "task-cart" } });
    const question = {
      v: 1 as const,
      type: "ask_shopper" as const,
      task_id: "task-cart",
      action_id: "question-cart",
      sequence_number: 1,
      narration: "Which page?",
      question: "Which page should I open?",
      options: ["افتح السلة"],
    };
    context.emit({ type: "action", data: { action: question } });
    expect(context.actions).toEqual([question]);

    context.controller.receiveStorefront({
      type: "action_result",
      result: {
        v: 1,
        task_id: "task-cart",
        action_id: "question-cart",
        sequence_number: 1,
        status: "ok",
        snapshot,
      },
    });
    await Promise.resolve();
    expect(context.results).toHaveLength(0);

    const navigate = {
      v: 1 as const,
      type: "navigate" as const,
      task_id: "task-cart",
      action_id: "open-cart",
      sequence_number: 2,
      narration: "Opening cart",
      url: "/cart",
    };
    context.emit({ type: "action", data: { action: navigate } });
    expect(context.actions).toEqual([question, navigate]);
    context.controller.receiveStorefront({
      type: "action_result",
      result: {
        v: 1,
        task_id: "task-cart",
        action_id: "open-cart",
        sequence_number: 2,
        status: "navigated",
        snapshot,
      },
    });
    await Promise.resolve();
    expect(context.results).toEqual([
      expect.objectContaining({ action_id: "open-cart", status: "navigated" }),
    ]);
  });

  it("accepts a typed answer when a Shopper question has no options", async () => {
    const context = setup();
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    context.emit({ type: "task_started", data: { task_id: "task-typed" } });
    context.emit({
      type: "action",
      data: {
        action: {
          v: 1,
          type: "ask_shopper",
          task_id: "task-typed",
          action_id: "question-typed",
          sequence_number: 1,
          narration: "I need an EGP amount.",
          question: "What is your budget in EGP?",
          options: [],
        },
      },
    });
    const input = context.root.querySelector<HTMLInputElement>(
      "#question-answer-input",
    )!;
    input.value = "2000 EGP";
    context.root
      .querySelector<HTMLFormElement>("#question-answer-form")!
      .dispatchEvent(
        new context.dom.window.Event("submit", {
          bubbles: true,
          cancelable: true,
        }),
      );
    await Promise.resolve();

    expect(context.answers[0]).toMatchObject({
      taskId: "task-typed",
      questionId: "question-typed",
      text: "2000 EGP",
    });
  });

  it("retires the active task immediately when Stop is pressed", async () => {
    const context = setup();
    await context.controller.start();
    context.emit({ type: "task_started", data: { task_id: "task-stop" } });

    context.root.querySelector<HTMLButtonElement>("#stop-task")!.click();
    context.emit({
      type: "action",
      data: {
        action: {
          v: 1,
          type: "navigate",
          task_id: "task-stop",
          action_id: "late-action",
          sequence_number: 1,
          narration: "Too late.",
          url: "/c/shoes",
        },
      },
    });
    await Promise.resolve();

    expect(context.cancelledTasks).toEqual(["task-stop"]);
    expect(context.actions).toEqual([]);
  });

  it("keeps English task completion in English", async () => {
    const context = setup();
    await context.controller.start();

    context.emit({
      type: "done",
      data: {
        summary: "Running shoes within your budget are now shown.",
        language: "en",
      },
    });

    expect(context.root.querySelector('[role="status"]')?.textContent).toBe(
      "Task complete",
    );
    expect(context.root.querySelector("#conversation")?.textContent).toContain(
      "Running shoes within your budget are now shown.",
    );
  });

  it("restores conversation only after reconciling a fresh Snapshot", async () => {
    const restoredState: SessionView = {
      session_id: "session-restored",
      lease: "owned",
      event_cursor: 3,
      conversation: [
        { role: "shopper", text: "Show me running shoes" },
        { role: "copilot", text: "I was applying your filters." },
      ],
      requires_reconciliation: true,
      task: {
        task_id: "task-restored",
        status: "awaiting_action_result",
        pending_question: null,
      },
    };
    const context = setup({
      savedSessionId: "session-restored",
      restoredState,
    });

    await context.controller.start();
    expect(context.root.querySelector("#task-status")?.textContent).toBe(
      "Reconnecting…",
    );
    expect(
      context.root.querySelector<HTMLInputElement>("#shopper-message")
        ?.disabled,
    ).toBe(true);

    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    await Promise.resolve();
    await Promise.resolve();

    expect(context.reconciliations).toEqual([
      { sessionId: "session-restored", snapshot },
    ]);
    expect(context.root.querySelector("#conversation")?.textContent).toContain(
      "Show me running shoes",
    );
  });

  it("reconciles the latest Storefront Snapshot once when reload delivers overlapping snapshots", async () => {
    let release!: () => void;
    const reconcileGate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const context = setup({
      savedSessionId: "session-restored",
      reconcileGate,
    });
    await context.controller.start();
    const latest = { ...snapshot, url: "http://localhost:4000/cart" };
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    context.controller.receiveStorefront({
      type: "snapshot",
      snapshot: latest,
    });

    expect(context.reconciliations).toEqual([
      { sessionId: "session-restored", snapshot },
    ]);
    release();
    await Promise.resolve();
    await Promise.resolve();
    expect(context.reconciliations).toEqual([
      { sessionId: "session-restored", snapshot },
      { sessionId: "session-restored", snapshot: latest },
    ]);
  });

  it("ignores early snapshots until restored tab ownership permits reconciliation", async () => {
    let release!: () => void;
    const restoreGate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const context = setup({
      savedSessionId: "session-other",
      restoreGate,
      restoredState: {
        session_id: "session-other",
        lease: "takeover_required",
        event_cursor: 0,
        conversation: [],
        requires_reconciliation: true,
        task: null,
      },
    });
    const starting = context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    expect(context.reconciliations).toEqual([]);
    release();
    await starting;
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    expect(context.reconciliations).toEqual([]);
    expect(
      context.root.querySelector<HTMLInputElement>("#shopper-message")!
        .disabled,
    ).toBe(true);
    expect(context.root.querySelector("#task-status")!.textContent).toContain(
      "another tab",
    );
  });

  it("requires explicit takeover before another tab can reconnect", async () => {
    const restoredState: SessionView = {
      session_id: "session-owned-elsewhere",
      lease: "takeover_required",
      event_cursor: 2,
      conversation: [],
      requires_reconciliation: true,
      task: {
        task_id: "task-1",
        status: "awaiting_action_result",
        pending_question: null,
      },
    };
    const context = setup({
      savedSessionId: "session-owned-elsewhere",
      restoredState,
    });

    await context.controller.start();
    const takeover =
      context.root.querySelector<HTMLButtonElement>("#takeover-session");
    expect(takeover).not.toBeNull();
    takeover!.click();
    await Promise.resolve();

    expect(context.takeovers).toEqual([
      { sessionId: "session-owned-elsewhere", tabId: "tab-1" },
    ]);
  });

  it("restores Retry for a paused model call after refresh", async () => {
    const restoredState: SessionView = {
      session_id: "session-paused",
      lease: "owned",
      event_cursor: 3,
      conversation: [{ role: "shopper", text: "عاوز حذاء" }],
      requires_reconciliation: false,
      task: {
        task_id: "task-paused",
        status: "paused",
        pending_question: null,
        pause_message: "The model service timed out. Retry or stop the task.",
      },
    };
    const context = setup({ savedSessionId: "session-paused", restoredState });
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    await Promise.resolve();
    await Promise.resolve();

    const retry = context.root.querySelector<HTMLButtonElement>("#retry-task");
    expect(retry).not.toBeNull();
    expect(context.root.querySelector("#task-status")?.textContent).toContain(
      "timed out",
    );
    const changed = {
      ...snapshot,
      url: "http://localhost:4000/c/shoes?type=running",
    };
    context.controller.receiveStorefront({
      type: "snapshot",
      snapshot: changed,
    });
    retry?.click();
    await Promise.resolve();
    expect(context.retries).toEqual([
      { sessionId: "session-paused", taskId: "task-paused", snapshot: changed },
    ]);
  });

  it.each([404, 410])(
    "starts a fresh session when saved session restore returns %i",
    async (status) => {
      const context = setup({
        savedSessionId: "session-expired",
        restoreError: new Error(`Session restore failed with ${status}`),
      });

      await context.controller.start();

      expect(context.snapshotRequests()).toBe(1);
      expect(context.root.querySelector("#task-status")?.textContent).toBe(
        "بانتظار اتصال المتجر…",
      );
      expect(
        context.root.querySelector("#conversation")?.textContent,
      ).toContain("بدأت جلسة جديدة");
      context.controller.receiveStorefront({ type: "snapshot", snapshot });
      expect(
        context.root.querySelector<HTMLInputElement>("#shopper-message")
          ?.disabled,
      ).toBe(false);
    },
  );

  it.each(["completed", "cancelled"])(
    "restores a %s task without locking Shopper input",
    async (status) => {
      const restoredState: SessionView = {
        session_id: "session-finished",
        lease: "owned",
        event_cursor: 6,
        conversation: [{ role: "copilot", text: "Finished earlier." }],
        requires_reconciliation: false,
        task: {
          task_id: "task-finished",
          status,
          pending_question: null,
        },
      };
      const context = setup({
        savedSessionId: "session-finished",
        restoredState,
      });

      await context.controller.start();
      context.controller.receiveStorefront({ type: "snapshot", snapshot });
      await Promise.resolve();
      await Promise.resolve();

      expect(
        context.root.querySelector<HTMLInputElement>("#shopper-message")
          ?.disabled,
      ).toBe(false);
      expect(context.root.querySelector("#pending-question")?.textContent).toBe(
        "",
      );
    },
  );

  it("keeps Stop available and disables speech when the browser lacks recognition", async () => {
    const context = setup();
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    expect(
      context.root.querySelector<HTMLButtonElement>("#stop-task")?.disabled,
    ).toBe(false);
    expect(
      context.root.querySelector<HTMLButtonElement>("#speech-input")?.disabled,
    ).toBe(true);
    context.root.querySelector<HTMLButtonElement>("#stop-task")?.click();
    expect(context.stopped).toEqual(["session-1"]);
  });

  it("transcribes selected Arabic or English speech into the editable input without submitting", async () => {
    const recognitions: Array<{
      lang: string;
      onresult:
        | ((event: {
            results: ArrayLike<ArrayLike<{ transcript: string }>>;
          }) => void)
        | null;
      onend: (() => void) | null;
      aborted: boolean;
    }> = [];
    class FakeSpeechRecognition {
      lang = "";
      onresult:
        | ((event: {
            results: ArrayLike<ArrayLike<{ transcript: string }>>;
          }) => void)
        | null = null;
      onerror: (() => void) | null = null;
      onend: (() => void) | null = null;
      aborted = false;
      constructor() {
        recognitions.push(this);
      }
      start() {
        /* browser mock */
      }
      abort() {
        this.aborted = true;
        this.onend?.();
      }
    }
    const context = setup({ speechRecognition: FakeSpeechRecognition });
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    context.root.querySelector<HTMLButtonElement>("#speech-input")?.click();
    expect(recognitions[0]?.lang).toBe("ar-EG");
    recognitions[0]?.onresult?.({
      results: [[{ transcript: "عايز كوتشي جري" }]],
    });
    expect(
      context.root.querySelector<HTMLInputElement>("#shopper-message")?.value,
    ).toBe("عايز كوتشي جري");
    expect(context.submitted).toEqual([]);
    context.root.querySelector<HTMLSelectElement>("#speech-language")!.value =
      "en-US";
    recognitions[0]?.onend?.();
    context.root.querySelector<HTMLButtonElement>("#speech-input")?.click();
    expect(recognitions[1]?.lang).toBe("en-US");
    context.root.querySelector<HTMLButtonElement>("#stop-task")?.click();
    expect(recognitions[1]?.aborted).toBe(true);
  });

  it("reports the browser's speech failure reason while preserving typed input", async () => {
    const recognitions: FakeSpeechRecognition[] = [];
    class FakeSpeechRecognition {
      lang = "";
      onresult = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;
      constructor() {
        recognitions.push(this);
      }
      start() {
        /* browser mock */
      }
      abort() {
        this.onend?.();
      }
    }
    const context = setup({ speechRecognition: FakeSpeechRecognition });
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    const input =
      context.root.querySelector<HTMLInputElement>("#shopper-message")!;
    input.value = "عايز كوتشي";
    context.root.querySelector<HTMLButtonElement>("#speech-input")?.click();
    recognitions[0]?.onerror?.({ error: "network" });
    expect(context.root.querySelector("#task-status")?.textContent).toBe(
      "خدمة التعرف على الصوت غير متاحة الآن. جرّب Chrome أو اكتب طلبك.",
    );
    expect(input.value).toBe("عايز كوتشي");
    recognitions[0]?.onend?.();
    context.root.querySelector<HTMLSelectElement>("#speech-language")!.value =
      "en-US";
    context.root.querySelector<HTMLButtonElement>("#speech-input")?.click();
    recognitions[1]?.onerror?.({ error: "not-allowed" });
    expect(context.root.querySelector("#task-status")?.textContent).toBe(
      "Microphone access was blocked. Check browser and system permissions, then retry.",
    );
  });

  it("uses an explicit short recording after browser speech network failure without submitting", async () => {
    const recognitions: FakeSpeechRecognition[] = [];
    class FakeSpeechRecognition {
      lang = "";
      onresult = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;
      constructor() {
        recognitions.push(this);
      }
      start() {
        /* browser mock */
      }
      abort() {
        this.onend?.();
      }
    }
    let trackStopped = false;
    const stream = {
      getTracks: () => [{ stop: () => (trackStopped = true) }],
    } as unknown as MediaStream;
    class FakeMediaRecorder {
      state: RecordingState = "inactive";
      ondataavailable: ((event: BlobEvent) => void) | null = null;
      onstop: (() => void) | null = null;
      start() {
        this.state = "recording";
      }
      stop() {
        this.state = "inactive";
        this.ondataavailable?.({
          data: new Blob([new Uint8Array([0x1a, 0x45, 0xdf, 0xa3, 1])]),
        } as BlobEvent);
        this.onstop?.();
      }
    }
    const context = setup({
      speechRecognition: FakeSpeechRecognition,
      mediaRecorder: FakeMediaRecorder as unknown as typeof MediaRecorder,
      getUserMedia: async () => stream,
    });
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    context.root.querySelector<HTMLButtonElement>("#speech-input")?.click();
    recognitions[0]?.onerror?.({ error: "network" });
    await Promise.resolve();
    const area = context.root.querySelector<HTMLElement>(
      "#speech-fallback-area",
    )!;
    expect(area.hidden).toBe(false);
    const button =
      context.root.querySelector<HTMLButtonElement>("#speech-fallback")!;
    button.click();
    await Promise.resolve();
    expect(button.getAttribute("aria-pressed")).toBe("true");
    button.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(trackStopped).toBe(true);
    expect(context.transcribed).toHaveLength(1);
    expect(context.transcribed[0]?.language).toBe("ar");
    expect(
      context.root.querySelector<HTMLInputElement>("#shopper-message")?.value,
    ).toBe("عايز كوتشي جري");
    expect(context.submitted).toEqual([]);
  });

  it("explains unavailable OpenRouter recording without requesting microphone access", async () => {
    const getUserMedia = vi.fn();
    class FailedSpeechRecognition {
      lang = "";
      onresult = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onend = null;
      start() {
        this.onerror?.({ error: "network" });
      }
      abort() {
        /* browser mock */
      }
    }
    const context = setup({
      speechRecognition: FailedSpeechRecognition,
      mediaRecorder: class {} as unknown as typeof MediaRecorder,
      getUserMedia,
      speechAvailable: false,
    });
    await context.controller.start();
    context.root.querySelector<HTMLButtonElement>("#speech-input")?.click();
    await Promise.resolve();
    expect(
      context.root.querySelector<HTMLElement>("#speech-fallback-area")?.hidden,
    ).toBe(true);
    expect(context.root.textContent).toContain(
      "التفريغ عبر OpenRouter غير متاح",
    );
    expect(getUserMedia).not.toHaveBeenCalled();
  });
});

describe("PanelController plan checklist", () => {
  const steps = [
    { position: 1, text: "ضيفلي الجزمة للعربية" },
    { position: 2, text: "افتح العربية" },
  ];

  async function ready() {
    const context = setup();
    await context.controller.start();
    context.controller.receiveStorefront({ type: "snapshot", snapshot });
    return context;
  }
  const marks = (root: HTMLElement) =>
    Array.from(root.querySelectorAll<HTMLElement>(".plan-step")).map(
      (item) => item.dataset.mark,
    );
  const inputDisabled = (root: HTMLElement) =>
    root.querySelector<HTMLInputElement>("#shopper-message")!.disabled;
  const created = (
    language: "ar" | "en" = "ar",
    skipped: string[] = [],
  ): AgentEvent => ({
    type: "plan_created",
    data: { plan_id: "plan-1", language, steps, skipped },
  });
  const started = (position: number, taskId: string): AgentEvent => ({
    type: "plan_step_started",
    data: { plan_id: "plan-1", position, task_id: taskId },
  });
  const finishStep = (
    position: number,
    outcome: "done" | "failed" | "skipped",
  ): AgentEvent => ({
    type: "plan_step_finished",
    data: { plan_id: "plan-1", position, outcome },
  });
  const finished = (
    outcome: "done" | "failed" | "cancelled",
    report = "Report",
  ): AgentEvent => ({
    type: "plan_finished",
    data: { plan_id: "plan-1", outcome, report },
  });

  it("ticks marks live and keeps the input disabled until the plan finishes", async () => {
    const { root, emit } = await ready();
    expect(inputDisabled(root)).toBe(false);
    emit({ type: "task_started", data: { task_id: "task-1" } });
    emit(created());
    expect(root.querySelectorAll("#plan-checklist")).toHaveLength(1);
    expect(root.querySelector<HTMLElement>("#plan-checklist")!.hidden).toBe(
      false,
    );
    expect(root.querySelector("#plan-checklist")!.getAttribute("dir")).toBe(
      "rtl",
    );
    expect(root.querySelector(".plan-heading")!.textContent).toBe("الخطوات");
    expect(marks(root)).toEqual(["pending", "pending"]);
    expect(inputDisabled(root)).toBe(true);

    emit(started(1, "task-1"));
    expect(marks(root)).toEqual(["running", "pending"]);
    emit({ type: "done", data: { summary: "تمت", language: "ar" } });
    emit(finishStep(1, "done"));
    expect(marks(root)).toEqual(["done", "pending"]);
    // The gap between step 1's done and step 2's task_started.
    expect(inputDisabled(root)).toBe(true);
    emit({ type: "task_started", data: { task_id: "task-2" } });
    emit(started(2, "task-2"));
    expect(marks(root)).toEqual(["done", "running"]);
    emit({ type: "done", data: { summary: "تمت", language: "ar" } });
    emit(finishStep(2, "done"));
    expect(inputDisabled(root)).toBe(true);
    emit(finished("done"));
    expect(marks(root)).toEqual(["done", "done"]);
    expect(inputDisabled(root)).toBe(false);
    expect(root.querySelectorAll("#plan-checklist")).toHaveLength(1);
    expect(root.querySelectorAll(".plan-steps")).toHaveLength(1);
  });

  it("labels the checklist in English and shows text-based state, not colour only", async () => {
    const { root, emit } = await ready();
    emit(created("en"));
    emit(started(1, "task-1"));
    const container = root.querySelector("#plan-checklist")!;
    expect(container.getAttribute("dir")).toBe("ltr");
    expect(container.querySelector(".plan-heading")!.textContent).toBe("Steps");
    const states = Array.from(container.querySelectorAll(".plan-state")).map(
      (node) => node.textContent,
    );
    expect(states).toEqual(["In progress", "Waiting"]);
  });

  it("renders step text as text, never HTML", async () => {
    const { root, emit } = await ready();
    emit({
      type: "plan_created",
      data: {
        plan_id: "plan-1",
        language: "en",
        steps: [
          { position: 1, text: "<img src=x onerror=alert(1)>" },
          { position: 2, text: "open the cart" },
        ],
        skipped: ["<b>later</b>"],
      },
    });
    expect(root.querySelector("#plan-checklist img")).toBeNull();
    expect(root.querySelector("#plan-checklist b")).toBeNull();
    expect(root.querySelector(".plan-text")!.textContent).toBe(
      "<img src=x onerror=alert(1)>",
    );
  });

  it("shows a failed step 1 and a skipped step 2, then frees the input", async () => {
    const { root, emit } = await ready();
    emit({ type: "task_started", data: { task_id: "task-1" } });
    emit(created());
    emit(started(1, "task-1"));
    emit({ type: "cancelled", data: {} });
    emit(finishStep(1, "failed"));
    emit(finishStep(2, "skipped"));
    expect(marks(root)).toEqual(["failed", "skipped"]);
    expect(inputDisabled(root)).toBe(true);
    emit(finished("failed"));
    expect(inputDisabled(root)).toBe(false);
  });

  const paused = (
    position: number,
    reason: "question" | "confirmation",
  ): AgentEvent => ({
    type: "plan_paused",
    data: { plan_id: "plan-1", position, reason },
  });
  const resumed = (position: number): AgentEvent => ({
    type: "plan_resumed",
    data: { plan_id: "plan-1", position },
  });

  it("shows the running step as waiting for the Shopper, then running again", async () => {
    const { root, emit } = await ready();
    emit({ type: "task_started", data: { task_id: "task-1" } });
    emit(created());
    emit(started(1, "task-1"));
    emit(finishStep(1, "done"));
    emit({ type: "task_started", data: { task_id: "task-2" } });
    emit(started(2, "task-2"));
    emit(paused(2, "question"));
    expect(marksWithWords(root)).toEqual([
      ["done", "تمّت"],
      ["paused", "مستني ردك"],
    ]);
    expect(
      root.querySelectorAll(".plan-step")[1]!.querySelector(".plan-mark")!
        .textContent,
    ).toBe("◷");
    expect(inputDisabled(root)).toBe(true);
    emit(resumed(2));
    expect(marks(root)).toEqual(["done", "running"]);
    emit(paused(2, "confirmation"));
    expect(marks(root)).toEqual(["done", "paused"]);
  });

  it("labels the paused step in English", async () => {
    const { root, emit } = await ready();
    emit(created("en"));
    emit(started(1, "task-1"));
    emit(paused(1, "question"));
    expect(marksWithWords(root)[0]).toEqual(["paused", "Waiting for you"]);
  });

  it("still renders the Confirmation card while the plan shows a paused step", async () => {
    const { root, emit } = await ready();
    emit({ type: "task_started", data: { task_id: "task-2" } });
    emit(created());
    emit(started(2, "task-2"));
    emit({
      type: "action",
      data: {
        action: {
          v: 1,
          type: "ask_shopper",
          kind: "confirmation",
          task_id: "task-2",
          action_id: "confirmation-1234567890abcdef1234567890abcdef",
          sequence_number: 2,
          narration: "Confirm this action.",
          question: "Confirm this action: empty the cart. Continue?",
          options: ["Confirm", "Stop"],
        },
      },
    });
    emit(paused(2, "confirmation"));
    expect(marks(root)).toEqual(["pending", "paused"]);
    const card = root.querySelector<HTMLElement>(
      "#pending-question .confirmation-card",
    );
    expect(card?.textContent).toContain("empty the cart");
    expect(root.querySelectorAll(".plan-steps")).toHaveLength(1);
  });

  it("ignores paused and resumed for an unknown plan", async () => {
    const { root, emit } = await ready();
    emit(created());
    emit(started(1, "task-1"));
    emit({
      type: "plan_paused",
      data: { plan_id: "other", position: 1, reason: "question" },
    });
    expect(marks(root)).toEqual(["running", "pending"]);
  });

  it("ignores step events for an unknown plan", async () => {
    const { root, emit } = await ready();
    emit(created());
    emit({
      type: "plan_step_started",
      data: { plan_id: "other", position: 1, task_id: "task-1" },
    });
    emit({
      type: "plan_finished",
      data: { plan_id: "other", outcome: "done", report: "Other" },
    });
    expect(marks(root)).toEqual(["pending", "pending"]);
    expect(inputDisabled(root)).toBe(true);
  });

  it("shows no checklist for a one-step task and behaves as today", async () => {
    const { root, emit } = await ready();
    emit({ type: "task_started", data: { task_id: "task-1" } });
    expect(root.querySelector<HTMLElement>("#plan-checklist")!.hidden).toBe(
      true,
    );
    expect(root.querySelectorAll(".plan-step")).toHaveLength(0);
    expect(inputDisabled(root)).toBe(true);
    emit({ type: "done", data: { summary: "Done", language: "en" } });
    expect(inputDisabled(root)).toBe(false);
    expect(root.querySelectorAll(".plan-step")).toHaveLength(0);
  });

  const conversationTexts = (root: HTMLElement) =>
    Array.from(root.querySelectorAll("#conversation li")).map(
      (item) => item.textContent,
    );
  const statusText = (root: HTMLElement) =>
    root.querySelector("#task-status")!.textContent;
  const marksWithWords = (root: HTMLElement) =>
    Array.from(root.querySelectorAll(".plan-step")).map((item) => [
      (item as HTMLElement).dataset.mark,
      item.querySelector(".plan-state")!.textContent,
    ]);

  it("marks a failed step, the skipped ones after it, and shows the report", async () => {
    const { root, emit } = await ready();
    const report =
      "وقفت عند خطوة ماتمّتش:\n✓ ضيفلي الجزمة للعربية\n✕ افتح العربية — تعذر فتح الصفحة المطلوبة. حاول تاني.";
    emit({ type: "task_started", data: { task_id: "task-1" } });
    emit(created());
    emit(started(1, "task-1"));
    emit(finishStep(1, "done"));
    emit({ type: "task_started", data: { task_id: "task-2" } });
    emit(started(2, "task-2"));
    emit({ type: "error", data: { message: "تعذر فتح الصفحة المطلوبة." } });
    emit(finishStep(2, "failed"));
    emit({ type: "cancelled", data: {} });
    expect(marks(root)).toEqual(["done", "failed"]);
    expect(inputDisabled(root)).toBe(true);
    // The step's own Retry is gone once its task is cancelled.
    expect(root.querySelector("#retry-task")).toBeNull();
    emit(finished("failed", report));
    expect(marksWithWords(root)).toEqual([
      ["done", "تمّت"],
      ["failed", "لم تنجح"],
    ]);
    expect(conversationTexts(root).at(-1)).toBe(report);
    expect(statusText(root)).toBe("وقفت عند خطوة ماتمّتش:");
    expect(inputDisabled(root)).toBe(false);
  });

  it("marks steps skipped when the plan is cancelled and says so in the report", async () => {
    const { root, emit } = await ready();
    const report =
      "I stopped your request as you asked:\n– Add the shoes (cancelled)\n– Open the cart (cancelled)";
    emit({ type: "task_started", data: { task_id: "task-1" } });
    emit(created("en"));
    emit(started(1, "task-1"));
    emit({ type: "cancelled", data: {} });
    emit(finishStep(1, "skipped"));
    emit(finishStep(2, "skipped"));
    expect(inputDisabled(root)).toBe(true);
    emit(finished("cancelled", report));
    expect(marksWithWords(root)).toEqual([
      ["skipped", "Skipped"],
      ["skipped", "Skipped"],
    ]);
    expect(conversationTexts(root).at(-1)).toBe(report);
    expect(statusText(root)).toBe("I stopped your request as you asked:");
    expect(inputDisabled(root)).toBe(false);
  });

  it("appends the report of a plan that finished done as a copilot message", async () => {
    const { root, emit } = await ready();
    emit(created());
    emit(finished("done", "خلصت طلبك:\n✓ أ\n✓ ب"));
    expect(statusText(root)).toBe("خلصت طلبك:");
    expect(
      root.querySelector("#conversation li:last-child")!.className,
    ).toContain("message-copilot");
  });

  it("shows a step skipped by its own condition with its reason, and the plan done", async () => {
    const { root, emit } = await ready();
    const reason = "ما ضفتهاش: سعرها 1200 جنيه، والشرط مش متحقق.";
    const report = `خلصت طلبك:
✓ ضيفلي الجزمة
– ضيفها لو أقل من 1000 — ${reason}`;
    emit({ type: "task_started", data: { task_id: "task-1" } });
    emit(created());
    emit(started(1, "task-1"));
    emit(finishStep(1, "done"));
    emit({ type: "task_started", data: { task_id: "task-2" } });
    emit(started(2, "task-2"));
    emit({ type: "done", data: { summary: reason, language: "ar" } });
    emit(finishStep(2, "skipped"));
    expect(marksWithWords(root)).toEqual([
      ["done", "تمّت"],
      ["skipped", "تم تخطّيها"],
    ]);
    expect(conversationTexts(root).at(-1)).toBe(reason);
    expect(inputDisabled(root)).toBe(true);
    emit(finished("done", report));
    expect(conversationTexts(root).at(-1)).toBe(report);
    expect(statusText(root)).toBe("خلصت طلبك:");
    expect(marks(root)).toEqual(["done", "skipped"]);
    expect(inputDisabled(root)).toBe(false);
  });

  it("announces requests beyond the limit under the checklist, in the Shopper's language", async () => {
    const { root, emit } = await ready();
    emit(created("ar", ["افتح الطلبات", "افتح المساعدة"]));
    expect(root.querySelector(".plan-skipped-note")!.textContent).toBe(
      "مش هعمل دول دلوقتي (الحد ٣ طلبات): افتح الطلبات، افتح المساعدة",
    );
    emit(created("en", ["show orders", "open help"]));
    expect(root.querySelector(".plan-skipped-note")!.textContent).toBe(
      "Not doing these now (limit is 3 requests): show orders, open help",
    );
    emit(created("en"));
    expect(root.querySelector(".plan-skipped-note")).toBeNull();
  });

  describe("after a reload", () => {
    const restoredWith = (
      plan: SessionView["plan"],
      task: SessionView["task"],
    ): SessionView => ({
      session_id: "session-restored",
      lease: "owned",
      event_cursor: 9,
      conversation: [
        { role: "shopper", text: "ضيفلي الجزمة وبعدين افتح العربية" },
      ],
      requires_reconciliation: false,
      plan,
      task,
    });

    async function reload(restoredState: SessionView) {
      const context = setup({
        savedSessionId: "session-restored",
        restoredState,
      });
      await context.controller.start();
      context.controller.receiveStorefront({ type: "snapshot", snapshot });
      await Promise.resolve();
      await Promise.resolve();
      return context;
    }

    it("rebuilds an active checklist from the Session and keeps the input disabled", async () => {
      const { root } = await reload(
        restoredWith(
          {
            plan_id: "plan-1",
            language: "ar",
            active: true,
            steps: [
              { position: 1, text: "ضيفلي الجزمة للعربية", status: "done" },
              { position: 2, text: "افتح العربية", status: "running" },
              { position: 3, text: "افتح الحساب", status: "pending" },
            ],
            skipped: ["افتح الطلبات"],
          },
          {
            task_id: "task-2",
            status: "awaiting_action_result",
            pending_question: null,
          },
        ),
      );
      // Steps that never ran are never shown as done.
      expect(marks(root)).toEqual(["done", "running", "pending"]);
      expect(root.querySelector<HTMLElement>("#plan-checklist")!.hidden).toBe(
        false,
      );
      expect(root.querySelector(".plan-skipped-note")!.textContent).toBe(
        "مش هعمل دول دلوقتي (الحد ٣ طلبات): افتح الطلبات",
      );
      expect(inputDisabled(root)).toBe(true);
    });

    it("restores a paused step from the Session", async () => {
      const { root } = await reload(
        restoredWith(
          {
            plan_id: "plan-1",
            language: "ar",
            active: true,
            paused: "confirmation",
            steps: [
              { position: 1, text: "ضيفلي الجزمة للعربية", status: "done" },
              { position: 2, text: "امسح العربية", status: "running" },
            ],
            skipped: [],
          },
          {
            task_id: "task-2",
            status: "awaiting_answer",
            pending_question: null,
          },
        ),
      );
      expect(marksWithWords(root)).toEqual([
        ["done", "تمّت"],
        ["paused", "مستني ردك"],
      ]);
      expect(inputDisabled(root)).toBe(true);
    });

    it("rebuilds a finished checklist from the Session and enables the input", async () => {
      const { root } = await reload(
        restoredWith(
          {
            plan_id: "plan-1",
            language: "en",
            active: false,
            steps: [
              { position: 1, text: "Add the shoes", status: "done" },
              { position: 2, text: "Open the cart", status: "failed" },
              { position: 3, text: "Open the account", status: "skipped" },
            ],
            skipped: [],
          },
          { task_id: "task-2", status: "cancelled", pending_question: null },
        ),
      );
      expect(marksWithWords(root)).toEqual([
        ["done", "Done"],
        ["failed", "Failed"],
        ["skipped", "Skipped"],
      ]);
      expect(inputDisabled(root)).toBe(false);
    });

    it("shows no checklist when the Session has no plan", async () => {
      const { root } = await reload(restoredWith(null, null));
      expect(root.querySelector<HTMLElement>("#plan-checklist")!.hidden).toBe(
        true,
      );
      expect(inputDisabled(root)).toBe(false);
    });
  });

  it("clears a finished checklist when the Shopper sends the next message", async () => {
    const { root, emit } = await ready();
    emit(created());
    emit(finished("cancelled"));
    root.querySelector<HTMLInputElement>("#shopper-message")!.value = "hi";
    root.querySelector<HTMLButtonElement>(".input-row button")!.click();
    expect(root.querySelector<HTMLElement>("#plan-checklist")!.hidden).toBe(
      true,
    );
  });
});
