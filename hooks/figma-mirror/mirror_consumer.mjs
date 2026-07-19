#!/usr/bin/env node
/**
 * mirror_consumer.mjs -- the agent-facing consumer for the figma-mirror pipeline (gem-hunt N.3).
 *
 * The figma-mirror hook (check.py) does the deterministic bookkeeping: at Stop it hashes the
 * design/style files edited this session and MARKS which ones went stale in `mirror-manifest.json`.
 * This consumer is what the AGENT runs to actually act on that manifest:
 *
 *   node mirror_consumer.mjs plan   [--target figma|designsync] [--files a,b] [--dirty <file>]
 *        -> recomputes staleness (content-hash), SKIPS unchanged surfaces, marks the changed ones
 *           `planned`, and prints the exact use_figma / DesignSync plan the agent should execute.
 *
 *   node mirror_consumer.mjs mark-mirrored --source <path> --target figma --node <id>
 *   node mirror_consumer.mjs mark-mirrored --source <path> --target designsync --path <p>
 *        -> records an HONEST `mirrored` entry AFTER the agent actually performed the write
 *           (target + node/path + timestamp + the exact mirrored hash). This is the only way an
 *           entry becomes `mirrored`; nothing else claims a sync happened.
 *
 *   node mirror_consumer.mjs status
 *        -> prints honest manifest counts (recomputed staleness).
 *
 * HONESTY (MASTER Theme C / N.3): a code->Figma mirror is LOSSY -- structure + design tokens
 * survive the round-trip; React state, routing, data, and logic do NOT. `plan` therefore emits
 * `status:"planned"`, never `"synced"`. use_figma writes are in-place and quota-exempt on the
 * Education Full seat; DesignSync (claude.ai Design System project) is the Figma-free 2nd target.
 *
 * Pure Node (node:crypto / node:fs / node:path) -- no external deps. sha256-of-raw-bytes matches
 * check.py's hashlib exactly, so both tools read/write the same manifest.
 */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

// --- helpers ----------------------------------------------------------------
function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function norm(p) {
  return String(p || "").split(path.sep).join("/").replace(/\\/g, "/");
}

function absKey(p) {
  return norm(path.resolve(String(p)));
}

function sha256(p) {
  try {
    return createHash("sha256").update(fs.readFileSync(p)).digest("hex");
  } catch {
    return null;
  }
}

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith("--")) {
        out[key] = true;
      } else {
        out[key] = next;
        i++;
      }
    } else {
      out._.push(a);
    }
  }
  return out;
}

function blankManifest() {
  return { version: 1, hash_algo: "sha256", updated_at: null, target_default: "figma", entries: {} };
}

function resolveManifestPath(args) {
  if (process.env.FIGMA_MIRROR_MANIFEST) return process.env.FIGMA_MIRROR_MANIFEST;
  if (args.manifest && args.manifest !== true) return String(args.manifest);
  const cwd = args.cwd && args.cwd !== true ? String(args.cwd) : process.cwd();
  try {
    const designDir = path.join(cwd, ".design");
    if (fs.existsSync(designDir) && fs.statSync(designDir).isDirectory()) {
      return path.join(designDir, "mirror-manifest.json");
    }
  } catch {
    /* ignore */
  }
  return path.join(os.homedir(), ".claude", "figma-mirror", "mirror-manifest.json");
}

function readManifest(p) {
  try {
    const obj = JSON.parse(fs.readFileSync(p, "utf8"));
    if (obj && typeof obj === "object" && obj.entries && typeof obj.entries === "object") {
      obj.version ??= 1;
      obj.hash_algo ??= "sha256";
      obj.target_default ??= "figma";
      return obj;
    }
  } catch {
    /* ignore */
  }
  return blankManifest();
}

function writeManifest(p, obj) {
  obj.updated_at = nowIso();
  fs.mkdirSync(path.dirname(p), { recursive: true });
  const tmp = p + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(obj, null, 2), "utf8");
  fs.renameSync(tmp, p);
}

// exact, then case-insensitive (Windows drive-letter / path casing) lookup
function findEntryKey(entries, key) {
  if (Object.prototype.hasOwnProperty.call(entries, key)) return key;
  const lk = key.toLowerCase();
  for (const k of Object.keys(entries)) {
    if (k.toLowerCase() === lk) return k;
  }
  return key;
}

