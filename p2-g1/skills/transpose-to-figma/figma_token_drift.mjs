#!/usr/bin/env node
// transpose-to-figma / figma_token_drift.mjs — W3C-DTCG token drift detector
// (design #8, MASTER C-Tier2 S-series; makes the "tokens round-trip losslessly" claim CHECKED).
//
// Pull live Figma variables -> DTCG -> diff against the code-side DTCG tokens. Like transpose.mjs
// this harness is PLUMBING: it never calls the Figma MCP itself. The caller saves the Figma
// variable defs (Figma MCP `get_variable_defs`, or a `use_figma` Plugin-API export) to a DTCG
// JSON file, then feeds both sides in here for a numeric, per-token drift report.
//
// Zero external deps. Understands the W3C Design Tokens Community Group format (DTCG v1.0 /
// 2025.10): nested groups, leaf tokens carrying `$value` + optional `$type`, `$type` inheritance
// from ancestor groups, and `{alias.references}`. Colors are normalized (#rgb -> #rrggbb, case,
// rgb()/rgba()) so cosmetic differences are NOT counted as drift.
//
// SHADOW MODE by default (council C5): reports drift, never blocks (exit 0 + SUCCESS marker as
// long as the diff ran). Pass --enforce to exit 1 with a FAILED marker when drift > --max-drift.
//
// Subcommand:
//   diff --figma <figma.dtcg.json> --code <code.dtcg.json> [--max-drift 0] [--out <dir>] [--enforce]
//     -> prints added / removed / changed leaf tokens + a drift count + SUCCESS/FAILED marker.
//
// Terminal-state markers (AGENTS.md §4):
//   SUCCESS:figma-token-drift-<id>  /  FAILED:figma-token-drift-<id> <reason>

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) out[key] = true;
      else { out[key] = next; i++; }
    } else out._.push(a);
  }
  return out;
}

const shortId = () => Math.random().toString(36).slice(2, 8);

// Flatten a DTCG tree into a Map<dotted.path, {value, type}>.
// A node is a leaf token iff it carries `$value`. `$type` inherits from the nearest ancestor.
function flattenTokens(node, prefix, inheritedType, acc) {
  if (node === null || typeof node !== 'object' || Array.isArray(node)) return acc;
  const groupType = Object.prototype.hasOwnProperty.call(node, '$type') ? node.$type : inheritedType;
  if (Object.prototype.hasOwnProperty.call(node, '$value')) {
    const type = Object.prototype.hasOwnProperty.call(node, '$type') ? node.$type : inheritedType;
    acc.set(prefix, { value: node.$value, type: type ?? null });
    return acc; // leaf tokens are not descended further
  }
  for (const key of Object.keys(node)) {
    if (key.startsWith('$')) continue; // $type, $description, $extensions, etc.
    const child = node[key];
    const path = prefix ? `${prefix}.${key}` : key;
    flattenTokens(child, path, groupType, acc);
  }
  return acc;
}

