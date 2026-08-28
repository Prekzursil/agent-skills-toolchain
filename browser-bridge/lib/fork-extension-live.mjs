#!/usr/bin/env node
/**
 * Fork extension-agent → extension-live with port 8790 baked in and a stable
 * CRX id derived from a generated public key. Private key is discarded (not written).
 */
import { generateKeyPairSync, createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const src = path.join(root, "extension-agent");
const dest = path.join(root, "extension-live");

function copyDir(from, to) {
  fs.mkdirSync(to, { recursive: true });
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    const a = path.join(from, entry.name);
    const b = path.join(to, entry.name);
    if (entry.isDirectory()) copyDir(a, b);
    else fs.copyFileSync(a, b);
  }
}

copyDir(src, dest);

const { publicKey } = generateKeyPairSync("rsa", {
  modulusLength: 2048,
  publicKeyEncoding: { type: "spki", format: "der" },
  privateKeyEncoding: { type: "pkcs8", format: "pem" },
});

const hex = createHash("sha256").update(publicKey).digest("hex").slice(0, 32);
const extensionId = [...hex].map((c) => String.fromCharCode("a".charCodeAt(0) + parseInt(c, 16))).join("");
const keyB64 = publicKey.toString("base64");

const manifestPath = path.join(dest, "manifest.json");
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
manifest.name = "Chrome Bridge (LIVE profile)";
manifest.version = "0.2.0";
manifest.description =
  "LIVE-profile bridge. Hub ws://127.0.0.1:8790 baked in. Owner-loaded only. Never load extension-agent into this profile.";
manifest.key = keyB64;
manifest.action.default_title = "Chrome Bridge LIVE (8790)";
fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");

let background = fs.readFileSync(path.join(dest, "background.js"), "utf8");
background = background.replace("const DEFAULT_PORT = 8770;", "const DEFAULT_PORT = 8790;");
fs.writeFileSync(path.join(dest, "background.js"), background);

let popupJs = fs.readFileSync(path.join(dest, "popup.js"), "utf8");
popupJs = popupJs
  .replace("const LOCKED_PORT = 8770;", "const LOCKED_PORT = 8790;")
  .replace("Connected to agent hub", "Connected to LIVE hub")
  .replace("Waiting for agent hub", "Waiting for LIVE hub");
fs.writeFileSync(path.join(dest, "popup.js"), popupJs);

let popupHtml = fs.readFileSync(path.join(dest, "popup.html"), "utf8");
popupHtml = popupHtml
  .replace("Chrome Bridge (agent)", "Chrome Bridge (LIVE)")
  .replace(">8770<", ">8790<")
  .replace("chromeBridge.agentToken", "chromeBridge.liveToken")
  .replace(
    "This extension talks only to ws://127.0.0.1:8770. Do not load it into the human/1Password Chrome profile — that is extension-live on 8790.",
    "Port 8790 is baked in. Load this unpacked folder into the human profile only when the owner chose (a) live for this run. Never load extension-agent here.",
  );
fs.writeFileSync(path.join(dest, "popup.html"), popupHtml);

fs.writeFileSync(path.join(dest, "EXTENSION_ID"), extensionId + "\n");
console.log(JSON.stringify({ ok: true, dest, extensionId, keyBytes: publicKey.length }));
