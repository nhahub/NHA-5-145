import type { RequestHandler, Response } from "express";
import { timingSafeEqual } from "node:crypto";
import type { CartChange, Outcome } from "./event-log.js";
import {
  ShopperRegistry,
  credentialDigest,
  type ShopperState,
} from "./shopper-state.js";

export function equalSecret(actual: unknown, expected: string): boolean {
  if (typeof actual !== "string" || !expected) return false;
  const a = Buffer.from(actual),
    b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}
export function cookieValue(header: string | undefined, name: string): string {
  const entries = (header ?? "")
    .split(";")
    .map((part) => part.trim())
    .filter((part) => part.startsWith(name + "="));
  return entries.length === 1 ? entries[0].slice(name.length + 1) : "";
}
export function shopper(response: Response): ShopperState {
  return response.locals.shopper as ShopperState;
}
const RETRIED = Symbol("shopper-state-retried");

function fail(
  response: Response,
  realEnd: Response["end"],
  status: number,
  error: string,
): void {
  if (response.headersSent) return;
  for (const name of ["set-cookie", "location", "content-length"])
    response.removeHeader(name);
  response.statusCode = status;
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  realEnd(JSON.stringify({ error }));
}

export function shopperHttp(
  registry: ShopperRegistry,
  options: {
    origin: string;
    panelOrigin: string;
    secure: boolean;
    evaluation: boolean;
    /** Runs the (synchronous) request handling inside one catalogue snapshot. */
    snapshot: <T>(read: () => T) => T;
    /** Emits one cart-change record (fixed vocabulary only). */
    record: (change: CartChange, outcome: Outcome, status: number) => void;
  },
): RequestHandler {
  return async (request, response, next) => {
    if (
      request.path === "/__catalogue/v1/products" &&
      request.method === "GET"
    ) {
      next();
      return;
    }
    if (
      request.path.toLowerCase().startsWith("/__test/") &&
      !options.evaluation
    ) {
      response.sendStatus(404);
      return;
    }
    const realEnd = response.end.bind(response) as Response["end"];
    try {
      let state = await registry.resolve(
        cookieValue(request.headers.cookie, "copilot_store"),
        false,
      );
      const safe = request.method === "GET" || request.method === "HEAD";
      // Only a navigation/bootstrap starts an identity, never a mutation or private read.
      if (
        !state &&
        safe &&
        (request.path === "/" ||
          request.path === "/__shopper" ||
          request.path.startsWith("/p/") ||
          request.path.startsWith("/c/"))
      ) {
        const created = await registry.create();
        if (!created) {
          response.status(503).json({ error: "shopper_capacity" });
          return;
        }
        state = created.state;
        response.cookie("copilot_store", created.credential, {
          httpOnly: true,
          secure: options.secure,
          sameSite: "strict",
          path: "/",
        });
      }
      if (!state) {
        response.status(401).json({ error: "shopper_expired" });
        return;
      }
      if (
        !safe &&
        (request.headers.origin !== options.origin ||
          !equalSecret(
            request.headers["x-csrf-token"] ?? request.body?.copilot_csrf,
            state.csrf,
          ))
      ) {
        response.status(403).json({ error: "invalid_browser_authority" });
        return;
      }
      // Authenticated browser activity extends commerce expiry; private probes do not.
      registry.touch(state);
      const current = state;
      const held: Array<[CartChange, Outcome, number]> = [];
      response.locals.heldChanges = held;
      const release = (failedStatus?: number): void => {
        for (const [change, outcome, status] of held.splice(0))
          options.record(
            change,
            failedStatus ? "rejected" : outcome,
            failedStatus ?? status,
          );
      };
      const originalSend = response.send;
      // Write-through: the Shopper is saved before the response leaves. A failed or
      // refused save never reports success; a lost race reloads and retries once.
      let ended = false;
      response.end = ((...args: unknown[]) => {
        if (ended) return (realEnd as (...a: unknown[]) => unknown)(...args);
        ended = true;
        registry.save(current).then(
          (outcome) => {
            if (outcome === "saved") {
              release();
              (realEnd as (...a: unknown[]) => unknown)(...args);
              return;
            }
            const retried = request as unknown as Record<symbol, boolean>;
            if (retried[RETRIED] || response.headersSent) {
              release(409);
              fail(response, realEnd, 409, "shopper_state_conflict");
              return;
            }
            retried[RETRIED] = true;
            held.length = 0;
            for (const name of response.getHeaderNames())
              response.removeHeader(name);
            response.statusCode = 200;
            response.send = originalSend;
            response.end = realEnd;
            (
              request.app as unknown as {
                handle: (req: unknown, res: unknown) => void;
              }
            ).handle(request, response);
          },
          () => {
            release(503);
            fail(response, realEnd, 503, "shopper_state_unavailable");
          },
        );
        return response;
      }) as Response["end"];
      response.locals.shopper = state;
      response.set("Cache-Control", "no-store");
      const send = response.send.bind(response);
      response.send = (body: unknown) => {
        if (typeof body === "string" && body.startsWith("<!doctype html>")) {
          body = body
            .replace(
              "</head>",
              '<meta name="copilot-panel-origin" content="' +
                options.panelOrigin +
                '" /><meta name="copilot-store-origin" content="' +
                options.origin +
                '" /><meta name="copilot-csrf" content="' +
                state.csrf +
                '" /><meta name="copilot-context" content="' +
                credentialDigest(
                  state.binding.shopper_id + ":" + state.binding.generation,
                ) +
                '" /></head>',
            )
            .replace(
              /(<form\b[^>]*\bmethod="post"[^>]*>)/gi,
              '$1<input type="hidden" name="copilot_csrf" data-sensitive="true" value="' +
                state.csrf +
                '" />',
            );
        }
        return send(body);
      };
      options.snapshot(() => next());
    } catch {
      fail(response, realEnd, 503, "shopper_state_unavailable");
    }
  };
}
