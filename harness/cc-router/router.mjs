// cc-router — zero-dependency Anthropic-protocol router for the Claude Code "unified" profile.
// Routes by model prefix: glm-* -> https://api.z.ai/api/anthropic (rotation-fresh key),
// claude-* -> https://api.anthropic.com (Machine-scope ANTHROPIC_API_KEY). Both upstreams speak the
// Anthropic wire format, so bodies are forwarded VERBATIM — only the auth header is rewritten.
// Contract (estate-audit verified): never allowlist beta values, relay SSE byte-for-byte including
// pings, forward error bodies / retry-after / anthropic-ratelimit-* unmodified.
// Lifecycle: start via router-run.cmd (health-check gated); no scheduled tasks, no reapers.
import http from "node:http";
import https from "node:https";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import os from "node:os";

const PORT = Number(process.env.CC_ROUTER_PORT || 8377);
const ZAI_UPSTREAM = "api.z.ai";
const CC_UPSTREAM = "api.anthropic.com";
const KEY_FILE = path.join(os.homedir(), ".agents", "secrets", "zai-api-key.txt");
const VERBOSE = process.env.CC_ROUTER_VERBOSE === "1";
const BODY_CAP = 64 * 1024 * 1024;

// --- credential caches ------------------------------------------------------
let zaiCache = { key: "", at: 0 };
function zaiKey() {
  const now = Date.now();
  if (now - zaiCache.at < 5000) return zaiCache.key; // 5s cache: rotation-fresh without per-request IO
  try {
    const k = fs.readFileSync(KEY_FILE, "utf8").trim();
    if (k) { zaiCache = { key: k, at: now }; return k; }
  } catch { /* fail open to env */ }
  zaiCache = { key: process.env.ZAI_API_KEY || "", at: now };
  return zaiCache.key;
}

let ccCache = { key: "", at: 0 };
function ccKey() {
  if (process.env.CC_ANTHROPIC_KEY) return process.env.CC_ANTHROPIC_KEY; // owner-stashed router-only key wins
  const now = Date.now();
  if (now - ccCache.at < 10 * 60 * 1000) return ccCache.key; // 10 min cache
  try {
    const out = execSync(
      'reg query "HKLM\\Environment" /v ANTHROPIC_API_KEY',
      { encoding: "utf8", timeout: 5000, windowsHide: true },
    );
    const m = out.match(/ANTHROPIC_API_KEY\s+REG_SZ\s+(\S+)/);
    ccCache = { key: m ? m[1] : "", at: now };
  } catch { ccCache = { key: "", at: now }; }
  return ccCache.key;
}

function pickUpstream(model) {
  if (/^claude/i.test(model || "")) {
    const k = ccKey();
    return { host: CC_UPSTREAM, port: 443, key: k, auth: k ? { "x-api-key": k } : null, leg: "claude", prefix: "" };
  }
  const k = zaiKey();
  return { host: ZAI_UPSTREAM, port: 443, key: k, auth: k ? { authorization: `Bearer ${k}` } : null, leg: "glm", prefix: "/api/anthropic" };
}

// --- proxy handler ----------------------------------------------------------
function proxy(req, res) {
  if (req.method === "GET" && req.url === "/health") {
    const health = { ok: true, port: PORT, legs: { glm: Boolean(zaiKey()), claude: Boolean(ccKey()) } };
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify(health));
    return;
  }
  if (req.method === "HEAD" && req.url === "/api/hello") { res.writeHead(200); res.end(); return; }

  const okPath = req.url.startsWith("/v1/messages") || req.url.startsWith("/v1/messages/count_tokens");
  if (req.method !== "POST" || !okPath) {
    res.writeHead(404, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: { type: "not_found", message: `router: unsupported ${req.method} ${req.url}` } }));
    return;
  }

  const chunks = [];
  let size = 0;
  req.on("data", (c) => {
    size += c.length;
    if (size > BODY_CAP) { req.destroy(); return; }
    chunks.push(c);
  });
  req.on("end", () => {
    let model = "";
    try {
      const body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      model = String(body.model || "");
    } catch { /* body stays opaque; route by default below */ }
    const up = pickUpstream(model);
    if (!up.key) {
      res.writeHead(502, { "content-type": "application/json" });
      res.end(JSON.stringify({ error: { type: "router_no_credential", message: `router: no credential for leg '${up.leg}' (model '${model}')` } }));
      return;
    }
    const headers = {
      ...(up.auth),
      "content-type": req.headers["content-type"] || "application/json",
      "accept": req.headers["accept"] || "application/json",
      "anthropic-version": req.headers["anthropic-version"] || "2023-06-01",
    };
    // beta header(s) forwarded VERBATIM — never allowlist (extended-context etc. are header-only)
    for (const h of Object.keys(req.headers)) {
      if (h === "anthropic-beta" && req.headers[h]) headers["anthropic-beta"] = req.headers[h];
    }
    const ureq = https.request(
      { host: up.host, port: up.port, path: (up.prefix || "") + req.url, method: "POST", headers, servername: up.host },
      (ures) => {
        const outHeaders = {};
        for (const [h, v] of Object.entries(ures.headers)) {
          if (h === "transfer-encoding" || h === "content-length" || h === "connection") continue;
          outHeaders[h] = v;
        }
        res.writeHead(ures.statusCode || 502, outHeaders);
        ures.pipe(res); // byte-for-byte SSE pass-through, pings included
      },
    );
    ureq.on("error", (e) => {
      if (!res.headersSent) {
        res.writeHead(502, { "content-type": "application/json" });
        res.end(JSON.stringify({ error: { type: "router_upstream_error", message: `router: ${up.leg} leg failed: ${e.message}` } }));
      } else res.end();
    });
    if (chunks.length) ureq.write(Buffer.concat(chunks));
    ureq.end();
    if (VERBOSE) console.log(`${new Date().toISOString()} ${up.leg} ${model || "?"} ${req.url}`);
  });
}

const server = http.createServer(proxy);
server.listen(PORT, "127.0.0.1", () => {
  console.log(`cc-router listening on http://127.0.0.1:${PORT} (legs: glm=${Boolean(zaiKey())}, claude=${Boolean(ccKey())})`);
});
server.on("error", (e) => {
  console.error(`cc-router: ${e.message}`);
  process.exit(1);
});
