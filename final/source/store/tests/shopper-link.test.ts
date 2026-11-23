import request from "supertest";
import { describe, expect, it } from "vitest";
import { createApp } from "./app.js";
import { browser } from "./browser.js";
const secret = "test-only-service-credential-not-a-real-secret";

describe("private shopper linking", () => {
  it("requires service authority and consumes only the matching challenge once", async () => {
    const app = createApp({ serviceSecret: secret });
    const a = await browser(app);
    const issued = await a.post("/__copilot/link-ticket").send({
      challenge: "a".repeat(64),
      audience: "http://localhost:4100",
    });
    expect(issued.status).toBe(201);
    const body = {
      ticket: issued.body.ticket,
      challenge: "a".repeat(64),
      audience: "http://localhost:4100",
    };
    expect(
      (await request(app).post("/__internal/link/redeem").send(body)).status,
    ).toBe(403);
    expect(
      (
        await request(app)
          .post("/__internal/link/redeem")
          .set("x-service-secret", secret)
          .send({ ...body, challenge: "b".repeat(64) })
      ).status,
    ).toBe(409);
    const redeemed = await request(app)
      .post("/__internal/link/redeem")
      .set("x-service-secret", secret)
      .send(body);
    expect(redeemed.status).toBe(200);
    expect(redeemed.body.shopper_id).toHaveLength(64);
    expect(
      (
        await request(app)
          .post("/__internal/link/redeem")
          .set("x-service-secret", secret)
          .send(body)
      ).status,
    ).toBe(409);
    expect(
      (
        await request(app)
          .post("/__internal/shopper/validate")
          .set("x-service-secret", secret)
          .send(redeemed.body)
      ).status,
    ).toBe(200);
  });
  it("expires tickets and denies stale generations without creating commerce state", async () => {
    let now = 100;
    const app = createApp({ serviceSecret: secret, clock: () => now });
    const a = await browser(app);
    const issued = await a.post("/__copilot/link-ticket").send({
      challenge: "a".repeat(64),
      audience: "http://localhost:4100",
    });
    now += 60000;
    expect(
      (
        await request(app)
          .post("/__internal/link/redeem")
          .set("x-service-secret", secret)
          .send({
            ticket: issued.body.ticket,
            challenge: "a".repeat(64),
            audience: "http://localhost:4100",
          })
      ).status,
    ).toBe(409);
    expect(
      (
        await request(app)
          .post("/__internal/shopper/validate")
          .set("x-service-secret", secret)
          .send({ shopper_id: "a".repeat(64), generation: "b".repeat(64) })
      ).status,
    ).toBe(410);
  });
});
