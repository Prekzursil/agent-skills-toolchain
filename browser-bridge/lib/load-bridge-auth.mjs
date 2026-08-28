/**
 * Read chromeBridge auth from ~/.agents/local.json. Never logs token values.
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const LOCAL_JSON = path.join(os.homedir(), ".agents", "local.json");

export function loadBridgeAuth(mode = "agent") {
  if (!fs.existsSync(LOCAL_JSON)) {
    throw new Error("local.json missing — run lib/ensure_bridge_auth.py first");
  }
  const data = JSON.parse(fs.readFileSync(LOCAL_JSON, "utf8"));
  const bridge = data.chromeBridge;
  if (!bridge || typeof bridge !== "object") {
    throw new Error("local.json chromeBridge missing");
  }
  const token = mode === "live" ? bridge.liveToken : bridge.agentToken;
  const extensionId = mode === "live" ? bridge.liveExtensionId : bridge.agentExtensionId;
  if (!token || String(token).length < 16) {
    throw new Error(`chromeBridge ${mode} token missing`);
  }
  return {
    token: String(token),
    extensionId: String(extensionId || ""),
    port: mode === "live" ? 8790 : 8770,
    path: LOCAL_JSON,
  };
}