function collectCandidates(args, manifest) {
  const set = new Set();
  if (args.files && args.files !== true) {
    for (const f of String(args.files).split(",")) {
      const s = f.trim();
      if (s) set.add(absKey(s));
    }
  }
  if (args.dirty && args.dirty !== true) {
    try {
      for (const line of fs.readFileSync(String(args.dirty), "utf8").split(/\r?\n/)) {
        const s = line.trim();
        if (s) set.add(absKey(s));
      }
    } catch {
      /* ignore */
    }
  }
  // Default source of truth: everything the hook already recorded in the manifest.
  for (const k of Object.keys(manifest.entries || {})) set.add(k);
  return [...set];
}

function actionFor(target, entry) {
  if (target === "designsync") {
    return {
      tool: "DesignSync",
      skill: "/design-sync",
      action: entry && entry.designsync_path
        ? `DesignSync finalize_plan + write_files to '${entry.designsync_path}' (Figma-free target).`
        : "DesignSync finalize_plan + write_files to a claude.ai Design System project (Figma-free target).",
    };
  }
  return {
    tool: "mcp__figma__use_figma",
    skill: "/figma-use",
    action: entry && entry.figma_node_id
      ? `Run /figma-use, then use_figma to update node '${entry.figma_node_id}' IN PLACE (quota-exempt on the Education Full seat).`
      : "Run /figma-use, then use_figma to create/locate the mirror node and write it IN PLACE (quota-exempt on the Education Full seat).",
  };
}

// --- commands ---------------------------------------------------------------
function cmdPlan(args) {
  const rawTarget = args.target && args.target !== true ? String(args.target) : null;
  // An explicit, valid --target OVERRIDES an entry's previously-stored target.
  const explicitTarget = ["figma", "designsync"].includes(rawTarget) ? rawTarget : null;
  const mpath = resolveManifestPath(args);
  const manifest = readManifest(mpath);
  const defTarget = explicitTarget || manifest.target_default || "figma";
  const entries = (manifest.entries ||= {});
  const plan = [];
  const skipped = [];
  const missing = [];
  let mutated = false;

  for (const cand of collectCandidates(args, manifest)) {
    const key = findEntryKey(entries, cand);
    if (!fs.existsSync(key)) {
      missing.push(key);
      continue;
    }
    const h = sha256(key);
    if (!h) {
      missing.push(key);
      continue;
    }
    const entry = entries[key] || {};
    const prior = entry.last_mirrored_hash || null;
    let size = 0;
    try {
      size = fs.statSync(key).size;
    } catch {
      /* ignore */
    }
    // "skip when content-hash unchanged" -- already mirrored at this exact hash.
    if (prior && prior === h) {
      entry.source = key;
      entry.content_hash = h;
      entry.size = size;
      entry.lossy = true;
      entry.status = "mirrored";
      entries[key] = entry;
      skipped.push({ source: key, content_hash: h, reason: "unchanged-since-last-mirror" });
      mutated = true;
      continue;
    }
    const tgt = explicitTarget || entry.target || defTarget;
    const act = actionFor(tgt, entry);
    entry.source = key;
    entry.content_hash = h;
    entry.size = size;
    entry.last_seen_at = nowIso();
    entry.lossy = true;
    entry.target = tgt;
    entry.figma_node_id ??= null;
    entry.designsync_path ??= null;
    entry.last_mirrored_hash = prior;
    entry.last_mirrored_at ??= null;
    entry.status = "planned";
    entries[key] = entry;
    mutated = true;
    plan.push({
      source: key,
      content_hash: h,
      status: "planned",
      target: tgt,
      lossy: true,
      never_mirrored: prior === null,
      ...act,
    });
  }

  if (mutated) writeManifest(mpath, manifest);

  const out = {
    ok: true,
    command: "plan",
    manifest: norm(mpath),
    generated_at: nowIso(),
    default_target: defTarget,
    lossy: true,
    honesty:
      "code->Figma is lossy: structure + design tokens carry across; state, routing, data, and logic do not. These entries are PLANNED, not synced. After each real write, run `mark-mirrored`.",
    counts: { planned: plan.length, skipped: skipped.length, missing: missing.length },
    plan,
    skipped,
    missing,
  };
  process.stdout.write(JSON.stringify(out, null, 2) + "\n");
  process.stderr.write(`SUCCESS:figma-mirror-plan planned=${plan.length} skipped=${skipped.length}\n`);
  return 0;
}

