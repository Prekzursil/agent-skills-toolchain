#!/usr/bin/env node
// extract_tokens.mjs — pull design tokens OUT of code into DTCG JSON.
// Source of truth for a code-first repo is the code; this lifts CSS custom
// properties (and an optional Tailwind theme dump) into a W3C-DTCG token tree
// so Tokens Studio / Style Dictionary can round-trip them (FIGMA-SETUP §3:
// "establish the Variables token set BEFORE capture").
//
// Inputs:
//   --css <file,file,...>     one or more CSS files; reads `--name: value;`
//                             declarations (any selector, :root recommended).
//   --tailwind <json>         a JSON dump of a Tailwind theme (e.g.
//                             `npx tailwindcss ... ` or hand-exported
//                             `theme.extend`) — flat or nested colors/spacing.
//   --prefix <str>            strip this leading token-name prefix (e.g. `tw`).
//   --out <file>             write the DTCG tree here (default: stdout JSON).
//
// Emits SUCCESS:design-tokens-extract <n> / FAILED:... on the last line.
import { readFileSync, writeFileSync } from "node:fs";
import { parseArgs, inferType, nameToPath, cssRefToAlias, unflatten, emitMarker } from "./lib.mjs";

const ID = "design-tokens-extract";

function parseCssVars(css, prefix) {
  // Strip comments, then match custom-property declarations.
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const out = [];
  const re = /(--[\w-]+)\s*:\s*([^;{}]+);/g;
  let m;
  while ((m = re.exec(clean)) !== null) {
    const name = m[1];
    const raw = m[2].trim();
    const path = nameToPath(name, prefix);
    if (!path) continue;
    const value = cssRefToAlias(raw, prefix); // var(--x) -> {x} alias
    const type = inferType(value);
    out.push([path, { value, type }]);
  }
  return out;
}

function walkTailwind(obj, base, out) {
  for (const [k, v] of Object.entries(obj)) {
    const key = String(k).replace(/[.\/]/g, "-"); // 0.5 / 1/2 -> safe key
    const path = base ? `${base}.${key}` : key;
    if (v && typeof v === "object" && !Array.isArray(v)) {
      walkTailwind(v, path, out);
    } else {
      const value = String(v);
      out.push([path, { value, type: inferType(value) }]);
    }
  }
}

function parseTailwind(json) {
  const theme = JSON.parse(json);
  const out = [];
  // Map well-known theme keys to DTCG-ish group names; keep others verbatim.
  const groups = {
    colors: "color",
    spacing: "spacing",
    fontSize: "fontSize",
    fontFamily: "fontFamily",
    borderRadius: "radius",
    boxShadow: "shadow",
  };
  const src = theme.theme?.extend ?? theme.theme ?? theme;
  for (const [k, v] of Object.entries(src)) {
    if (v && typeof v === "object") walkTailwind(v, groups[k] ?? k, out);
  }
  return out;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const prefix = typeof args.prefix === "string" ? args.prefix : "";
  let entries = [];
  try {
    if (args.css) {
      for (const f of String(args.css).split(",").map((s) => s.trim()).filter(Boolean)) {
        entries.push(...parseCssVars(readFileSync(f, "utf8"), prefix));
      }
    }
    if (args.tailwind) {
      entries.push(...parseTailwind(readFileSync(String(args.tailwind), "utf8")));
    }
  } catch (e) {
    return process.exit(emitMarker(false, ID, e.message));
  }
  if (entries.length === 0) {
    return process.exit(emitMarker(false, ID, "no tokens found (need --css and/or --tailwind)"));
  }
  // De-dup by path (later source wins) and warn on unknown types via stderr.
  const byPath = new Map(entries);
  const untyped = [...byPath.entries()].filter(([, l]) => !l.type).map(([p]) => p);
  if (untyped.length) process.stderr.write(`warn: ${untyped.length} token(s) with un-inferable $type: ${untyped.slice(0, 8).join(", ")}\n`);
  const tree = unflatten([...byPath.entries()]);
  const out = JSON.stringify(tree, null, 2);
  if (args.out) writeFileSync(String(args.out), out + "\n");
  else process.stdout.write(out + "\n");
  process.exit(emitMarker(true, ID, String(byPath.size)));
}

main();
