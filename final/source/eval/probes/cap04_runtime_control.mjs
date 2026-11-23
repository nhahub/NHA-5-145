// Evaluation-only fault injection and cookie control, outside the public Caddy listener.
import http from "node:http";
import https from "node:https";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import process from "node:process";

const secret = process.env.COPILOT_SERVICE_SECRET;
if (!secret || secret.length < 32)
  throw new Error("Missing evaluation control authority");
const tls = resolve(process.cwd(), ".scratch/cap04-cloud-readiness/probe/tls");
const streams = new Set();
http
  .createServer((req, res) => {
    const upstream = http.request(
      {
        hostname: "127.0.0.1",
        port: 8000,
        path: req.url,
        method: req.method,
        headers: req.headers,
      },
      (response) => {
        res.writeHead(response.statusCode, response.headers);
        res.flushHeaders();
        if (
          String(response.headers["content-type"]).includes("text/event-stream")
        ) {
          const stream = { cookie: req.headers.cookie, response: res };
          streams.add(stream);
          res.on("close", () => streams.delete(stream));
        }
        response.pipe(res);
      },
    );
    upstream.on("error", () => {
      if (!res.headersSent) res.writeHead(502);
      res.end();
    });
    res.on("close", () => upstream.destroy());
    req.pipe(upstream);
  })
  .listen(8001, "127.0.0.1");

http
  .createServer((req, res) => {
    if (
      req.method !== "POST" ||
      req.headers["x-service-secret"] !== secret ||
      req.url !== "/disconnect"
    ) {
      res.writeHead(403).end();
      return;
    }
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 4096) req.destroy();
    });
    req.on("end", () => {
      try {
        const { cookie } = JSON.parse(body);
        if (typeof cookie !== "string") throw new Error("Invalid cookie");
        let disconnected = 0;
        if (req.url === "/disconnect")
          for (const stream of [...streams]) {
            if (stream.cookie === cookie) {
              stream.response.destroy();
              disconnected++;
            }
          }
        res.writeHead(200, { "Content-Type": "application/json" }).end(
          JSON.stringify({
            disconnected,
          }),
        );
      } catch {
        res.writeHead(400).end();
      }
    });
  })
  .listen(8002, "127.0.0.1");

https
  .createServer(
    {
      key: readFileSync(resolve(tls, "leaf.key")),
      cert: readFileSync(resolve(tls, "leaf.pem")),
    },
    (req, res) => {
      const host = req.headers.host;
      if (
        !["panel.copilot.test:4444", "store.merchant.test:4444"].includes(host)
      ) {
        res.writeHead(421).end();
        return;
      }
      const headers = { "Cache-Control": "no-store" };
      if (
        host === "panel.copilot.test:4444" &&
        req.url === "/__probe/control-page"
      ) {
        res
          .writeHead(200, { ...headers, "Content-Type": "text/html" })
          .end(
            '<!doctype html><iframe id="cookie-control" src="https://store.merchant.test:4444/__probe/control-frame"></iframe>',
          );
      } else if (req.url === "/__probe/control-frame") {
        res
          .writeHead(200, { ...headers, "Content-Type": "text/html" })
          .end("<!doctype html><body>cookie control</body>");
      } else if (req.url === "/__probe/cookie-control") {
        res
          .writeHead(200, {
            ...headers,
            "Set-Cookie": [
              "probe_unpartitioned=1; Secure; HttpOnly; SameSite=None; Path=/",
              "probe_partitioned=1; Secure; HttpOnly; SameSite=None; Partitioned; Path=/",
            ],
          })
          .end("ok");
      } else if (req.url === "/__probe/cookie-echo") {
        const cookie = req.headers.cookie ?? "";
        res
          .writeHead(200, { ...headers, "Content-Type": "application/json" })
          .end(
            JSON.stringify({
              unpartitioned: cookie.includes("probe_unpartitioned=1"),
              partitioned: cookie.includes("probe_partitioned=1"),
            }),
          );
      } else res.writeHead(404).end();
    },
  )
  .listen(4444, "127.0.0.1");
