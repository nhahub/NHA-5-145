import { Router } from "express";
import { randomUUID } from "node:crypto";
import {
  credentialDigest,
  opaqueToken,
  type ShopperBinding,
  ShopperRegistry,
} from "./shopper-state.js";
import { equalSecret, shopper } from "./shopper-http.js";

interface Ticket {
  binding: ShopperBinding;
  challenge: string;
  audience: string;
  expires: number;
}
export class LinkTickets {
  readonly #records = new Map<string, Ticket>();
  constructor(private readonly clock: () => number = Date.now) {}
  #expire(): void {
    for (const [key, value] of this.#records)
      if (value.expires <= this.clock()) this.#records.delete(key);
  }
  issue(
    binding: ShopperBinding,
    challenge: string,
    audience: string,
  ): string | undefined {
    this.#expire();
    if (
      this.#records.size >= 400 ||
      [...this.#records.values()].filter(
        (t) => t.binding.shopper_id === binding.shopper_id,
      ).length >= 4
    )
      return undefined;
    const ticket = opaqueToken();
    this.#records.set(credentialDigest(ticket), {
      binding,
      challenge,
      audience,
      expires: this.clock() + 60000,
    });
    return ticket;
  }
  redeem(
    ticket: string,
    challenge: string,
    audience: string,
  ): ShopperBinding | undefined {
    this.#expire();
    const key = credentialDigest(ticket);
    const record = this.#records.get(key);
    if (
      !record ||
      record.challenge !== challenge ||
      record.audience !== audience
    )
      return undefined;
    this.#records.delete(key);
    return record.binding;
  }
}
export function privateShopperRoutes(
  registry: ShopperRegistry,
  tickets: LinkTickets,
  secret: string,
  audience: string,
) {
  const router = Router();
  router.use((request, response, next) => {
    response.set("Cache-Control", "no-store");
    if (!equalSecret(request.headers["x-service-secret"], secret)) {
      response.sendStatus(403);
      return;
    }
    next();
  });
  router.post("/link/redeem", async (request, response) => {
    const {
      ticket,
      challenge,
      audience: requestedAudience,
    } = request.body ?? {};
    if (
      typeof ticket !== "string" ||
      typeof challenge !== "string" ||
      requestedAudience !== audience
    ) {
      response.sendStatus(409);
      return;
    }
    const binding = tickets.redeem(ticket, challenge, audience);
    if (!binding || !(await registry.lookup(binding))) {
      response.sendStatus(409);
      return;
    }
    response.json(binding);
  });
  router.post("/shopper/validate", async (request, response) => {
    const state = await registry.lookup(request.body ?? {});
    if (!state) {
      response.sendStatus(410);
      return;
    }
    response.json({ valid: true });
  });
  router.post("/confirmations", async (request, response) => {
    const state = await registry.lookup(request.body?.shopper ?? {});
    if (!state) {
      response.sendStatus(410);
      return;
    }
    if (!state.cart.register(request.body?.confirmation ?? {})) {
      response.sendStatus(409);
      return;
    }
    // Registering may first notice a changed product and bump the cart revision.
    if ((await registry.save(state)) !== "saved") {
      response.sendStatus(409);
      return;
    }
    response.status(201).json({ status: "registered" });
  });
  return router;
}
export function browserLinkRoutes(tickets: LinkTickets, audience: string) {
  const router = Router();
  router.post("/link-ticket", (request, response) => {
    const challenge = request.body?.challenge;
    if (
      typeof challenge !== "string" ||
      !/^[a-f0-9]{64}$/.test(challenge) ||
      request.body?.audience !== audience
    ) {
      response.sendStatus(400);
      return;
    }
    const ticket = tickets.issue(
      shopper(response).binding,
      challenge,
      audience,
    );
    if (!ticket) {
      response.sendStatus(429);
      return;
    }
    response.status(201).json({ ticket });
  });
  router.post("/manual-confirmation", (request, response) => {
    const kind = request.body?.kind;
    if (kind !== "clear_cart" && kind !== "submit_checkout") {
      response.sendStatus(400);
      return;
    }
    const token = "confirmation-" + randomUUID().replaceAll("-", "");
    if (
      !shopper(response).cart.register({
        token,
        task_id: "task-manual-" + randomUUID(),
        kind,
        cart_revision: request.body?.cart_revision,
      })
    ) {
      response.sendStatus(409);
      return;
    }
    response.status(201).json({ token });
  });
  return router;
}
