import { JSDOM } from "jsdom";
import { expect, it, vi } from "vitest";
import { linkShopper, requestShopperTicket } from "../src/shopper-link.js";

it("accepts only the correlated ticket from the exact Storefront frame and origin", async () => {
  const dom = new JSDOM("<iframe></iframe>", { url: "http://localhost:4100" });
  const frame = dom.window.document.querySelector("iframe")!;
  vi.spyOn(frame.contentWindow!, "postMessage").mockImplementation(() => {});
  const pending = requestShopperTicket(
    frame,
    "http://localhost:4000",
    "challenge",
    dom.window as unknown as Window,
  );
  const send = (origin: string, source: Window | null, challenge: string) =>
    dom.window.dispatchEvent(
      new dom.window.MessageEvent("message", {
        origin,
        source,
        data: {
          type: "shopper_link_result",
          challenge,
          ticket: "a".repeat(64),
        },
      }),
    );
  send("https://hostile.example", frame.contentWindow, "challenge");
  send("http://localhost:4000", null, "challenge");
  send("http://localhost:4000", frame.contentWindow, "wrong");
  send("http://localhost:4000", frame.contentWindow, "challenge");
  expect(await pending).toBe("a".repeat(64));
  dom.window.close();
});

it("recovers a lost redemption response using a fresh challenge without replaying shopping", async () => {
  const dom = new JSDOM("<iframe></iframe>", { url: "http://localhost:4100" });
  const frame = dom.window.document.querySelector("iframe")!;
  const attempts: string[] = [];
  let challengeNumber = 0;
  vi.stubGlobal("window", dom.window);
  vi.spyOn(frame.contentWindow!, "postMessage").mockImplementation(
    (message) => {
      queueMicrotask(() =>
        dom.window.dispatchEvent(
          new dom.window.MessageEvent("message", {
            origin: "http://localhost:4000",
            source: frame.contentWindow,
            data: {
              type: "shopper_link_result",
              challenge: message.challenge,
              ticket: "c".repeat(64),
            },
          }),
        ),
      );
    },
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options: RequestInit) => {
      if (url.endsWith("/shopper/bootstrap"))
        return Response.json({ csrf: "fixture-csrf" });
      if (url.endsWith("/shopper/challenge"))
        return Response.json({
          challenge: String(++challengeNumber).repeat(64),
        });
      if (url.endsWith("/shopper/link")) {
        attempts.push(JSON.parse(options.body as string).challenge);
        if (attempts.length === 1)
          throw new TypeError("response lost after redemption");
        return Response.json({ linked: true, shopper_context: "d".repeat(64) });
      }
      throw new Error("Unexpected shopping request during linking");
    }),
  );
  try {
    expect(
      await linkShopper(
        frame,
        "http://localhost:8000",
        "http://localhost:4000",
      ),
    ).toEqual({
      csrf: "fixture-csrf",
      context: "d".repeat(64),
    });
    expect(attempts).toEqual(["1".repeat(64), "2".repeat(64)]);
  } finally {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    dom.window.close();
  }
});
