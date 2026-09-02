#!/usr/bin/env node
/**
 * Probe ws://127.0.0.1:<port>/client.
 * Default: no token. --expect-reject exits 0 when the handshake is refused.
 * Optional --token (for positive checks). Never logs the token.
 */
import http from "node:http";
import crypto from "node:crypto";

const args = process.argv.slice(2);
const port = Number(args[Math.max(0, args.indexOf("--port")) + 1] || "8770") || Number(args[args.indexOf("--port") + 1]);
const parsedPort = (() => {
  const i = args.indexOf("--port");
  return i >= 0 ? Number(args[i + 1]) : 8770;
})();
const expectReject = args.includes("--expect-reject");
const tokenIdx = args.indexOf("--token");
const token = tokenIdx >= 0 ? args[tokenIdx + 1] : "";
const path = token ? `/client?token=${encodeURIComponent(token)}` : "/client";

const outcome = await new Promise((resolve) => {
  const key = crypto.randomBytes(16).toString("base64");
  const req = http.request({
    host: "127.0.0.1",
    port: parsedPort,
    path,
    method: "GET",
    headers: {
      Connection: "Upgrade",
      Upgrade: "websocket",
      "Sec-WebSocket-Version": "13",
      "Sec-WebSocket-Key": key,
    },
  });
  const timer = setTimeout(() => {
    req.destroy();
    resolve("timeout");
  }, 4000);
  req.on("upgrade", () => {
    clearTimeout(timer);
    req.destroy();
    resolve("open");
  });
  req.on("response", (res) => {
    clearTimeout(timer);
    res.resume();
    resolve(`rejected:${res.statusCode}`);
  });
  req.on("error", (err) => {
    clearTimeout(timer);
    resolve(`rejected:error:${err.code || "err"}`);
  });
  req.end();
});

const rejected = String(outcome).startsWith("rejected") || outcome === "timeout";
if (expectReject) {
  if (rejected && outcome !== "timeout") {
    console.log(JSON.stringify({ ok: true, outcome, unauthenticated: "rejected" }));
    process.exit(0);
  }
  console.log(JSON.stringify({ ok: false, outcome, unauthenticated: outcome === "open" ? "accepted" : outcome }));
  process.exit(1);
}

console.log(JSON.stringify({ ok: outcome === "open", outcome }));
process.exit(outcome === "open" ? 0 : 1);
