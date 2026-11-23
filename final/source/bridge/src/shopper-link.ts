/** Fixed-origin infrastructure linking; credentials never enter the semantic snapshot. */
export function installShopperLink(host: Window, panelOrigin: string): void {
  const pending = new Map<string, Promise<string>>();
  host.addEventListener("message", (event) => {
    if (
      event.source !== host.parent ||
      event.origin !== panelOrigin ||
      event.data?.type !== "shopper_link_request" ||
      event.data.audience !== panelOrigin ||
      typeof event.data.challenge !== "string" ||
      !/^[a-f0-9]{64}$/.test(event.data.challenge)
    )
      return;
    const challenge: string = event.data.challenge;
    if (!pending.has(challenge)) {
      if (pending.size >= 4) return;
      const issue = async () => {
        const bootstrap = await host.fetch("/__shopper", { cache: "no-store" });
        if (!bootstrap.ok) throw new Error("Storefront identity unavailable");
        const { csrf } = (await bootstrap.json()) as { csrf: string };
        const response = await host.fetch("/__copilot/link-ticket", {
          method: "POST",
          headers: { "content-type": "application/json", "x-csrf-token": csrf },
          body: JSON.stringify({ challenge, audience: panelOrigin }),
        });
        if (!response.ok) throw new Error("Storefront ticket unavailable");
        return ((await response.json()) as { ticket: string }).ticket;
      };
      pending.set(challenge, issue());
      host.setTimeout(() => pending.delete(challenge), 60000);
    }
    void pending.get(challenge)!.then(
      (ticket) =>
        host.parent.postMessage(
          { type: "shopper_link_result", challenge, ticket },
          panelOrigin,
        ),
      () =>
        host.parent.postMessage(
          { type: "shopper_link_result", challenge, error: true },
          panelOrigin,
        ),
    );
  });
}
