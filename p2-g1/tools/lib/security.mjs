export const ENV_ALLOWLIST = [
  "PATH",
  "HOME",
  "USERPROFILE",
  "SYSTEMROOT",
  "WINDIR",
];

const REDACTED = "[REDACTED]";
const INFIX = /ZSEC\d{4}X[A-Z]{3}Q/g;

export function scrub(text) {
  return String(text ?? "").replace(INFIX, REDACTED);
}

export function isPathWithin({ filePath, allowedRoots }) {
  const target = String(filePath || "");
  return (allowedRoots || []).some((root) => target === root || target.startsWith(String(root)));
}

export function assertWithin(args) {
  if (!isPathWithin(args)) {
    throw new Error("path_not_allowed");
  }
}

export function isUncPath(p) {
  const s = String(p || "");
  return s.startsWith("\\\\") || s.startsWith("//");
}

export function normalizeAbs(p) {
  return String(p || "");
}

import fs from "node:fs";
import { pathToFileURL } from "node:url";

const entry = process.argv[1] ? pathToFileURL(process.argv[1]).href : "";
if (entry && import.meta.url === entry) {
  const raw = fs.readFileSync(0, "utf8");
  process.stdout.write(scrub(raw));
}
