import { describe, expect, it } from "vitest";

import { AGENT_EVENT_TYPES, parseAgentEvent } from "../src/panel.js";

describe("Agent event contract", () => {
  it("accepts a valid typed Action event", () => {
    const action = {
      v: 1,
      type: "navigate",
      task_id: "task-1",
      action_id: "action-1",
      sequence_number: 1,
      narration: "Applying filters.",
      url: "/c/shoes?type=running&max_price=2000",
    };

    expect(parseAgentEvent("action", { action })).toEqual({
      type: "action",
      data: { action },
    });
  });

  it("rejects unknown events and malformed payloads", () => {
    expect(() => parseAgentEvent("unexpected", {})).toThrow(/supported/);
    expect(() => parseAgentEvent("narration", {})).toThrow(/text/);
    expect(() =>
      parseAgentEvent("done", { summary: "Done", language: "fr" }),
    ).toThrow(/language/);
  });

  it("publishes the event names used by the EventSource subscription", () => {
    expect(AGENT_EVENT_TYPES).toEqual([
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
    ]);
  });

  describe("plan events", () => {
    const steps = [
      { position: 1, text: "add the shoes" },
      { position: 2, text: "open the cart" },
    ];

    it("accepts the four plan events", () => {
      expect(
        parseAgentEvent("plan_created", {
          plan_id: "p1",
          language: "en",
          steps,
          skipped: ["show orders"],
        }),
      ).toEqual({
        type: "plan_created",
        data: {
          plan_id: "p1",
          language: "en",
          steps,
          skipped: ["show orders"],
        },
      });
      expect(
        parseAgentEvent("plan_step_started", {
          plan_id: "p1",
          position: 2,
          task_id: "task-2",
        }).type,
      ).toBe("plan_step_started");
      for (const outcome of ["done", "failed", "skipped"])
        expect(
          parseAgentEvent("plan_step_finished", {
            plan_id: "p1",
            position: 1,
            outcome,
          }).data,
        ).toEqual({ plan_id: "p1", position: 1, outcome });
      for (const outcome of ["done", "failed", "cancelled"])
        expect(
          parseAgentEvent("plan_finished", {
            plan_id: "p1",
            outcome,
            report: "Report",
          }).data,
        ).toEqual({ plan_id: "p1", outcome, report: "Report" });
    });

    it("accepts the paused and resumed plan events", () => {
      for (const reason of ["question", "confirmation"]) {
        expect(
          parseAgentEvent("plan_paused", {
            plan_id: "p1",
            position: 2,
            reason,
          }).data,
        ).toEqual({ plan_id: "p1", position: 2, reason });
      }
      expect(
        parseAgentEvent("plan_resumed", { plan_id: "p1", position: 2 }).data,
      ).toEqual({ plan_id: "p1", position: 2 });
    });

    it("rejects malformed paused and resumed events", () => {
      const bad: Array<[string, unknown]> = [
        ["plan_paused", { plan_id: "p1", position: 1, reason: "other" }],
        ["plan_paused", { plan_id: "p1", position: 1 }],
        ["plan_paused", { plan_id: "p1", position: 0, reason: "question" }],
        ["plan_paused", { position: 1, reason: "question" }],
        ["plan_resumed", { plan_id: "p1", position: 4 }],
        ["plan_resumed", { plan_id: "", position: 1 }],
        ["plan_resumed", { plan_id: "p1" }],
      ];
      for (const [type, payload] of bad)
        expect(() => parseAgentEvent(type, payload)).toThrow(TypeError);
    });

    it("rejects malformed plan events", () => {
      const created = (extra: Record<string, unknown>) => ({
        plan_id: "p1",
        language: "ar",
        steps,
        skipped: [],
        ...extra,
      });
      const bad: Array<[string, unknown]> = [
        ["plan_created", created({ language: "fr" })],
        ["plan_created", created({ steps: [] })],
        ["plan_created", created({ steps: [steps[0]] })],
        ["plan_created", created({ steps: [...steps, ...steps] })],
        [
          "plan_created",
          created({ steps: [steps[0], { position: 2, text: 5 }] }),
        ],
        [
          "plan_created",
          created({ steps: [steps[0], { position: 1.5, text: "x" }] }),
        ],
        [
          "plan_created",
          created({ steps: [steps[0], { position: 3, text: "x" }] }),
        ],
        ["plan_created", { language: "ar", steps, skipped: [] }],
        ["plan_created", created({ skipped: undefined })],
        ["plan_created", created({ skipped: "none" })],
        ["plan_created", created({ skipped: [1] })],
        [
          "plan_created",
          created({ skipped: ["a", "b", "c", "d", "e", "f", "g"] }),
        ],
        ["plan_created", created({ plan_id: "" })],
        ["plan_step_started", { plan_id: "p1", position: 0, task_id: "t" }],
        ["plan_step_started", { plan_id: "p1", position: 1.5, task_id: "t" }],
        ["plan_step_started", { plan_id: "p1", position: 4, task_id: "t" }],
        ["plan_step_started", { plan_id: "p1", position: "1", task_id: "t" }],
        ["plan_step_started", { plan_id: "p1", position: 1 }],
        ["plan_step_started", { position: 1, task_id: "t" }],
        ["plan_step_finished", { plan_id: "p1", position: 1, outcome: "ok" }],
        [
          "plan_step_finished",
          { plan_id: "p1", position: 1, outcome: "cancelled" },
        ],
        ["plan_finished", { plan_id: "p1", outcome: "skipped", report: "r" }],
        ["plan_finished", { plan_id: 7, outcome: "done", report: "r" }],
        ["plan_finished", { plan_id: "p1", report: "r" }],
        ["plan_finished", { plan_id: "p1", outcome: "done" }],
        ["plan_finished", { plan_id: "p1", outcome: "done", report: 5 }],
      ];
      for (const [type, payload] of bad)
        expect(() => parseAgentEvent(type, payload)).toThrow(TypeError);
    });
  });
});
