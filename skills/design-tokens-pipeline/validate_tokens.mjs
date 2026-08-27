#!/usr/bin/env node
// validate_tokens.mjs — gate a DTCG token file against the W3C DTCG v1.0 rules
// that actually break the Tokens-Studio ⇄ Style-Dictionary round-trip.
// Checks (each emits a finding with a rule id):
//   missing-type     leaf token has no resolvable $type (own or inherited).
//   bad-alias        a {group.token} alias points at a non-existent token.
//   alias-cycle      aliases form a cycle (a -> b -> a) — SD would loop.
//   raw-hex-in-code  a $type:color value is a raw hex AND a sibling alias of
//                    the SAME value exists (i.e. a hardcoded value that should
//                    reference a token; the §G1 "no raw hex" token gate).
//   reserved-misuse  a `$`-prefixed key other than the DTCG reserved set.
//
// Usage: node validate_tokens.mjs --file tokens.json [--strict]
// --strict treats warnings (raw-hex-in-code) as failures too.
// Emits SUCCESS:design-tokens-validate <n ok> / FAILED:... <n errors>.
import { readFileSync } from "node:fs";
import { parseArgs, flatten, aliasTarget, emitMarker } from "./lib.mjs";

const ID = "design-tokens-validate";
const RESERVED = new Set(["$value", "$type", "$description", "$extensions", "$deprecated"]);

function findReservedMisuse(node, path, findings) {
  if (node == null || typeof node !== "object") return;
  for (const k of Object.keys(node)) {
    if (k.startsWith("$") && !RESERVED.has(k)) {
      findings.push({ rule: "reserved-misuse", path: path ? `${path}.${k}` : k, severity: "error",
        message: `unknown reserved key "${k}" (DTCG reserves only ${[...RESERVED].join(", ")})` });
    }
    if (!k.startsWith("$") && node[k] && typeof node[k] === "object") {
      findReservedMisuse(node[k], path ? `${path}.${k}` : k, findings);
    }
  }
}

function resolveChain(start, flat, seen = new Set()) {
  // Follow aliases to a concrete value; returns {ok, value, type} or {cycle|broken}.
  let path = start;
  while (true) {
    if (seen.has(path)) return { cycle: true, at: path };
    seen.add(path);
    const leaf = flat.get(path);
    if (!leaf) return { broken: true, at: path };
    const target = aliasTarget(leaf.value);
    if (!target) return { ok: true, value: leaf.value, type: leaf.type };
    path = target;
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.file) return process.exit(emitMarker(false, ID, "missing --file"));
  let tree;
  try {
    tree = JSON.parse(readFileSync(String(args.file), "utf8"));
  } catch (e) {
    return process.exit(emitMarker(false, ID, `parse: ${e.message}`));
  }

  const flat = flatten(tree);
  const findings = [];
  findReservedMisuse(tree, "", findings);

  // index concrete color values -> set of token paths (for raw-hex-in-code).
  const colorValuePaths = new Map();
  for (const [path, leaf] of flat) {
    if (leaf.type === "color" && !aliasTarget(leaf.value)) {
      const key = leaf.value.toLowerCase().trim();
      (colorValuePaths.get(key) ?? colorValuePaths.set(key, []).get(key)).push(path);
    }
  }

  for (const [path, leaf] of flat) {
    const target = aliasTarget(leaf.value);
    if (target) {
      const r = resolveChain(path, flat);
      if (r.cycle) findings.push({ rule: "alias-cycle", path, severity: "error", message: `alias cycle through ${r.at}` });
      else if (r.broken) findings.push({ rule: "bad-alias", path, severity: "error", message: `alias -> {${target}} does not resolve (dangling at ${r.at})` });
      continue; // aliases inherit type from referent; no missing-type check
    }
    if (!leaf.type) {
      findings.push({ rule: "missing-type", path, severity: "error",
        message: `no $type (and no ancestor group $type) for value "${leaf.value}"` });
    }
    // raw-hex-in-code: a concrete color that an alias-able semantic token also holds.
    if (leaf.type === "color") {
      const key = leaf.value.toLowerCase().trim();
      const peers = colorValuePaths.get(key) ?? [];
      if (peers.length > 1) {
        findings.push({ rule: "raw-hex-in-code", path, severity: "warning",
          message: `raw color ${leaf.value} duplicated across ${peers.length} tokens (${peers.join(", ")}) — alias one to the other` });
      }
    }
  }

  const errors = findings.filter((f) => f.severity === "error");
  const warnings = findings.filter((f) => f.severity === "warning");
  const report = { id: ID, file: String(args.file), tokens: flat.size,
    summary: { errors: errors.length, warnings: warnings.length }, findings };
  process.stderr.write(JSON.stringify(report, null, 2) + "\n");

  const fail = errors.length > 0 || (args.strict && warnings.length > 0);
  if (fail) return process.exit(emitMarker(false, ID, `${errors.length} error(s), ${warnings.length} warning(s)`));
  process.exit(emitMarker(true, ID, `${flat.size} tokens, ${warnings.length} warning(s)`));
}

main();
