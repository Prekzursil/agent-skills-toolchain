#!/usr/bin/env node
// execution-grounded-bon / rerank.mjs
// -----------------------------------------------------------------------------
// Execution-grounded best-of-N + behavioral-diff reranker.
//
// Picks a winner among N CANDIDATE PATCHES (typically from a cross-vendor
// Claude+Codex worktree fan-out) using ONLY execution-derived, agent-inauthorable
// signals — NEVER an LLM judge (JudgeBench shows model-opinion rerank ~= chance;
// MASTER A4 / COUNCIL C3 both forbid model opinion in the done-signal loop).
//
// Pipeline (each stage is a pure, deterministic function, all exported):
//   1. observe   — read a behavior matrix: candidate x probe -> {status,exit,stdout}.
//                  Two sources: precomputed observations in the manifest, OR
//                  `execute` mode which runs each candidate's cmd per probe.
//   2. knockout  — eliminate any candidate that CRASHES / TIMES OUT / ERRORS on
//                  any probe (a strictly-broken candidate; hard, oracle-free signal).
//   3. cluster   — behavioral-diff: group survivors into equivalence classes by
//                  their behavior vector hash (identical [exit,normStdout] per probe).
//   4. consensus — pick the winning cluster. CROSS-VENDOR agreement is primary:
//                  Claude AND Codex independently reaching the same behavior are
//                  INDEPENDENT samples, so a 2-vendor cluster beats a larger
//                  1-vendor cluster (correlated). Then size, then aspect jury.
//   5. jury      — BoN-MAV: rank candidates within the winning cluster by several
//                  execution-derived aspects (probe completion, output sanity,
//                  determinism, parsimony, latency); each aspect is a juror.
//
// SHADOW by default (COUNCIL C5): always exit 0, emit an advisory verdict, never
// block. `--enforce` lets a caller turn a low-confidence verdict into a non-zero
// exit; it ships OFF.
//
// Evidence: MASTER A4 (arXiv 2502.14382 S*, 2409.08692 B4, 2503.15223 PatchDiff,
// 2207.10397 CodeT); COUNCIL C2/C3 (cross-vendor = independent failures).
//
// Zero runtime deps (node stdlib only). Node >= 18.
// -----------------------------------------------------------------------------

