import request from "supertest";
import type { Express } from "express";

/** Real cookie/CSRF bootstrap for HTTP tests; no production authentication bypass. */
export async function browser(app: Express) {
  const client = request.agent(app);
  const bootstrap = await client.get("/__shopper");
  if (bootstrap.status !== 200) throw new Error("Shopper bootstrap failed");
  client.set("Origin", "http://localhost:4000");
  client.set("x-csrf-token", bootstrap.body.csrf);
  return client;
}
