#!/usr/bin/env node
/**
 * Focus-independent Chrome/Edge proof via chrome-bridge hub + chrome.debugger CDP.
 * No OS keystroke injection. Window does not need to be foreground.
 */
import { Hub } from "../chrome-bridge-mcp/dist/hub.js";
import { loadBridgeAuth } from "../lib/load-bridge-auth.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const get = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : fallback;
};

const hubPort = Number(get("port", "8770"));
const auth = loadBridgeAuth(hubPort === 8790 ? "live" : "agent");
const port = hubPort;
const browser = get("browser", "chrome");
const resultsDir = get("results", path.join(path.dirname(fileURLToPath(import.meta.url)), "results"));
const foregroundFile = get("foreground-json", "");

function readForeground() {
  if (!foregroundFile || !fs.existsSync(foregroundFile)) return null;
  try {
    return JSON.parse(fs.readFileSync(foregroundFile, "utf8"));
  } catch {
    return null;
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function evalJson(hub, expression) {
  const response = await hub.call(
    {
      type: "cdp",
      method: "Runtime.evaluate",
      params: { expression, returnByValue: true, awaitPromise: true, userGesture: true },
    },
    20000,
  );
  if (response?.exceptionDetails) {
    throw new Error(response.exceptionDetails.exception?.description ?? response.exceptionDetails.text ?? "eval failed");
  }
  return response?.result?.value;
}

const hub = new Hub(port, auth.token, auth.extensionId);
const role = await hub.start();
const deadline = Date.now() + 40000;
let tabs;
while (Date.now() < deadline) {
  try {
    tabs = await hub.call({ type: "listTabs" }, 5000);
    break;
  } catch (error) {
    const msg = String(error?.message ?? error);
    if (!/not connected/i.test(msg)) throw error;
    await sleep(500);
  }
}
if (!tabs) {
  await hub.close();
  console.error("FAILED:proof extension never connected to hub");
  process.exit(1);
}

const opened = await hub.call({ type: "newTab", url: "https://example.com/", active: true, group: true }, 30000);
await sleep(1200);
for (let i = 0; i < 20; i++) {
  const ready = await evalJson(hub, "document.readyState");
  if (ready === "complete" || ready === "interactive") break;
  await sleep(250);
}

const titleBefore = await evalJson(hub, "document.title");
const urlBefore = await evalJson(hub, "location.href");
const href = await evalJson(
  hub,
  `(() => { const a = document.querySelector('a[href]'); if (!a) return ''; window.__bridgeClickTrusted = null; a.addEventListener('click', (e) => { window.__bridgeClickTrusted = e.isTrusted; }, true); return a.href; })()`,
);
const box = await evalJson(
  hub,
  `(() => { const a = document.querySelector('a[href]'); if (!a) return null; const r = a.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2, text: a.textContent.trim() }; })()`,
);

const fgDuring = readForeground();

if (box && typeof box.x === "number") {
  await hub.call({ type: "cdp", method: "Input.dispatchMouseEvent", params: { type: "mouseMoved", x: box.x, y: box.y } });
  await hub.call({
    type: "cdp",
    method: "Input.dispatchMouseEvent",
    params: { type: "mousePressed", x: box.x, y: box.y, button: "left", clickCount: 1, buttons: 1 },
  });
  await hub.call({
    type: "cdp",
    method: "Input.dispatchMouseEvent",
    params: { type: "mouseReleased", x: box.x, y: box.y, button: "left", clickCount: 1, buttons: 0 },
  });
  await sleep(1500);
}

const trusted = await evalJson(hub, "window.__bridgeClickTrusted");
const titleAfter = await evalJson(hub, "document.title");
const urlAfter = await evalJson(hub, "location.href");
const fgAfter = readForeground();

const evidence = {
  ok: true,
  browser,
  hubRole: role,
  hubPort: port,
  bind: "127.0.0.1",
  tab: opened,
  titleBefore,
  urlBefore,
  clicked: box,
  href,
  isTrusted: trusted,
  titleAfter,
  urlAfter,
  foregroundDuring: fgDuring,
  foregroundAfter: fgAfter,
  keystrokeInjection: false,
  inputPath: "cdp Input.dispatchMouseEvent via chrome.debugger",
  navigated: urlAfter !== urlBefore || titleAfter !== titleBefore,
  timestamp: new Date().toISOString(),
};

fs.mkdirSync(resultsDir, { recursive: true });
const out = path.join(resultsDir, `${browser}-focus-independent.json`);
fs.writeFileSync(out, JSON.stringify(evidence, null, 2));
console.log(`SUCCESS:proof wrote ${out}`);
console.log(`titleBefore=${titleBefore}`);
console.log(`titleAfter=${titleAfter}`);
console.log(`urlAfter=${urlAfter}`);
console.log(`isTrusted=${trusted}`);
console.log(`navigated=${evidence.navigated}`);
await hub.close();