import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { readFileSync, appendFileSync, realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// --- observation status vocabulary -------------------------------------------
export const OK = 'ok';           // ran to a graceful exit (any exit code)
export const ERROR = 'error';     // could not spawn / internal error -> knockout
export const TIMEOUT = 'timeout'; // exceeded per-candidate timeout   -> knockout
export const CRASH = 'crash';     // killed by a signal (segfault etc)-> knockout
const HARD_FAIL = new Set([ERROR, TIMEOUT, CRASH]);

// --- normalization ------------------------------------------------------------
// Compile a manifest-supplied list of {pattern,flags,replace} into RegExp subs,
// applied to stdout before hashing (strip volatile tokens: timestamps, tmp paths,
// pids). Invalid regexes are skipped (fail-open) rather than crashing the gate.
export function compileNormalizers(specs = []) {
  const subs = [];
  for (const s of specs) {
    if (!s || typeof s.pattern !== 'string') continue;
    try {
      subs.push({ re: new RegExp(s.pattern, s.flags ?? 'g'), replace: s.replace ?? '' });
    } catch { /* skip bad regex, fail-open */ }
  }
  return subs;
}

export function normalize(text, subs = []) {
  let out = String(text ?? '');
  for (const { re, replace } of subs) {
    try { out = out.replace(re, replace); } catch { /* fail-open */ }
  }
  // trim trailing whitespace per line + collapse trailing blank lines
  return out.replace(/[ \t]+$/gm, '').replace(/\s+$/s, '');
}

// --- behavior vector + key ----------------------------------------------------
// A candidate's behavior = ordered vector of [statusCategory, exit, normStdout]
// across probes. Knocked-out candidates are removed BEFORE this, so the key only
// clusters gracefully-running candidates. Category folds all non-ok into 'fail'
// so that (ok, exit=1, "") and a real crash never collide.
export function behaviorVector(observations, probeOrder, subs = []) {
  const byProbe = new Map(observations.map((o) => [o.probe, o]));
  return probeOrder.map((pid) => {
    const o = byProbe.get(pid);
    if (!o) return ['missing', null, ''];
    const cat = o.status === OK ? 'ok' : 'fail';
    const exit = o.status === OK ? (o.exit ?? 0) : null;
    const stdout = o.status === OK ? normalize(o.stdout, subs) : '';
    return [cat, exit, stdout];
  });
}

export function behaviorKey(vector) {
  return createHash('sha256').update(JSON.stringify(vector)).digest('hex').slice(0, 16);
}

// --- knockout -----------------------------------------------------------------
export function knockout(candidate) {
  for (const o of candidate.observations ?? []) {
    if (HARD_FAIL.has(o.status)) {
      return { out: true, reason: `${o.status} on probe ${o.probe}` };
    }
  }
  return { out: false, reason: null };
}

// --- BoN-MAV aspect jury ------------------------------------------------------
// Each aspect is a juror scoring a candidate in [0,1] from EXECUTION metrics only.
// Aspects that cannot be computed (no diff size, no latency) are omitted and the
// weights renormalized over present aspects — never invented.
const DEFAULT_WEIGHTS = {
  probeCompletion: 0.4, // fraction of probes that ran ok
  outputSanity: 0.2,    // fraction of ok probes with non-empty output
  determinism: 0.2,     // identical output on a repeat run (if provided)
  parsimony: 0.1,       // smaller diff preferred (Occam) - relative
  latency: 0.1,         // faster preferred - relative
};

export function aspectScores(candidate, probeOrder, ctx = {}) {
  const obs = candidate.observations ?? [];
  const okObs = obs.filter((o) => o.status === OK);
  const m = probeOrder.length || 1;
  const aspects = {};

  aspects.probeCompletion = okObs.length / m;

  const withOutput = okObs.filter((o) => normalize(o.stdout, ctx.subs).length > 0).length;
  aspects.outputSanity = okObs.length ? withOutput / okObs.length : 0;

  // determinism: only if the manifest provided a repeat run per probe
  if (obs.some((o) => typeof o.stdout2 === 'string')) {
    let stable = 0, checked = 0;
    for (const o of obs) {
      if (o.status !== OK || typeof o.stdout2 !== 'string') continue;
      checked++;
      if (normalize(o.stdout, ctx.subs) === normalize(o.stdout2, ctx.subs)) stable++;
    }
    aspects.determinism = checked ? stable / checked : 1;
  }

  // parsimony: relative to the smallest diff among candidates (ctx.minDiff)
  if (typeof candidate.diffLines === 'number' && ctx.minDiff != null && ctx.minDiff >= 0) {
    aspects.parsimony = candidate.diffLines <= 0 ? 1 : (ctx.minDiff + 1) / (candidate.diffLines + 1);
  }

  // latency: relative to the fastest candidate (ctx.minLatency)
  const lat = candidate._totalMs ?? candidate.latencyMs;
  if (typeof lat === 'number' && ctx.minLatency != null && ctx.minLatency >= 0) {
    aspects.latency = lat <= 0 ? 1 : (ctx.minLatency + 1) / (lat + 1);
  }

  // weighted aggregate over PRESENT aspects (renormalized)
  const weights = ctx.weights ?? DEFAULT_WEIGHTS;
  let num = 0, den = 0;
  for (const [k, v] of Object.entries(aspects)) {
    const w = weights[k] ?? 0;
    num += w * v; den += w;
  }
  const aggregate = den ? num / den : 0;
  return { aspects, aggregate };
}

// --- execute mode -------------------------------------------------------------
// Run a candidate's cmd once per probe, in the candidate's cwd (its worktree).
// Probe input is delivered via stdin (default) or appended as an argv item.
// This is the only stage that touches the OS; precomputed mode skips it entirely.
export function executeCandidate(candidate, probes, opts = {}) {
  const timeout = candidate.timeoutMs ?? opts.timeoutMs ?? 20000;
  const observations = [];
  let totalMs = 0;
  for (const probe of probes) {
    const args = [...(candidate.cmd.slice(1))];
    let input;
    if (candidate.probeArg === 'arg') args.push(String(probe.input ?? ''));
    else input = String(probe.input ?? '');
    const t0 = Date.now();
    const r = spawnSync(candidate.cmd[0], args, {
      cwd: candidate.cwd || process.cwd(),
      input,
      timeout,
      encoding: 'utf8',
      maxBuffer: opts.maxBuffer ?? 8 * 1024 * 1024,
      shell: false,
    });
    totalMs += Date.now() - t0;
    let status = OK, exit = r.status;
    if (r.error && r.error.code === 'ETIMEDOUT') status = TIMEOUT;
    else if (r.error) status = ERROR;
    else if (r.signal) status = CRASH;
    observations.push({
      probe: probe.id,
      status,
      exit: status === OK ? (exit ?? 0) : null,
      stdout: status === OK ? (r.stdout ?? '') : '',
      stderr: (r.stderr ?? '').slice(0, 2000),
    });
  }
  return { observations, totalMs };
}

// --- core rerank --------------------------------------------------------------
export function rerank(manifest, opts = {}) {
  const subs = compileNormalizers(manifest.normalize);
  const weights = manifest.weights ?? DEFAULT_WEIGHTS;
  const tiebreak = manifest.tiebreak ?? opts.tiebreak ?? ['vendors', 'size', 'jury'];
  const probes = Array.isArray(manifest.probes) ? manifest.probes : [];
  const probeOrder = probes.map((p) => p.id);
  const candidates = (manifest.candidates ?? []).map((c) => ({ ...c }));

  // 1. observe (execute mode fills observations if missing)
  if (opts.execute) {
    for (const c of candidates) {
      if (!Array.isArray(c.observations) && Array.isArray(c.cmd)) {
        const { observations, totalMs } = executeCandidate(c, probes, opts);
        c.observations = observations;
        c._totalMs = totalMs;
      }
    }
  }
  for (const c of candidates) {
    c.observations = c.observations ?? [];
    c.vendor = c.vendor || 'unknown';
  }

  // 2. knockout
  const survivors = [], knockedOut = [];
  for (const c of candidates) {
    const k = knockout(c);
    if (k.out) knockedOut.push({ id: c.id, vendor: c.vendor, reason: k.reason });
    else survivors.push(c);
  }

  // aspect-jury context (relative aspects need cross-candidate mins)
  const diffVals = survivors.map((c) => c.diffLines).filter((v) => typeof v === 'number');
  const latVals = survivors.map((c) => c._totalMs ?? c.latencyMs).filter((v) => typeof v === 'number');
  const ctx = {
    subs, weights,
    minDiff: diffVals.length ? Math.min(...diffVals) : null,
    minLatency: latVals.length ? Math.min(...latVals) : null,
  };
  const juryById = new Map();
  for (const c of survivors) juryById.set(c.id, aspectScores(c, probeOrder, ctx));

  // 3. cluster survivors by behavior vector
  const clusterMap = new Map();
  for (const c of survivors) {
    const vec = behaviorVector(c.observations, probeOrder, subs);
    const key = behaviorKey(vec);
    if (!clusterMap.has(key)) clusterMap.set(key, { behaviorKey: key, members: [], vendorsSet: new Set() });
    const cl = clusterMap.get(key);
    cl.members.push(c.id);
    cl.vendorsSet.add(c.vendor);
  }
  let clusters = [...clusterMap.values()].map((cl, i) => ({
    id: `c${i + 1}`,
    behaviorKey: cl.behaviorKey,
    members: cl.members,
    vendors: [...cl.vendorsSet].sort(),
    size: cl.members.length,
    bestJury: Math.max(0, ...cl.members.map((id) => juryById.get(id)?.aggregate ?? 0)),
  }));

  // 4. consensus ranking of clusters
  const cmp = (a, b) => {
    for (const key of tiebreak) {
      let d = 0;
      if (key === 'vendors') d = b.vendors.length - a.vendors.length;
      else if (key === 'size') d = b.size - a.size;
      else if (key === 'jury') d = b.bestJury - a.bestJury;
      if (d !== 0) return d;
    }
    // final deterministic tiebreak: member input order (lowest index first)
    return a.members[0] < b.members[0] ? -1 : a.members[0] > b.members[0] ? 1 : 0;
  };
  clusters = clusters.sort(cmp);
  const winnerCluster = clusters[0] ?? null;

  // 5. winner within the winning cluster = best aspect-jury aggregate
  let winner = null;
  if (winnerCluster) {
    winner = [...winnerCluster.members].sort((x, y) => {
      const d = (juryById.get(y)?.aggregate ?? 0) - (juryById.get(x)?.aggregate ?? 0);
      return d !== 0 ? d : (x < y ? -1 : x > y ? 1 : 0);
    })[0];
  }

  // diagnostics: discrimination = fraction of probes where survivors diverge.
  // Low discrimination => the probes are weak; synthesize more distinguishing inputs.
  const overallVendors = new Set(survivors.map((c) => c.vendor));
  let discrimination = 0;
  if (survivors.length > 1 && probeOrder.length) {
    let divergent = 0;
    for (let i = 0; i < probeOrder.length; i++) {
      const cellKeys = new Set(survivors.map((c) => {
        const vec = behaviorVector(c.observations, probeOrder, subs);
        return JSON.stringify(vec[i]);
      }));
      if (cellKeys.size > 1) divergent++;
    }
    discrimination = divergent / probeOrder.length;
  }
  const indistinguishable = survivors.length > 1 && clusters.length === 1;

  // confidence (honest, execution-grounded — not model opinion)
  let confidence;
  if (survivors.length === 0) confidence = 'none';
  else if (survivors.length === 1 || overallVendors.size < 2 || indistinguishable) confidence = 'low';
  else if (winnerCluster && winnerCluster.vendors.length >= 2 && discrimination >= 0.3) confidence = 'high';
  else confidence = 'medium';

  const reasons = [];
  if (winnerCluster) {
    reasons.push(
      `winner cluster ${winnerCluster.id}: ${winnerCluster.size} candidate(s), ` +
      `${winnerCluster.vendors.length} vendor(s) [${winnerCluster.vendors.join('+')}]`);
    if (winnerCluster.vendors.length >= 2) reasons.push('cross-vendor consensus (independent failures) — strongest signal');
  }
  if (knockedOut.length) reasons.push(`${knockedOut.length} candidate(s) knocked out (crash/timeout/error)`);
  if (indistinguishable) reasons.push('all survivors behaviorally identical on the given probes — synthesize distinguishing inputs to raise confidence');
  if (survivors.length && overallVendors.size < 2) reasons.push('single-vendor pool — no cross-vendor independence; treat as low confidence');
  if (discrimination < 0.3 && survivors.length > 1) reasons.push(`low discrimination (${discrimination.toFixed(2)}) — probes barely separate candidates`);

  return {
    ok: true,
    task: manifest.task ?? null,
    mode: opts.execute ? 'execute' : 'precomputed',
    nCandidates: candidates.length,
    nSurvivors: survivors.length,
    nProbes: probeOrder.length,
    knockedOut,
    clusters,
    winnerCluster: winnerCluster ? winnerCluster.id : null,
    winner,
    winnerVendor: winner ? (candidates.find((c) => c.id === winner)?.vendor ?? null) : null,
    confidence,
    discrimination: Number(discrimination.toFixed(3)),
    indistinguishable,
    aspectScores: Object.fromEntries([...juryById.entries()].map(([id, v]) => [id, v])),
    reasons,
  };
}

// --- self-test (embedded; keeps everything in one file, real & reproducible) ---
export function selfTest() {
  const results = [];
  const check = (name, cond) => { results.push({ name, pass: !!cond }); };

  // Case 1: cross-vendor consensus beats a larger same-vendor cluster.
  // {claudeA, codexA} agree on "42"; {claudeB, claudeC, claudeD} agree on "43".
  const ob = (val) => [{ probe: 'p1', status: OK, exit: 0, stdout: val }];
  const v1 = rerank({
    task: 'crossvendor',
    probes: [{ id: 'p1', input: '1' }],
    candidates: [
      { id: 'claudeA', vendor: 'claude', observations: ob('42') },
      { id: 'codexA', vendor: 'codex', observations: ob('42') },
      { id: 'claudeB', vendor: 'claude', observations: ob('43') },
      { id: 'claudeC', vendor: 'claude', observations: ob('43') },
      { id: 'claudeD', vendor: 'claude', observations: ob('43') },
    ],
  });
  const winCl = v1.clusters.find((c) => c.id === v1.winnerCluster);
  check('cross-vendor cluster wins over larger same-vendor', winCl && winCl.vendors.length === 2 && winCl.size === 2);
  check('winner is a member of the cross-vendor cluster', ['claudeA', 'codexA'].includes(v1.winner));

  // Case 2: a crashing candidate is knocked out and cannot win.
  const v2 = rerank({
    task: 'knockout',
    probes: [{ id: 'p1' }, { id: 'p2' }],
    candidates: [
      { id: 'good', vendor: 'claude', observations: [
        { probe: 'p1', status: OK, exit: 0, stdout: 'x' }, { probe: 'p2', status: OK, exit: 0, stdout: 'y' }] },
      { id: 'crasher', vendor: 'codex', observations: [
        { probe: 'p1', status: OK, exit: 0, stdout: 'x' }, { probe: 'p2', status: CRASH, stdout: '' }] },
    ],
  });
  check('crasher knocked out', v2.knockedOut.some((k) => k.id === 'crasher'));
  check('crasher cannot be winner', v2.winner === 'good');
  check('knockout not in any cluster', !v2.clusters.some((c) => c.members.includes('crasher')));

  // Case 3: identical behavior => one cluster, flagged indistinguishable, low confidence.
  const v3 = rerank({
    task: 'indistinguishable',
    probes: [{ id: 'p1' }],
    candidates: [
      { id: 'a', vendor: 'claude', observations: ob('same') },
      { id: 'b', vendor: 'codex', observations: ob('same') },
    ],
  });
  check('single behavior cluster', v3.clusters.length === 1);
  check('indistinguishable flagged', v3.indistinguishable === true);
  check('indistinguishable => low confidence', v3.confidence === 'low');

  // Case 4: normalization strips volatile tokens so runs cluster together.
  const v4 = rerank({
    task: 'normalize',
    normalize: [{ pattern: 'ts=\\d+', flags: 'g', replace: 'ts=<n>' }],
    probes: [{ id: 'p1' }],
    candidates: [
      { id: 'a', vendor: 'claude', observations: ob('result ts=111 done') },
      { id: 'b', vendor: 'codex', observations: ob('result ts=999 done') },
    ],
  });
  check('normalized outputs cluster together', v4.clusters.length === 1 && v4.clusters[0].vendors.length === 2);

  // Case 5: high confidence when cross-vendor consensus + real discrimination.
  const v5 = rerank({
    task: 'confidence',
    probes: [{ id: 'p1' }, { id: 'p2' }],
    candidates: [
      { id: 'a', vendor: 'claude', observations: [
        { probe: 'p1', status: OK, exit: 0, stdout: 'A' }, { probe: 'p2', status: OK, exit: 0, stdout: 'B' }] },
      { id: 'b', vendor: 'codex', observations: [
        { probe: 'p1', status: OK, exit: 0, stdout: 'A' }, { probe: 'p2', status: OK, exit: 0, stdout: 'B' }] },
      { id: 'c', vendor: 'claude', observations: [
        { probe: 'p1', status: OK, exit: 0, stdout: 'X' }, { probe: 'p2', status: OK, exit: 0, stdout: 'Y' }] },
    ],
  });
  check('cross-vendor + discrimination => high confidence', v5.confidence === 'high');
  check('discrimination computed > 0', v5.discrimination > 0);

  // Case 6: aspect jury prefers the higher-completion candidate within a cluster.
  // Distinct behavior per candidate (so 2 clusters), winner cluster chosen, jury ranks.
  const v6 = rerank({
    task: 'jury',
    probes: [{ id: 'p1' }, { id: 'p2' }],
    candidates: [
      { id: 'full', vendor: 'claude', observations: [
        { probe: 'p1', status: OK, exit: 0, stdout: 'a' }, { probe: 'p2', status: OK, exit: 0, stdout: 'b' }] },
      { id: 'partial', vendor: 'claude', observations: [
        { probe: 'p1', status: OK, exit: 0, stdout: 'a' }, { probe: 'p2', status: OK, exit: 1, stdout: '' }] },
    ],
  });
  check('full-completion candidate scores >= partial', v6.aspectScores.full.aggregate >= v6.aspectScores.partial.aggregate);

  // Case 7: empty candidate pool => confidence none, no winner, still ok.
  const v7 = rerank({ task: 'empty', probes: [{ id: 'p1' }], candidates: [] });
  check('empty pool => no winner', v7.winner === null && v7.confidence === 'none' && v7.ok === true);

  const passed = results.filter((r) => r.pass).length;
  return { passed, total: results.length, results };
}

// --- CLI ----------------------------------------------------------------------
function parseArgs(argv) {
  const a = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === '--manifest' || t === '-m') a.manifest = argv[++i];
    else if (t === '--out' || t === '-o') a.out = argv[++i];
    else if (t === '--ledger') a.ledger = argv[++i];
    else if (t === '--execute') a.execute = true;
    else if (t === '--enforce') a.enforce = true;
    else if (t === '--json') a.json = true;
    else if (t === '--self-test') a.selfTest = true;
    else if (t === '--help' || t === '-h') a.help = true;
    else a._.push(t);
  }
  return a;
}

