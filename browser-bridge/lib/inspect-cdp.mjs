#!/usr/bin/env node
const port = Number(process.argv[2] || 9224);
const version = await fetch(`http://127.0.0.1:${port}/json/version`).then((r) => r.json());
const ws = new WebSocket(version.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener("open", resolve);
  ws.addEventListener("error", () => reject(new Error("ws error")));
});
let nextId = 1;
function cdp(method, params = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timeout ${method}`)), 12000);
    const onMessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id !== id) return;
      clearTimeout(timer);
      ws.removeEventListener("message", onMessage);
      if (msg.error) reject(new Error(`${method}: ${JSON.stringify(msg.error)}`));
      else resolve(msg.result ?? {});
    };
    ws.addEventListener("message", onMessage);
    ws.send(JSON.stringify({ id, method, params }));
  });
}
try {
  const targets = await cdp("Target.getTargets");
  for (const t of targets.targetInfos ?? []) {
    console.log(`target type=${t.type} url=${t.url} title=${t.title}`);
  }
} catch (e) {
  console.log("getTargets", e.message);
}
for (const method of ["Extensions.getExtensions", "Extensions.list", "SystemInfo.getInfo"]) {
  try {
    const result = await cdp(method, {});
    console.log(method, JSON.stringify(result).slice(0, 400));
  } catch (e) {
    console.log(method, e.message);
  }
}
const extPath = process.argv[3];
if (extPath) {
  try {
    const loaded = await cdp("Extensions.loadUnpacked", { path: extPath });
    console.log("loadUnpacked", loaded);
  } catch (e) {
    console.log("loadUnpacked", e.message);
  }
}
ws.close();
