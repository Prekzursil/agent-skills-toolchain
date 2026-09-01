#!/usr/bin/env node
/**
 * Hardening verification: (a) unauthenticated hub rejected, (b) cookie CDP
 * refused, (c) tokened navigate+read of example.com when the extension is up.
 * Never prints the token.
 */
import http from "node:http";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Hub } from "../chrome-bridge-mcp/dist/hub.js";
import { loadBridgeAuth } from "../lib/load-bridge-auth.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const resultsDir = path.join(root, "proof", "results");
const auth = loadBridgeAuth("agent");
const port = auth.port;

function handshake(pathnameQs) {
  return new Promise((resolve) => {
    const key = crypto.randomBytes(16).toString("base64");
    const req = http.request({
      host: "127.0.0.1",
      port,
      path: pathnameQs,
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
}

const evidence = {
  ok: false,
  timestamp: new Date().toString(),
  port,
  extensionId: auth.extensionId,
  tokenSource: auth.path,
  tokenPrinted: false,
  a_unauthenticatedRejected: false,
  a_wrongTokenRejected: false,
  a_detail: "",
  b_getAllCookiesRefused: false,
  b_documentCookieRefused: false,
  b_detail: "",
  c_navigated: false,
  c_title: "",
  c_url: "",
  c_detail: "",
  hubRole: "",
};

const unauth = await handshake("/client");
evidence.a_detail = `unauth=${unauth}`;
evidence.a_unauthenticatedRejected = String(unauth).startsWith("rejected");

const wrong = await handshake("/client?token=definitely-wrong-token");
evidence.a_detail += ` wrong=${wrong}`;
evidence.a_wrongTokenRejected = String(wrong).startsWith("rejected");

const hub = new Hub(port, auth.token, auth.extensionId);
evidence.hubRole = await hub.start();

try {
  try {
    await hub.call({ type: "cdp", method: "Network.getAllCookies", params: {} }, 8000);
    evidence.b_detail = "Network.getAllCookies unexpectedly succeeded";
  } catch (err) {
    const msg = String(err?.message ?? err);
    evidence.b_detail = msg.slice(0, 240);
    evidence.b_getAllCookiesRefused = /denied|allowlist/i.test(msg);
  }
  try {
    await hub.call(
      {
        type: "cdp",
        method: "Runtime.evaluate",
        params: { expression: "document.cookie", returnByValue: true },
      },
      8000,
    );
    evidence.b_detail += " | document.cookie unexpectedly succeeded";
  } catch (err) {
    const msg = String(err?.message ?? err);
    evidence.b_detail += ` | eval=${msg.slice(0, 200)}`;
    evidence.b_documentCookieRefused = /cookie|credential|storage|denied|allowlist/i.test(msg);
  }

  let connected = false;
  try {
    await hub.call({ type: "listTabs" }, 6000);
    connected = true;
  } catch (err) {
    evidence.c_detail = String(err?.message ?? err).slice(0, 200);
  }

  if (connected) {
    const opened = await hub.call({ type: "newTab", url: "https://example.com/", active: true, group: true }, 30000);
    await new Promise((r) => setTimeout(r, 1200));
    const titleResp = await hub.call(
      {
        type: "cdp",
        method: "Runtime.evaluate",
        params: { expression: "document.title", returnByValue: true, awaitPromise: true },
      },
      20000,
    );
    const urlResp = await hub.call(
      {
        type: "cdp",
        method: "Runtime.evaluate",
        params: { expression: "location.href", returnByValue: true, awaitPromise: true },
      },
      20000,
    );
    evidence.c_title = titleResp?.result?.value ?? "";
    evidence.c_url = urlResp?.result?.value ?? "";
    evidence.c_navigated = /example/i.test(String(evidence.c_title)) || /example\.com/i.test(String(evidence.c_url));
    evidence.c_detail = `tab=${opened?.id ?? "?"} title=${evidence.c_title}`;
    await hub.call({ type: "closeTab", tabId: opened?.id }, 10000).catch(() => {});
  }
} finally {
  await hub.close();
}

evidence.ok =
  evidence.a_unauthenticatedRejected &&
  evidence.a_wrongTokenRejected &&
  evidence.b_getAllCookiesRefused &&
  evidence.b_documentCookieRefused &&
  evidence.c_navigated;

fs.mkdirSync(resultsDir, { recursive: true });
const out = path.join(resultsDir, "hardening-verify.json");
fs.writeFileSync(out, JSON.stringify(evidence, null, 2));
console.log(`SUCCESS:hardening-evidence ${out}`);
console.log(`a_unauth_rejected=${evidence.a_unauthenticatedRejected}`);
console.log(`a_wrong_rejected=${evidence.a_wrongTokenRejected}`);
console.log(`b_cookies_refused=${evidence.b_getAllCookiesRefused}`);
console.log(`b_eval_cookie_refused=${evidence.b_documentCookieRefused}`);
console.log(`c_navigated=${evidence.c_navigated} title=${evidence.c_title}`);
console.log(`ok=${evidence.ok}`);
process.exit(evidence.ok ? 0 : 2);