const HELP = `execution-grounded-bon / rerank.mjs — execution-grounded best-of-N reranker

Usage:
  node rerank.mjs --manifest <file.json> [--execute] [--out verdict.json]
                  [--ledger log.jsonl] [--enforce] [--json]
  node rerank.mjs < manifest.json          # manifest on stdin
  node rerank.mjs --self-test              # run embedded assertions

Modes:
  precomputed (default) — manifest already carries candidates[].observations[]
  --execute             — run candidates[].cmd once per probe to build the matrix

Flags:
  --enforce   turn a low/none-confidence verdict into exit 2 (SHADOW-off by default)
  --ledger F  append a one-line JSONL shadow record to F
  --json      print only the verdict JSON (no human summary)

SHADOW mode (default): always exits 0, prints an advisory verdict, never blocks.`;

function runCli(argv) {
  const a = parseArgs(argv);
  if (a.help) { process.stdout.write(HELP + '\n'); return 0; }

  if (a.selfTest) {
    const r = selfTest();
    for (const t of r.results) process.stdout.write(`  ${t.pass ? 'PASS' : 'FAIL'}  ${t.name}\n`);
    const allPass = r.passed === r.total;
    process.stdout.write(`\n${allPass ? 'SUCCESS' : 'FAILED'}:rerank-selftest ${r.passed}/${r.total} assertions passed\n`);
    return allPass ? 0 : 1;
  }

  // load manifest
  let raw;
  try {
    raw = a.manifest ? readFileSync(a.manifest, 'utf8') : readFileSync(0, 'utf8');
  } catch (e) {
    process.stdout.write(`FAILED:rerank no manifest (${e.message})\n`);
    return a.enforce ? 2 : 0;
  }
  let manifest;
  try { manifest = JSON.parse(raw); }
  catch (e) {
    process.stdout.write(`FAILED:rerank bad JSON manifest (${e.message})\n`);
    return a.enforce ? 2 : 0;
  }

  let verdict;
  try { verdict = rerank(manifest, { execute: a.execute }); }
  catch (e) {
    // fail-open: a reranker crash must never block a real workflow
    process.stdout.write(`FAILED:rerank internal error (${e.message}) — SHADOW fail-open\n`);
    return a.enforce ? 2 : 0;
  }

  const line = {
    ts: new Date().toISOString(), task: verdict.task, mode: verdict.mode,
    winner: verdict.winner, winnerVendor: verdict.winnerVendor,
    winnerCluster: verdict.winnerCluster, confidence: verdict.confidence,
    nCandidates: verdict.nCandidates, nSurvivors: verdict.nSurvivors,
    knockedOut: verdict.knockedOut.map((k) => k.id), discrimination: verdict.discrimination,
  };
  if (a.ledger) { try { appendFileSync(a.ledger, JSON.stringify(line) + '\n'); } catch { /* fail-open */ } }
  if (a.out) { try { appendFileSync(a.out, JSON.stringify(verdict, null, 2) + '\n'); } catch { /* fail-open */ } }

  if (a.json) {
    process.stdout.write(JSON.stringify(verdict) + '\n');
  } else {
    process.stdout.write(`BON_RERANK task=${verdict.task ?? '-'} mode=${verdict.mode}\n`);
    process.stdout.write(`  candidates=${verdict.nCandidates} survivors=${verdict.nSurvivors} probes=${verdict.nProbes}\n`);
    for (const c of verdict.clusters) {
      process.stdout.write(`  cluster ${c.id} [${c.vendors.join('+')}] x${c.size}: ${c.members.join(', ')}${c.id === verdict.winnerCluster ? '  <= WINNER' : ''}\n`);
    }
    if (verdict.knockedOut.length) {
      for (const k of verdict.knockedOut) process.stdout.write(`  knockout ${k.id} (${k.vendor}): ${k.reason}\n`);
    }
    process.stdout.write(`  winner=${verdict.winner ?? '(none)'} vendor=${verdict.winnerVendor ?? '-'} confidence=${verdict.confidence} discrimination=${verdict.discrimination}\n`);
    for (const r of verdict.reasons) process.stdout.write(`  - ${r}\n`);
  }

  // terminal-state marker (AGENTS.md §4). SHADOW: the reranker SUCCEEDED at
  // producing a verdict; it never blocks. --enforce may escalate low confidence.
  // In --json mode the marker goes to stderr so stdout stays pure parseable JSON.
  const blocked = a.enforce && (verdict.confidence === 'none' || verdict.confidence === 'low');
  const marker = `${blocked ? 'FAILED' : 'SUCCESS'}:rerank-${verdict.task ?? 'unnamed'} winner=${verdict.winner ?? 'none'} confidence=${verdict.confidence}${blocked ? ' (enforce: low-confidence block)' : ''}\n`;
  (a.json ? process.stderr : process.stdout).write(marker);
  return blocked ? 2 : 0;
}

// run only when invoked directly (keeps functions importable for tests).
// realpathSync normalizes Windows slashes/case AND resolves symlinks — the skill
// vault is often symlinked, so a naive URL===argv[1] compare silently no-ops.
function invokedDirectly() {
  if (!process.argv[1]) return false;
  try {
    return realpathSync(fileURLToPath(import.meta.url)) === realpathSync(process.argv[1]);
  } catch {
    return false;
  }
}
if (invokedDirectly()) {
  process.exit(runCli(process.argv.slice(2)));
}
