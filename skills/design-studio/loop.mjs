#!/usr/bin/env node
/**
 * loop.mjs — the TCR Loop orchestrator harness (G0 PRIME .. G7 VERIFY -> back to G1).
 *
 * THIS HARNESS IS PURE PLUMBING. It never calls a model, never measures pixels, and
 * never edits app source. It tracks WHICH gate a design-review pass is on, prints the
 * gate's canonical named method + leaf skill + standard question bank, advances the
 * loop with ordering checks, and runs the G6 revert-gate decision. The actual work of
 * each gate lives in the leaf skills (ui-audit, transpose-to-figma, critique-panel,
 * figma-implement-design, ...). The orchestrator only sequences them and holds the
 * question banks.
 *
 * Subcommands:
 *   init      — start a loop pass; write loop-state.json at G0 with scope + source-of-truth.
 *   gate      — show the current (or named) gate: method + leaf skill + question bank + the
 *               next-tool hint. Emits SUCCESS:design-review-<gate>-<id>.
 *   advance   — move to the next gate (ordering-checked; G7 -> G1). Records the gate as done.
 *   revert    — the G6 revert-gate: decide KEEP or REVERT from before/after audit metrics.
 *               Emits SUCCESS:design-review-G6-<id> (KEEP) / FAILED:... (REVERT).
 *   status    — print the loop-state.json (current gate, history, scope).
 *   questions — dump just a gate's standard question bank.
 *
 * CLI:
 *   node loop.mjs init --app reframe --flow /editor --truth repo --altitude system --out ./dr-out
 *   node loop.mjs gate [--gate G3] [--out ./dr-out]
 *   node loop.mjs advance [--out ./dr-out]
 *   node loop.mjs revert --before 62 --after 81 --critical-before 2 --critical-after 0 \
 *        --gates-green --tests-green [--logic-touched] [--logic-approved] [--out ./dr-out]
 *   node loop.mjs status   [--out ./dr-out]
 *   node loop.mjs questions --gate G1
 *
 * Programmatic: import { initPass, renderGate, advancePass, runRevert } from './loop.mjs';
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync, realpathSync } from 'node:fs';
import { resolve, join, dirname } from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';

import { GATES, GATE_ORDER, nextGate, isGate, revertDecision } from './gates.mjs';

const SKILL_DIR = dirname(fileURLToPath(import.meta.url));
const STATE_FILE = 'loop-state.json';

const shortId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
const statePath = (out) => join(resolve(out || '.'), STATE_FILE);

function readState(out) {
  const p = statePath(out);
  if (!existsSync(p)) return null;
  return JSON.parse(readFileSync(p, 'utf8'));
}

function writeState(out, state) {
  const dir = resolve(out || '.');
  mkdirSync(dir, { recursive: true });
  writeFileSync(statePath(out), JSON.stringify(state, null, 2));
  return statePath(out);
}

// ---------------------------------------------------------------------------
// Core (programmatic)
// ---------------------------------------------------------------------------

/** Start a loop pass at G0 PRIME. */
export function initPass({ app, flow, truth, altitude, id } = {}) {
  const runId = id || shortId();
  const state = {
    id: `design-review-${runId}`,
    app: app || null,
    flow: flow || null,
    sourceOfTruth: truth || 'repo', // default repo-native for code-first apps
    altitude: altitude || 'unknown', // system | audit | unknown
    currentGate: 'G0',
    pass: 1,
    history: [], // [{ gate, name, at }]
    createdAt: new Date().toISOString(),
  };
  return state;
}

/** Render a gate brief (method + skill + emits + question bank + next hint). */
export function renderGate(state, gate) {
  const g = gate || state.currentGate;
  if (!isGate(g)) throw new Error(`unknown gate: ${g}`);
  const def = GATES[g];
  const edgeLabel = def.edge ? `  [${def.edge} edge]` : '';
  const lines = [];
  lines.push(`=== ${def.id} ${def.name}${edgeLabel} — pass ${state.pass} of ${state.id} ===`);
  lines.push(`Method   : ${def.method}`);
  lines.push(`Leaf skill: ${def.skill}`);
  lines.push(`Emits    : ${def.emits}`);
  lines.push('Standard questions:');
  for (const q of def.questions) lines.push(`  - ${q}`);
  lines.push(`Next gate : ${nextGate(g)}`);
  return { gate: g, def, text: lines.join('\n') };
}

/** Advance the pass to the next gate (ordering-checked). */
export function advancePass(state) {
  const from = state.currentGate;
  const to = nextGate(from);
  const next = { ...state };
  next.history = [...state.history, { gate: from, name: GATES[from].name, at: new Date().toISOString() }];
  next.currentGate = to;
  if (from === 'G7') next.pass = state.pass + 1; // wrapped: new cycle
  return next;
}

