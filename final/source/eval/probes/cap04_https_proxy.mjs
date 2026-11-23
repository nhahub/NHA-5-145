// DISPOSABLE CAP-04 feasibility probe. Never a deployment proxy.
import https from "node:https";
import process from "node:process";
import { URL } from "node:url";
import http from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { resolve, extname, sep } from "node:path";

const root = process.cwd();
const dir = resolve(root, ".scratch/cap04-cloud-readiness/probe");
const panel = "https://panel.copilot.test:4443";
const sameSite = process.env.COPILOT_PROBE_LAYOUT === "same-site";
const store = sameSite
  ? "https://store.copilot.test:4443"
  : "https://store.merchant.test:4443";
const replaceOrigins = (value) =>
  value
    .replaceAll("http://localhost:8000", panel)
    .replaceAll("http://localhost:4100", panel)
    .replaceAll("http://localhost:4000", store);
const tls = {
  key: readFileSync(resolve(dir, "tls/leaf.key")),
  cert: readFileSync(resolve(dir, "tls/leaf.pem")),
};
const streams = new Set();
https
  .createServer(tls, (req, res) => {
    const host = req.headers.host;
    const isStore = host === new URL(store).host;
    const isControl = sameSite && host === "store.merchant.test:4443";
    if (!isStore && !isControl && host !== "panel.copilot.test:4443") {
      res.writeHead(421).end();
      return;
    }
    const path = new URL(req.url, panel).pathname;
    if (!isStore && !isControl && path === "/__probe/disconnect-sse") {
      if (
        req.method !== "POST" ||
        req.headers.origin !== panel ||
        !req.headers.cookie
      ) {
        res.writeHead(403).end();
        return;
      }
      let disconnected = 0;
      for (const stream of [...streams]) {
        if (stream.cookie === req.headers.cookie) {
          stream.response.destroy();
          disconnected++;
        }
      }
      res
        .writeHead(200, {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
        })
        .end(JSON.stringify({ disconnected }));
      return;
    }

    if (isControl && path === "/__probe/control-frame") {
      res
        .writeHead(200, {
          "Content-Type": "text/html",
          "Cache-Control": "no-store",
        })
        .end("<!doctype html><html><body>cookie control</body></html>");
      return;
    }
    // Independently prove browser third-party blocking inside the actual iframe.
    if ((isStore || isControl) && path === "/__probe/cookie-control") {
      res
        .writeHead(200, {
          "Cache-Control": "no-store",
          "Set-Cookie": [
            "probe_unpartitioned=1; Secure; HttpOnly; SameSite=None; Path=/",
            "probe_partitioned=1; Secure; HttpOnly; SameSite=None; Partitioned; Path=/",
          ],
        })
        .end("ok");
      return;
    }
    if ((isStore || isControl) && path === "/__probe/cookie-echo") {
      const names = new Set(
        (req.headers.cookie ?? "")
          .split(";")
          .map((x) => x.trim().split("=")[0]),
      );
      res
        .writeHead(200, {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
        })
        .end(
          JSON.stringify({
            unpartitioned: names.has("probe_unpartitioned"),
            partitioned: names.has("probe_partitioned"),
          }),
        );
      return;
    }
    if (isControl) {
      res.writeHead(404).end();
      return;
    }
    if (!isStore && (path === "/" || path.startsWith("/assets/"))) {
      const base = resolve(root, "panel/dist");
      const file = resolve(base, path === "/" ? "index.html" : "." + path);
      if (!file.startsWith(base + sep) || !existsSync(file)) {
        res.writeHead(404).end();
        return;
      }
      const type =
        {
          ".html": "text/html",
          ".js": "application/javascript",
          ".css": "text/css",
        }[extname(file)] ?? "application/octet-stream";
      res
        .writeHead(200, { "Content-Type": type, "Cache-Control": "no-store" })
        .end(replaceOrigins(readFileSync(file, "utf8")));
      return;
    }
    const upstream = http.request(
      {
        host: "127.0.0.1",
        port: isStore ? 4000 : 8000,
        path: req.url,
        method: req.method,
        headers: { ...req.headers, "accept-encoding": "identity" },
      },
      (response) => {
        const headers = { ...response.headers };
        delete headers["transfer-encoding"];
        delete headers["content-length"];
        if (isStore && headers["set-cookie"]) {
          const mode = readFileSync(resolve(dir, "mode.txt"), "utf8").trim();
          headers["set-cookie"] = headers["set-cookie"].map((cookie) => {
            if (!cookie.startsWith("copilot_store=") || mode === "strict")
              return cookie;
            return (
              cookie.replace(/SameSite=Strict/i, "SameSite=None") +
              (mode === "partitioned" ? "; Partitioned" : "")
            );
          });
        }
        res.writeHead(response.statusCode, headers);
        res.flushHeaders();
        if (
          !isStore &&
          String(headers["content-type"]).includes("text/event-stream")
        ) {
          const stream = { cookie: req.headers.cookie, response: res };
          streams.add(stream);
          res.on("close", () => streams.delete(stream));
        }
        if (/javascript/.test(String(headers["content-type"]))) {
          let body = "";
          response.setEncoding("utf8");
          response.on("data", (chunk) => (body += chunk));
          response.on("end", () => res.end(replaceOrigins(body)));
        } else response.pipe(res); // SSE streams directly; never collect/buffer it.
      },
    );
    upstream.on("error", () => {
      if (!res.headersSent) res.writeHead(502);
      res.end();
    });
    res.on("close", () => upstream.destroy());
    req.pipe(upstream);
  })
  .listen(4443, "127.0.0.1");