function cmdMarkMirrored(args) {
  const source = args.source && args.source !== true ? String(args.source) : null;
  const target = args.target && args.target !== true ? String(args.target) : null;
  if (!source || !["figma", "designsync"].includes(target)) {
    fail("mark-mirrored requires --source <path> and --target figma|designsync");
    return 2;
  }
  const node = args.node && args.node !== true ? String(args.node) : null;
  const dpath = args.path && args.path !== true ? String(args.path) : null;
  if (target === "figma" && !node) {
    fail("mark-mirrored --target figma requires --node <figma-node-id>");
    return 2;
  }
  if (target === "designsync" && !dpath) {
    fail("mark-mirrored --target designsync requires --path <designsync-path>");
    return 2;
  }
  const key = absKey(source);
  const h = sha256(key);
  if (!h) {
    fail(`cannot read source file: ${key}`);
    return 2;
  }
  const mpath = resolveManifestPath(args);
  const manifest = readManifest(mpath);
  const entries = (manifest.entries ||= {});
  const ekey = findEntryKey(entries, key);
  const entry = entries[ekey] || {};
  let size = 0;
  try {
    size = fs.statSync(key).size;
  } catch {
    /* ignore */
  }
  entry.source = key;
  entry.content_hash = h;
  entry.size = size;
  entry.status = "mirrored";
  entry.target = target;
  entry.figma_node_id = target === "figma" ? node : (entry.figma_node_id || null);
  entry.designsync_path = target === "designsync" ? dpath : (entry.designsync_path || null);
  entry.last_mirrored_hash = h;
  entry.last_mirrored_at = nowIso();
  entry.last_seen_at ??= nowIso();
  entry.lossy = true;
  if (args.note && args.note !== true) entry.note = String(args.note);
  entries[ekey === key ? key : ekey] = entry;
  writeManifest(mpath, manifest);

  const out = {
    ok: true,
    command: "mark-mirrored",
    manifest: norm(mpath),
    source: key,
    target,
    figma_node_id: entry.figma_node_id,
    designsync_path: entry.designsync_path,
    last_mirrored_hash: h,
    last_mirrored_at: entry.last_mirrored_at,
    lossy: true,
  };
  process.stdout.write(JSON.stringify(out, null, 2) + "\n");
  process.stderr.write(`SUCCESS:figma-mirror-mark source=${path.basename(key)} target=${target}\n`);
  return 0;
}

function cmdStatus(args) {
  const mpath = resolveManifestPath(args);
  const manifest = readManifest(mpath);
  const entries = manifest.entries || {};
  const counts = { total: 0, stale: 0, mirrored: 0, planned: 0, unsupported: 0, missing: 0 };
  const stale = [];
  for (const [key, e] of Object.entries(entries)) {
    counts.total++;
    if (!fs.existsSync(key)) {
      counts.missing++;
      continue;
    }
    const h = sha256(key);
    const prior = e.last_mirrored_hash || null;
    if (h && prior && h === prior) {
      counts.mirrored++;
    } else {
      counts.stale++;
      stale.push(path.basename(key));
    }
    if (e.status === "planned") counts.planned++;
    if (e.status === "unsupported") counts.unsupported++;
  }
  const out = {
    ok: true,
    command: "status",
    manifest: norm(mpath),
    hash_algo: manifest.hash_algo,
    counts,
    stale_files: stale.slice(0, 24),
    honesty: "staleness = content_hash != last_mirrored_hash (recomputed live). Labels may lag; hashes do not.",
  };
  process.stdout.write(JSON.stringify(out, null, 2) + "\n");
  process.stderr.write(`SUCCESS:figma-mirror-status total=${counts.total} stale=${counts.stale}\n`);
  return 0;
}

function fail(reason) {
  process.stdout.write(JSON.stringify({ ok: false, error: reason }, null, 2) + "\n");
  process.stderr.write(`FAILED:figma-mirror-consumer ${reason}\n`);
}

function main() {
  const argv = process.argv.slice(2);
  const cmd = (argv[0] || "").toLowerCase();
  const args = parseArgs(argv.slice(1));
  try {
    if (cmd === "plan") return cmdPlan(args);
    if (cmd === "mark-mirrored" || cmd === "mark") return cmdMarkMirrored(args);
    if (cmd === "status") return cmdStatus(args);
    fail(`unknown command '${cmd || "(none)"}'. Use: plan | mark-mirrored | status`);
    return 2;
  } catch (err) {
    fail(String((err && err.message) || err));
    return 1;
  }
}

process.exit(main());