/** The G6 revert-gate. Returns the decision plus a re-anchored summary. */
export function runRevert(metrics) {
  return revertDecision(metrics);
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function requireState(out) {
  const s = readState(out);
  if (!s) throw new Error(`no ${STATE_FILE} in ${resolve(out || '.')} — run \`loop.mjs init\` first`);
  return s;
}

function cmdInit(v) {
  const state = initPass({ app: v.app, flow: v.flow, truth: v.truth, altitude: v.altitude, id: v.id });
  const p = writeState(v.out, state);
  console.log(`[dr] pass started: ${state.id}`);
  console.log(`[dr] app=${state.app || 'n/a'} flow=${state.flow || 'n/a'} truth=${state.sourceOfTruth} altitude=${state.altitude}`);
  console.log(`[dr] STATE -> ${p}`);
  console.log(renderGate(state, 'G0').text);
  console.log(`SUCCESS:${state.id}-G0`);
}

function cmdGate(v) {
  const state = requireState(v.out);
  const { gate, text } = renderGate(state, v.gate);
  console.log(text);
  console.log(`SUCCESS:${state.id}-${gate}`);
}

function cmdAdvance(v) {
  const state = requireState(v.out);
  const from = state.currentGate;
  const next = advancePass(state);
  writeState(v.out, next);
  console.log(`[dr] advanced ${from} (${GATES[from].name}) -> ${next.currentGate} (${GATES[next.currentGate].name})  pass=${next.pass}`);
  console.log(renderGate(next, next.currentGate).text);
  console.log(`SUCCESS:${state.id}-${from}`);
}

function cmdRevert(v) {
  const state = readState(v.out); // optional — revert can run standalone
  const id = (state && state.id) || `design-review-${shortId()}`;
  const metrics = {
    compositeBefore: v.before != null ? Number(v.before) : undefined,
    compositeAfter: v.after != null ? Number(v.after) : undefined,
    criticalBefore: v['critical-before'] != null ? Number(v['critical-before']) : 0,
    criticalAfter: v['critical-after'] != null ? Number(v['critical-after']) : 0,
    gatesGreen: v['gates-green'] === true ? true : (v['gates-red'] === true ? false : true),
    testsGreen: v['tests-green'] === true ? true : (v['tests-red'] === true ? false : true),
    logicTouched: v['logic-touched'] === true,
    logicApproved: v['logic-approved'] === true,
  };
  const { decision, reasons, regressed } = runRevert(metrics);
  console.log(`[dr] G6 REVERT-GATE -> ${decision}`);
  for (const r of reasons) console.log(`  - ${r}`);
  if (decision === 'KEEP') {
    console.log('[dr] keep the reversible commit; the audit delta IS the evidence the change improved.');
    console.log(`SUCCESS:${id}-G6`);
  } else {
    console.log('[dr] REVERT the commit (git + token diff rollback); re-branch and re-iterate. Do not self-certify.');
    console.error(`FAILED:${id}-G6 ${reasons.length} regression(s) — reverted`);
    process.exitCode = 1;
  }
}

function cmdStatus(v) {
  const state = requireState(v.out);
  const done = state.history.map((h) => h.gate).join(' -> ') || '(none)';
  console.log(`[dr] ${state.id}`);
  console.log(`[dr] app=${state.app || 'n/a'} flow=${state.flow || 'n/a'} truth=${state.sourceOfTruth} altitude=${state.altitude}`);
  console.log(`[dr] current=${state.currentGate} (${GATES[state.currentGate].name})  pass=${state.pass}`);
  console.log(`[dr] completed: ${done}`);
  console.log(`SUCCESS:${state.id}-status`);
}

function cmdQuestions(v) {
  const g = v.gate;
  if (!isGate(g)) throw new Error(`--gate must be one of ${GATE_ORDER.join(',')}`);
  const def = GATES[g];
  console.log(`${def.id} ${def.name} — ${def.method}`);
  for (const q of def.questions) console.log(`  - ${q}`);
  console.log(`SUCCESS:design-review-${g}-questions`);
}

function main() {
  const sub = process.argv[2];
  const { values } = parseArgs({
    args: process.argv.slice(3),
    options: {
      app: { type: 'string' }, flow: { type: 'string' }, truth: { type: 'string' },
      altitude: { type: 'string' }, id: { type: 'string' }, gate: { type: 'string' }, out: { type: 'string' },
      before: { type: 'string' }, after: { type: 'string' },
      'critical-before': { type: 'string' }, 'critical-after': { type: 'string' },
      'gates-green': { type: 'boolean' }, 'gates-red': { type: 'boolean' },
      'tests-green': { type: 'boolean' }, 'tests-red': { type: 'boolean' },
      'logic-touched': { type: 'boolean' }, 'logic-approved': { type: 'boolean' },
    },
    strict: false,
  });

  switch (sub) {
    case 'init': return cmdInit(values);
    case 'gate': return cmdGate(values);
    case 'advance': return cmdAdvance(values);
    case 'revert': return cmdRevert(values);
    case 'status': return cmdStatus(values);
    case 'questions': return cmdQuestions(values);
    default:
      console.error('usage: loop.mjs <init|gate|advance|revert|status|questions> [opts]');
      console.error('  init      --app <name> --flow </path> --truth <repo|figma> --altitude <system|audit> [--out dir]');
      console.error('  gate      [--gate G0..G7] [--out dir]');
      console.error('  advance   [--out dir]');
      console.error('  revert    --before N --after N [--critical-before N] [--critical-after N] [--gates-red] [--tests-red] [--logic-touched] [--logic-approved] [--out dir]');
      console.error('  status    [--out dir]');
      console.error('  questions --gate G0..G7');
      process.exitCode = 2;
  }
}

const __filename = fileURLToPath(import.meta.url);
// Junction/symlink-safe main-module check. `~/.claude/skills` is a junction to
// `skills.daily`; Node resolves symlinks for ESM so import.meta.url reports the REAL
// path while resolve(argv[1]) stays lexical. A lexical compare therefore NEVER matched
// on the documented `~/.claude/skills/...` invocation and main() silently never ran
// (exit 0, no output, no artifacts). realpathSync.native also collapses 8.3 short
// names (PREKZU~1), which realpathSync does not.
const __isMain = (a, b) => {
  try { return realpathSync.native(a) === realpathSync.native(b); }
  catch { return resolve(a) === resolve(b); }
};
if (process.argv[1] && __isMain(process.argv[1], __filename)) {
  try {
    main();
  } catch (err) {
    console.error(`FAILED:design-review-loop ${err.message}`);
    process.exitCode = 1;
  }
}
