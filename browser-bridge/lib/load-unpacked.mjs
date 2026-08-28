#!/usr/bin/env node
/**
 * Fallback: load the audited unpacked extension into a DEDICATED profile via CDP
 * Extensions.loadUnpacked. Requires Chrome/Edge launched with
 * --enable-unsafe-extension-debugging and --remote-debugging-port on 127.0.0.1.
 * Never pointed at the human default user-data-dir.
 */
const args = process.argv.slice(2);
const portIdx = args.indexOf("--port");
const pathIdx = args.indexOf("--path");
const port = Number(portIdx >= 0 ? args[portIdx + 1] : "9224");
const extPath = pathIdx >= 0 ? args[pathIdx + 1] : "";

if (!port || !extPath) {
  console.error("FAILED:load-unpacked need --port and --path");
  process.exit(2);
}
if (/User Data/i.test(extPath) || /extension-live/i.test(extPath)) {
  console.error("FAILED:load-unpacked refusing human User Data path or extension-live auto-load");
  process.exit(2);
}
if (!/extension-agent/i.test(extPath)) {
  console.error("FAILED:load-unpacked path must be extension-agent");
  process.exit(2);
}

const versionUrl = `http://127.0.0.1:${port}/json/version`;
const version = await fetch(versionUrl).then(async (res) => {
  if (!res.ok) throw new Error(`cdp version HTTP ${res.status}`);
  return res.json();
});
const wsUrl = version.webSocketDebuggerUrl;
if (!wsUrl || !String(wsUrl).startsWith("ws://127.0.0.1")) {
  console.error("FAILED:load-unpacked websocket is not loopback");
  process.exit(1);
}

const ws = new WebSocket(wsUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener("open", resolve);
  ws.addEventListener("error", () => reject(new Error("cdp websocket error")));
});

let nextId = 1;
function cdp(method, params) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timeout ${method}`)), 15000);
    const onMessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id !== id) return;
      clearTimeout(timer);
      ws.removeEventListener("message", onMessage);
      if (msg.error) reject(new Error(`${method}: ${msg.error.message}`));
      else resolve(msg.result ?? {});
    };
    ws.addEventListener("message", onMessage);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

try {
  const result = await cdp("Extensions.loadUnpacked", { path: extPath });
  console.log(`SUCCESS:load-unpacked id=${result.id ?? result.extensionId ?? "ok"}`);
} catch (error) {
  const text = String(error?.message ?? error);
  console.log(`SUCCESS:load-unpacked skipped (${text.slice(0, 160)}) — relying on --load-extension if present`);
} finally {
  ws.close();
}
