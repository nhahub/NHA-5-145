import { expect, it } from "vitest";
import { subscribeAgentStream } from "../src/event-stream.js";

it("reconnects transient failures but closes terminal authorization failures", () => {
  const listeners = new Map<
    string,
    ((event: MessageEvent<string>) => void)[]
  >();
  let closes = 0,
    resets = 0;
  const delivered: unknown[] = [];
  const source = {
    readyState: 0,
    addEventListener: (
      name: string,
      listener: (event: MessageEvent<string>) => void,
    ) => {
      listeners.set(name, [...(listeners.get(name) ?? []), listener]);
    },
    close: () => {
      closes++;
    },
  };
  subscribeAgentStream(
    "/events",
    (event) => delivered.push(event),
    0,
    undefined,
    () => source,
    () => {
      resets++;
    },
  );
  for (const listener of listeners.get("error")!)
    listener(new MessageEvent("error"));
  expect(closes).toBe(0);
  expect(resets).toBe(0);
  source.readyState = 1;
  for (const listener of listeners.get("error")!)
    listener(
      new MessageEvent("error", {
        lastEventId: "1",
        data: JSON.stringify({ message: "Task could not complete" }),
      }),
    );
  expect(delivered).toEqual([
    { type: "error", data: { message: "Task could not complete" } },
  ]);
  expect(resets).toBe(0);
  source.readyState = 2;
  for (const listener of listeners.get("error")!)
    listener(new MessageEvent("error"));
  expect(closes).toBe(1);
  expect(resets).toBe(1);
});

it("closes a revoked stream without reconnecting or delivering queued actions", () => {
  const listeners = new Map<string, (event: MessageEvent<string>) => void>();
  let closed = false,
    resets = 0;
  const events: unknown[] = [];
  subscribeAgentStream(
    "/events",
    (e) => events.push(e),
    0,
    undefined,
    () => ({
      addEventListener: (name, listener) => {
        listeners.set(name, listener);
      },
      close: () => {
        closed = true;
      },
    }),
    () => {
      resets++;
    },
  );
  listeners.get("shopper_reset")!(new MessageEvent("shopper_reset"));
  listeners.get("narration")!(
    new MessageEvent("narration", {
      lastEventId: "1",
      data: JSON.stringify({ text: "late" }),
    }),
  );
  expect(closed).toBe(true);
  expect(resets).toBe(1);
  expect(events).toEqual([]);
});

it("resumes after the cursor and does not repeat messages on reconnect", () => {
  const listeners = new Map<string, (event: MessageEvent<string>) => void>();
  const delivered: unknown[] = [];
  const cursors: number[] = [];
  let closed = false;
  const close = subscribeAgentStream(
    "/events?after=3",
    (e) => delivered.push(e),
    3,
    (c) => cursors.push(c),
    () => ({
      addEventListener: (name, listener) => {
        listeners.set(name, listener);
      },
      close: () => {
        closed = true;
      },
    }),
  );
  for (const id of ["3", "4", "4", "2", "5"])
    listeners.get("narration")!(
      new MessageEvent("narration", {
        lastEventId: id,
        data: JSON.stringify({ text: "Working" }),
      }),
    );
  expect(delivered).toHaveLength(2);
  expect(cursors).toEqual([4, 5]);
  close();
  expect(closed).toBe(true);
});