// Normalize a token value for comparison so cosmetic-only differences don't read as drift.
function normalizeValue(value, type) {
  if (value === null || value === undefined) return value;
  if (typeof value === 'object') {
    // composite tokens (shadow, typography, border, gradient) — normalize deeply + stably
    return JSON.stringify(sortDeep(normalizeDeep(value)));
  }
  if (typeof value !== 'string') return value; // numbers, booleans compared as-is
  let s = value.trim();
  // aliases like {color.brand.500} — compare case-insensitively, whitespace-collapsed
  if (/^\{.*\}$/.test(s)) return s.replace(/\s+/g, '').toLowerCase();
  if (type === 'color' || /^#|^rgb/i.test(s)) return normalizeColor(s);
  return s;
}

function normalizeDeep(v) {
  if (Array.isArray(v)) return v.map(normalizeDeep);
  if (v && typeof v === 'object') {
    const o = {};
    for (const k of Object.keys(v)) o[k] = normalizeDeep(v[k]);
    return o;
  }
  if (typeof v === 'string') {
    const s = v.trim();
    if (/^\{.*\}$/.test(s)) return s.replace(/\s+/g, '').toLowerCase();
    if (/^#|^rgb/i.test(s)) return normalizeColor(s);
    return s;
  }
  return v;
}

function sortDeep(v) {
  if (Array.isArray(v)) return v.map(sortDeep);
  if (v && typeof v === 'object') {
    const o = {};
    for (const k of Object.keys(v).sort()) o[k] = sortDeep(v[k]);
    return o;
  }
  return v;
}

function normalizeColor(input) {
  let s = input.trim().toLowerCase();
  // rgb()/rgba() -> #rrggbb(aa)
  const m = s.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/);
  if (m) {
    const to2 = (n) => Math.round(Math.max(0, Math.min(255, n))).toString(16).padStart(2, '0');
    let hex = '#' + to2(+m[1]) + to2(+m[2]) + to2(+m[3]);
    if (m[4] !== undefined) hex += to2(parseFloat(m[4]) <= 1 ? parseFloat(m[4]) * 255 : +m[4]);
    return hex;
  }
  if (/^#[0-9a-f]{3}$/.test(s)) return '#' + s[1] + s[1] + s[2] + s[2] + s[3] + s[3];
  if (/^#[0-9a-f]{4}$/.test(s)) return '#' + s[1] + s[1] + s[2] + s[2] + s[3] + s[3] + s[4] + s[4];
  // strip a redundant full-opacity alpha (#rrggbbff -> #rrggbb)
  if (/^#[0-9a-f]{8}$/.test(s) && s.slice(7) === 'ff') return s.slice(0, 7);
  return s;
}

function loadDtcg(path, label, id) {
  let text;
  try { text = readFileSync(path, 'utf8'); }
  catch (e) { console.log(`FAILED:figma-token-drift-${id} could not read ${label} tokens: ${e.message}`); process.exit(1); }
  try { return JSON.parse(text); }
  catch (e) { console.log(`FAILED:figma-token-drift-${id} ${label} tokens not valid JSON: ${e.message}`); process.exit(1); }
}

function cmdDiff(args) {
  const id = shortId();
  const figmaPath = args.figma;
  const codePath = args.code;
  if (!figmaPath || figmaPath === true) {
    console.log(`FAILED:figma-token-drift-${id} --figma <dtcg.json> is required (get_variable_defs export)`);
    process.exit(1);
  }
  if (!codePath || codePath === true) {
    console.log(`FAILED:figma-token-drift-${id} --code <dtcg.json> is required (repo design tokens)`);
    process.exit(1);
  }
  const maxDrift = args['max-drift'] ? Number(args['max-drift']) : 0;
  const enforce = !!args.enforce;

  const figmaTree = loadDtcg(figmaPath, 'figma', id);
  const codeTree = loadDtcg(codePath, 'code', id);

  const figma = flattenTokens(figmaTree, '', undefined, new Map());
  const code = flattenTokens(codeTree, '', undefined, new Map());

  const added = [];   // in figma, missing in code
  const removed = []; // in code, missing in figma
  const changed = []; // present both sides, value or type differs

  for (const [path, f] of figma) {
    if (!code.has(path)) { added.push({ path, figmaValue: f.value, type: f.type }); continue; }
    const c = code.get(path);
    const fv = normalizeValue(f.value, f.type);
    const cv = normalizeValue(c.value, c.type);
    const typeDrift = (f.type ?? null) !== (c.type ?? null);
    if (fv !== cv || typeDrift) {
      changed.push({
        path,
        figmaValue: f.value, codeValue: c.value,
        figmaType: f.type, codeType: c.type,
        reason: fv !== cv ? 'value' : 'type',
      });
    }
  }
  for (const [path, c] of code) {
    if (!figma.has(path)) removed.push({ path, codeValue: c.value, type: c.type });
  }

  const drift = added.length + removed.length + changed.length;
  const pass = drift <= maxDrift;

  const record = {
    id: `figma-token-drift-${id}`,
    figma: figmaPath,
    code: codePath,
    figmaTokenCount: figma.size,
    codeTokenCount: code.size,
    drift,
    added,
    removed,
    changed,
    maxDrift,
    verdict: pass ? 'pass' : 'fail',
    mode: enforce ? 'enforce' : 'shadow',
    capturedAt: new Date().toISOString(),
  };
  if (args.out && args.out !== true) {
    mkdirSync(args.out, { recursive: true });
    const file = join(args.out, 'figma-token-drift.json');
    writeFileSync(file, JSON.stringify(record, null, 2));
    console.log(`wrote ${file}`);
  }
  console.log(JSON.stringify(record, null, 2));

  if (!pass && enforce) {
    console.log(`FAILED:figma-token-drift-${id} drift ${drift} > max ${maxDrift} (enforce mode)`);
    process.exit(1);
  }
  if (!pass) {
    console.log(`NOTE: SHADOW verdict=fail (drift ${drift} > ${maxDrift}); observing only, not blocking.`);
  }
  console.log(`SUCCESS:figma-token-drift-${id}`);
}

const args = parseArgs(process.argv.slice(2));
const sub = args._[0];
try {
  if (sub === 'diff') cmdDiff(args);
  else {
    console.log('Usage: figma_token_drift.mjs diff --figma <figma.dtcg.json> --code <code.dtcg.json> [--max-drift 0] [--out <dir>] [--enforce]');
    console.log(`FAILED:figma-token-drift-usage-${shortId()} unknown subcommand: ${sub ?? '(none)'}`);
    process.exit(1);
  }
} catch (e) {
  console.log(`FAILED:figma-token-drift-${shortId()} ${e.message}`);
  process.exit(1);
}
