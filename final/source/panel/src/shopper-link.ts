/** Infrastructure ticket exchange; never part of a Snapshot or conversation. */
export function requestShopperTicket(
  frame: HTMLIFrameElement,
  origin: string,
  challenge: string,
  host: Window = window,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const send = () =>
      frame.contentWindow?.postMessage(
        {
          type: "shopper_link_request",
          challenge,
          audience: host.location.origin,
        },
        origin,
      );
    const cleanup = () => {
      host.clearTimeout(timeout);
      host.removeEventListener("message", receive);
      frame.removeEventListener("load", send);
    };
    const receive = (event: MessageEvent) => {
      if (
        event.origin !== origin ||
        event.source !== frame.contentWindow ||
        event.data?.type !== "shopper_link_result" ||
        event.data.challenge !== challenge
      )
        return;
      cleanup();
      if (
        typeof event.data.ticket === "string" &&
        /^[a-f0-9]{64}$/.test(event.data.ticket)
      )
        resolve(event.data.ticket);
      else reject(new Error("Storefront identity unavailable"));
    };
    const timeout = host.setTimeout(() => {
      cleanup();
      reject(new Error("Storefront link timed out"));
    }, 8000);
    host.addEventListener("message", receive);
    frame.addEventListener("load", send);
    send();
  });
}

export async function linkShopper(
  frame: HTMLIFrameElement,
  agent: string,
  store: string,
): Promise<{ csrf: string; context: string }> {
  const bootstrap = await fetch(agent + "/shopper/bootstrap", {
    method: "POST",
    credentials: "include",
    signal: AbortSignal.timeout(5000),
  });
  if (!bootstrap.ok) throw new Error("Shopper identity unavailable");
  const { csrf } = (await bootstrap.json()) as { csrf: string };
  const headers = { "content-type": "application/json", "x-csrf-token": csrf };
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const challengeResponse = await fetch(agent + "/shopper/challenge", {
        method: "POST",
        credentials: "include",
        headers,
        signal: AbortSignal.timeout(5000),
      });
      if (!challengeResponse.ok) throw new Error("Shopper linking unavailable");
      const { challenge } = (await challengeResponse.json()) as {
        challenge: string;
      };
      const ticket = await requestShopperTicket(frame, store, challenge);
      const result = await fetch(agent + "/shopper/link", {
        method: "POST",
        credentials: "include",
        headers,
        body: JSON.stringify({ ticket, challenge }),
        signal: AbortSignal.timeout(5000),
      });
      if (!result.ok) throw new Error("Shopper link changed or expired");
      const linked = (await result.json()) as { shopper_context?: unknown };
      if (
        typeof linked.shopper_context !== "string" ||
        !/^[a-f0-9]{64}$/.test(linked.shopper_context)
      )
        throw new Error("Invalid shopper context");
      return { csrf, context: linked.shopper_context };
    } catch (error) {
      // A fresh one-use challenge can recover a lost redemption response.
      // This exchange never submits a shopping request or replays an Action.
      if (attempt === 1) throw error;
    }
  }
  throw new Error("Shopper linking unavailable");
}
