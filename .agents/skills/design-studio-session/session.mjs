#!/usr/bin/env node
/**
 * session.mjs — the `design-studio session` interactive-modify capability (gem N.2).
 *
 * The interactive twin of the batch design-review-loop. It drives the owner + Claude
 * + Codex through ONE tight modify cycle per element, and it deliberately reuses the
 * SAME revert-gate, SAME audit-summary shape, and SAME loop-state.json scope as the
 * batch loop — so it consolidates the overlap instead of re-creating it (UIUX N.2 §89).
 *
 * The cycle (UIUX N.2 §2.2):
 *   PICK  (owner clicks a live element -> element->source picker resolves file:line)
 *   -> SUGGEST (Claude + Codex register N candidates, each a LIVE injected-style overlay FIRST)
 *   -> OVERLAY (preview every candidate BEFORE any source edit — reload = gone; reversible by construction)
 *   -> SELECT (Artifact gallery + one AskUserQuestion -> owner picks)
 *   -> APPLY  (one scoped micro-commit on a design/live-<id> branch — the picked file only)
 *   -> REAUDIT (incremental: changed screens only -> delta from the ui-audit summary)
 *   -> REVERT-GATE (shared revertDecision(): KEEP or REVERT) -> loop
 *
 * SAFETY / SHADOW (council C5 + build rails): the revert-gate is SHADOW by default —
 * it decides + logs + emits the recommended scoped git command but NEVER mutates the
 * repo itself. `apply` prints a scoped plan by default; `apply --commit` executes a
 * single-file scoped commit (execFile, no shell, the picked file ONLY — never `git add -A`).
 *
 * Dual-agent mingle (UIUX N.2 §92): Claude = driver/applier (holds the mcp_agent_mail
 * file-lease on the picked source); Codex = rival-suggester + INDEPENDENT re-auditor
 * (posts candidates + its own verdict, never edits the leased file). Candidates merge
 * attributed by:claude|codex; disagreement escalates to the owner. The verified win is
 * independent verification + candidate diversity — not debate-to-consensus.
 *
 * Subcommands:
 *   start | pick | suggest | overlay | gallery | select | apply | reaudit | revert | mingle | status
 *
 * Programmatic:
 *   import { scoreSummary, computeDelta, overlayStyle, buildGallery, loadRevertGate } from './session.mjs';
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { resolve, join, dirname } from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const SKILL_DIR = dirname(fileURLToPath(import.meta.url));
const SESSION_FILE = 'session-state.json';
const LOOP_FILE = 'loop-state.json';

const shortId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
const outDir = (out) => resolve(out || '.');
const sessionPath = (out) => join(outDir(out), SESSION_FILE);
const loopPath = (out) => join(outDir(out), LOOP_FILE);

function readJSON(p) {
  if (!existsSync(p)) return null;
  return JSON.parse(readFileSync(p, 'utf8'));
}
function writeJSON(p, obj) {
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, JSON.stringify(obj, null, 2));
  return p;
}

// ---------------------------------------------------------------------------
// The shared revert-gate (consolidation: prefer the batch loop's gate).
// ---------------------------------------------------------------------------

/**
 * The inline fallback — a byte-for-behaviour copy of design-review-loop's
 * revertDecision(). Used only when the sibling gate module cannot be resolved
 * (e.g. a standalone checkout). When the sibling loads, THAT one is used, so the
 * interactive and batch loops share one revert-gate.
 */
export function inlineRevert(m = {}) {
  const before = Number.isFinite(m.compositeBefore) ? m.compositeBefore : null;
  const after = Number.isFinite(m.compositeAfter) ? m.compositeAfter : null;
  const criticalBefore = m.criticalBefore ?? 0;
  const criticalAfter = m.criticalAfter ?? 0;
  const gatesGreen = m.gatesGreen !== false;
  const testsGreen = m.testsGreen !== false;
  const logicTouched = m.logicTouched === true;
  const logicApproved = m.logicApproved === true;

  const reasons = [];
  let regressed = false;
  if (before !== null && after !== null && after < before) {
    regressed = true;
    reasons.push(`composite regressed ${before} -> ${after} (after < before)`);
  }
  if (criticalAfter > criticalBefore) {
    regressed = true;
    reasons.push(`critical-error count rose ${criticalBefore} -> ${criticalAfter}`);
  }
  if (!gatesGreen) { regressed = true; reasons.push('contrast / focus / token gate is RED'); }
  if (!testsGreen) { regressed = true; reasons.push('tests / coverage gate is RED'); }
  if (logicTouched && !logicApproved) {
    regressed = true;
    reasons.push('apply-back re-touched state/routing/data (lossy for logic) and was not explicitly approved');
  }
  if (!regressed) {
    if (before !== null && after !== null && after > before) {
      reasons.push(`composite improved ${before} -> ${after} (+${(((after / before) - 1) * 100).toFixed(0)}%)`);
    } else {
      reasons.push('no tracked axis regressed; visual delta is safe to keep');
    }
  }
  return { decision: regressed ? 'REVERT' : 'KEEP', reasons, regressed };
}

/** Resolve the shared revert-gate, preferring the batch loop's canonical copy. */
export async function loadRevertGate() {
  const candidates = ['../design-studio/gates.mjs', '../design-review-loop/gates.mjs'];
  for (const rel of candidates) {
    try {
      const mod = await import(new URL(rel, import.meta.url).href);
      if (typeof mod.revertDecision === 'function') return { revertDecision: mod.revertDecision, source: rel };
    } catch { /* not present — try the next candidate */ }
  }
  return { revertDecision: inlineRevert, source: 'inline-fallback' };
}

// ---------------------------------------------------------------------------
// Incremental re-audit (delta.mjs, folded in): derive a deterministic composite
// proxy + critical-error count from the ui-audit `summary` shape so the shared
// revert-gate can arbitrate a changed screen without a full VLM critique pass.
// ---------------------------------------------------------------------------

/**
 * Deterministic 0-100 "cleanliness" proxy + critical-error count from a ui-audit
 * summary (run_audit.mjs aggregate().summary). Critical = functional breakage:
 * page crashes + non-actionable clicks + dead controls. The proxy is a penalty
 * roll-up; it never invents a score the numbers don't support.
 */
export function scoreSummary(summary = {}) {
  const s = summary.summary ? summary.summary : summary; // accept a full audit.json or a bare summary
  const pageErrors = s.pageErrors || 0;
  const clickErrors = s.clickErrors || 0;
  const deadControls = s.deadControls || 0;
  const axeViolations = s.axeViolations || 0;
  const spacing = (s.spacing && s.spacing.total) || 0;
  const affordance = (s.affordance && s.affordance.total) || 0;
  const motion = (s.motion && s.motion.total) || 0;
  const visualRegressions = s.visualRegressions || 0;

  const critical = pageErrors + clickErrors + deadControls;
  const penalty =
    5 * pageErrors + 4 * clickErrors + 3 * deadControls +
    2 * axeViolations + 1 * spacing + 1 * affordance + 1 * motion + 2 * visualRegressions;
  const composite = Math.max(0, Math.min(100, 100 - penalty));
  return { composite, critical, penalty };
}

/** Fold a before/after audit summary pair into the metrics revertDecision() expects. */
export function computeDelta(before, after, extra = {}) {
  const b = scoreSummary(before);
  const a = scoreSummary(after);
  return {
    compositeBefore: b.composite,
    compositeAfter: a.composite,
    criticalBefore: b.critical,
    criticalAfter: a.critical,
    gatesGreen: extra.gatesGreen !== false,
    testsGreen: extra.testsGreen !== false,
    logicTouched: extra.logicTouched === true,
    logicApproved: extra.logicApproved === true,
    penaltyBefore: b.penalty,
    penaltyAfter: a.penalty,
  };
}

// ---------------------------------------------------------------------------
// Overlay-preview (overlay.mjs, folded in): a candidate is an injected style tag
// on the running app BEFORE any source edit — reversible by construction.
// ---------------------------------------------------------------------------

const cssEscape = (v) => String(v).replace(/[<>]/g, ''); // keep injected CSS tag-free

/** The injectable style-tag markup for one candidate (data-candidate keyed = idempotent). */
export function overlayStyle(candidate = {}) {
  const cid = cssEscape(candidate.cid || 'c0');
  const by = cssEscape(candidate.by || 'claude');
  const selector = cssEscape(candidate.selector || '*');
  const css = cssEscape(candidate.css || '');
  return `<style data-candidate="${cid}" data-by="${by}">${selector} { ${css} }</style>`;
}

/**
 * The evaluate_script body that injects/replaces a candidate overlay on the live
 * page (run via chrome-devtools/playwright evaluate). Idempotent by data-candidate.
 * Reload removes it -> the revert-gate only ever arbitrates ACCEPTED (applied) edits.
 */
export function injectOverlaySnippet(candidate = {}) {
  const cid = cssEscape(candidate.cid || 'c0');
  const selector = cssEscape(candidate.selector || '*');
  const css = cssEscape(candidate.css || '');
  return [
    `(() => {`,
    `  const ID = ${JSON.stringify('ds-candidate-' + cid)};`,
    `  let el = document.getElementById(ID);`,
    `  if (!el) { el = document.createElement('style'); el.id = ID; document.head.appendChild(el); }`,
    `  el.setAttribute('data-candidate', ${JSON.stringify(cid)});`,
    `  el.textContent = ${JSON.stringify(selector + ' { ' + css + ' }')};`,
    `  return { injected: ID };`,
    `})()`,
  ].join('\n');
}

/** The evaluate_script body that clears every candidate overlay (preview teardown). */
export function clearOverlaysSnippet() {
  return `(() => { const n = document.querySelectorAll('style[id^="ds-candidate-"]'); n.forEach(e => e.remove()); return { cleared: n.length }; })()`;
}

// ---------------------------------------------------------------------------
// Element->source picker (react-dev-inspector-thin, rebuilt on evaluate): click
// resolves { selector, file, line, column, rect, computedStyle }. Deterministic,
// beats VLM Set-of-Mark guessing (the Cursor-2.0 / stagewise pattern).
// ---------------------------------------------------------------------------

/** Browser JS (for evaluate_script) that resolves the element under the pointer to its source. */
export function pickerScript() {
  return String.raw`(() => {
  function cssPath(el) {
    if (!(el instanceof Element)) return '';
    const parts = [];
    while (el && el.nodeType === 1 && parts.length < 8) {
      let sel = el.nodeName.toLowerCase();
      if (el.id) { sel += '#' + el.id; parts.unshift(sel); break; }
      const p = el.parentNode;
      if (p) {
        const same = [...p.children].filter(c => c.nodeName === el.nodeName);
        if (same.length > 1) sel += ':nth-of-type(' + (same.indexOf(el) + 1) + ')';
      }
      parts.unshift(sel);
      el = el.parentElement;
    }
    return parts.join(' > ');
  }
  function reactSource(el) {
    // react-dev-inspector / __source: _debugSource on the fiber carries {fileName,lineNumber,columnNumber}
    const key = Object.keys(el).find(k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'));
    let f = key ? el[key] : null;
    for (let i = 0; f && i < 12; i++) {
      const src = f._debugSource || (f.memoizedProps && f.memoizedProps.__source);
      if (src && src.fileName) return { file: src.fileName, line: src.lineNumber || null, column: src.columnNumber || null };
      f = f.return;
    }
    return null;
  }
  function inspectorAttr(el) {
    // code-inspector-plugin attrs: data-insp-path="file:line:column" (framework-agnostic)
    let node = el;
    for (let i = 0; node && i < 12; i++) {
      const p = node.getAttribute && (node.getAttribute('data-insp-path') || node.getAttribute('data-inspector-relative-path'));
      if (p) {
        const line = node.getAttribute('data-inspector-line');
        const col = node.getAttribute('data-inspector-column');
        const m = String(p).match(/^(.*?):(\d+):(\d+)$/);
        if (m) return { file: m[1], line: Number(m[2]), column: Number(m[3]) };
        return { file: p, line: line ? Number(line) : null, column: col ? Number(col) : null };
      }
      node = node.parentElement;
    }
    return null;
  }
  window.__dsPick = function (target) {
    const el = target || window.__dsLastEl || document.activeElement;
    if (!el) return { error: 'no element' };
    const src = reactSource(el) || inspectorAttr(el) || { file: null, line: null, column: null };
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const pick = ['color','backgroundColor','fontSize','fontWeight','lineHeight','padding','margin','borderRadius','display','gap'];
    const computedStyle = {};
    for (const k of pick) computedStyle[k] = cs[k];
    return {
      selector: cssPath(el),
      file: src.file, line: src.line, column: src.column,
      rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
      computedStyle,
    };
  };
  document.addEventListener('mousemove', (e) => { window.__dsLastEl = e.target; }, true);
  return { installed: true, usage: 'click an element then read window.__dsPick()' };
})()`;
}

// ---------------------------------------------------------------------------
// Selection gallery (gallery.mjs, folded in): the Artifact model = before + N
// candidates + predicted per-dimension deltas. Doubles as the iteration's doc page.
// ---------------------------------------------------------------------------

/** Build the gallery model (feeds an Artifact + one AskUserQuestion). */
export function buildGallery(session = {}) {
  const target = session.target || {};
  const options = (session.candidates || []).map((c) => ({
    cid: c.cid,
    by: c.by,
    label: `${c.cid} (by ${c.by})`,
    css: c.css,
    rationale: c.rationale || '',
    predictedDeltas: c.dims || {},
    overlay: overlayStyle(c),
  }));
  return {
    id: session.id,
    element: { selector: target.selector || null, file: target.file || null, line: target.line || null },
    baselineScreens: session.baselineScreens || [],
    options,
    // a "keep as-is" escape hatch is always offered so the owner is never forced to change
    question: {
      header: 'Pick a candidate',
      text: `Which restyle for ${target.selector || 'the selected element'}?`,
      choices: [...options.map((o) => o.label), 'keep as-is (no change)'],
    },
  };
}

// ---------------------------------------------------------------------------
// Dual-agent mingle protocol card (references/mingle-protocol.md, folded in).
// ---------------------------------------------------------------------------

/** The lease + role card for the Claude-driver / Codex-rival mingle over agent-mail. */
export function mingleCard(session = {}) {
  const file = (session.target && session.target.file) || '<picked source file>';
  return {
    session: session.id,
    leasedPath: file,
    roles: {
      claude: 'driver/applier — holds the mcp_agent_mail file-lease on the picked source; the ONLY writer of the apply-back micro-commit',
      codex: 'rival-suggester + INDEPENDENT re-auditor — posts candidates (by:codex) and its own delta verdict; NEVER edits the leased file',
    },
    protocol: [
      'Claude requests a file-lease on leasedPath (request_contact once, then file_reservation_paths).',
      'Both agents post candidates as attributed cards (by:claude|codex) into the same pool.',
      'Codex re-audits the applied change independently and posts its own KEEP/REVERT verdict.',
      'Agreement = the signal (cross-vendor independent failures); disagreement escalates to the owner, never auto-resolves to consensus.',
    ],
    cardSchema: { cid: 'string', by: 'claude|codex', selector: 'string', css: 'string', rationale: 'string', dims: '{dimension:+/-N}' },
  };
}

// ---------------------------------------------------------------------------
// Session state ops
// ---------------------------------------------------------------------------

export function startSession({ app, flow, url, repo, id, out } = {}) {
  const loop = readJSON(loopPath(out));
  const runId = id || shortId();
  const state = {
    id: `ds-session-${runId}`,
    app: app || (loop && loop.app) || null,
    flow: flow || (loop && loop.flow) || null,
    url: url || null,
    repo: repo || null,
    branch: `design/live-${runId}`,
    loopStateRef: loop ? loop.id : null,        // interoperate with the batch loop's state file
    sourceOfTruth: (loop && loop.sourceOfTruth) || 'repo',
    mode: 'session',                             // the interactive-modify specialization of G5<->G6
    target: null,
    candidates: [],
    selected: null,
    apply: null,
    delta: null,
    revert: null,
    baselineScreens: flow ? [flow] : (loop && loop.flow ? [loop.flow] : ['/']),
    history: [],
    createdAt: new Date().toISOString(),
  };
  return state;
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function requireSession(out) {
  const s = readJSON(sessionPath(out));
  if (!s) throw new Error(`no ${SESSION_FILE} in ${outDir(out)} — run \`session.mjs start\` first`);
  return s;
}
function save(out, s) { s.updatedAt = new Date().toISOString(); return writeJSON(sessionPath(out), s); }

function cmdStart(v) {
  const s = startSession(v);
  save(v.out, s);
  console.log(`[ds-session] started ${s.id}  app=${s.app || 'n/a'} flow=${s.flow || 'n/a'} branch=${s.branch}`);
  console.log(`[ds-session] scope inherited from loop-state: ${s.loopStateRef || '(none)'}  truth=${s.sourceOfTruth}`);
  console.log(`SUCCESS:${s.id}-start`);
}

function cmdPick(v) {
  if (v['emit-script']) { console.log(pickerScript()); console.log(`SUCCESS:ds-session-picker-script`); return; }
  const s = requireSession(v.out);
  const [file, line] = String(v.file || '').split(':');
  s.target = {
    selector: v.selector || null,
    file: file || null,
    line: line ? Number(line) : null,
    at: new Date().toISOString(),
  };
  s.history.push({ step: 'pick', selector: s.target.selector, file: s.target.file, at: s.target.at });
  save(v.out, s);
  console.log(`[ds-session] picked ${s.target.selector || '(no selector)'} -> ${s.target.file || '(no source)'}:${s.target.line || '?'}`);
  console.log(`SUCCESS:${s.id}-pick`);
}

function cmdSuggest(v) {
  const s = requireSession(v.out);
  const cid = v.cid || `c${s.candidates.length + 1}`;
  if (s.candidates.some((c) => c.cid === cid)) throw new Error(`candidate ${cid} already exists`);
  const dims = {};
  if (v.dims) for (const pair of String(v.dims).split(',')) {
    const [k, val] = pair.split(':');
    if (k) dims[k.trim()] = Number(val);
  }
  const cand = {
    cid,
    by: v.by === 'codex' ? 'codex' : 'claude',
    selector: v.selector || (s.target && s.target.selector) || '*',
    css: v.css || '',
    rationale: v.rationale || '',
    dims,
    logicTouched: v['logic-touched'] === true,
    at: new Date().toISOString(),
  };
  s.candidates.push(cand);
  s.history.push({ step: 'suggest', cid, by: cand.by, at: cand.at });
  save(v.out, s);
  console.log(`[ds-session] candidate ${cid} by ${cand.by}: ${cand.selector} { ${cand.css} }`);
  console.log(`[ds-session] overlay (preview BEFORE any edit): ${overlayStyle(cand)}`);
  console.log(`SUCCESS:${s.id}-suggest-${cid}`);
}

function cmdOverlay(v) {
  const s = requireSession(v.out);
  const c = (s.candidates || []).find((x) => x.cid === v.cid);
  if (!c) throw new Error(`no candidate ${v.cid}`);
  console.log(overlayStyle(c));
  console.log('--- evaluate_script inject ---');
  console.log(injectOverlaySnippet(c));
  console.log(`SUCCESS:${s.id}-overlay-${c.cid}`);
}

function cmdGallery(v) {
  const s = requireSession(v.out);
  const g = buildGallery(s);
  writeJSON(join(outDir(v.out), 'gallery.json'), g);
  console.log(JSON.stringify(g, null, 2));
  console.log(`SUCCESS:${s.id}-gallery`);
}

function cmdSelect(v) {
  const s = requireSession(v.out);
  if (v.cid === 'keep' || v.cid === 'none') {
    s.selected = null;
    s.history.push({ step: 'select', cid: 'keep-as-is', at: new Date().toISOString() });
    save(v.out, s);
    console.log(`[ds-session] owner kept as-is (no change) — cycle closes clean`);
    console.log(`SUCCESS:${s.id}-select-keep`);
    return;
  }
  const c = (s.candidates || []).find((x) => x.cid === v.cid);
  if (!c) throw new Error(`no candidate ${v.cid}`);
  s.selected = c.cid;
  s.history.push({ step: 'select', cid: c.cid, at: new Date().toISOString() });
  save(v.out, s);
  console.log(`[ds-session] selected ${c.cid} (by ${c.by})`);
  console.log(`SUCCESS:${s.id}-select-${c.cid}`);
}

function cmdApply(v) {
  const s = requireSession(v.out);
  if (!s.selected) throw new Error('nothing selected — run `select --cid <id>` first');
  const c = s.candidates.find((x) => x.cid === s.selected);
  const file = (s.target && s.target.file) || v.file;
  if (!file) throw new Error('no picked source file to commit — run `pick --file <path:line>` first');
  const msg = `design(session): ${c.cid} restyle ${c.selector} [by:${c.by}]`;
  const plan = [
    `git checkout -B ${s.branch}`,
    `git add ${file}`,               // SCOPED: the picked file ONLY — never `git add -A`
    `git commit -m ${JSON.stringify(msg)}`,
  ];
  s.apply = { cid: c.cid, file, branch: s.branch, message: msg, committed: false, sha: null, at: new Date().toISOString() };

  if (v.commit) {
    const repo = v.repo || s.repo;
    if (!repo) throw new Error('--commit needs --repo <path> (or a repo set at start)');
    const git = (...args) => execFileSync('git', ['-C', repo, ...args], { encoding: 'utf8' }).trim();
    git('checkout', '-B', s.branch);
    git('add', file);                // execFile array args — no shell, single-file scope
    git('commit', '-m', msg);
    s.apply.sha = git('rev-parse', 'HEAD');
    s.apply.committed = true;
    save(v.out, s);
    console.log(`[ds-session] scoped micro-commit ${s.apply.sha.slice(0, 8)} on ${s.branch} (file: ${file})`);
    console.log(`SUCCESS:${s.id}-apply-${c.cid}`);
    return;
  }
  save(v.out, s);
  console.log(`[ds-session] micro-commit PLAN (SHADOW — not executed; pass --commit --repo <path> to run):`);
  for (const line of plan) console.log(`  ${line}`);
  console.log(`SUCCESS:${s.id}-apply-plan-${c.cid}`);
}

function cmdReaudit(v) {
  const s = requireSession(v.out);
  const before = readJSON(resolve(v.before));
  const after = readJSON(resolve(v.after));
  if (!before || !after) throw new Error('--before and --after must be readable audit.json / summary files');
  const c = s.selected ? s.candidates.find((x) => x.cid === s.selected) : null;
  const delta = computeDelta(before, after, {
    gatesGreen: v['gates-red'] !== true,
    testsGreen: v['tests-red'] !== true,
    logicTouched: v['logic-touched'] === true || (c && c.logicTouched === true),
    logicApproved: v['logic-approved'] === true,
  });
  s.delta = delta;
  writeJSON(join(outDir(v.out), 'delta.json'), delta);
  save(v.out, s);
  console.log(`[ds-session] incremental re-audit (changed screens only):`);
  console.log(`  composite ${delta.compositeBefore} -> ${delta.compositeAfter}  |  critical ${delta.criticalBefore} -> ${delta.criticalAfter}`);
  console.log(`SUCCESS:${s.id}-reaudit`);
}

async function cmdRevert(v) {
  const s = requireSession(v.out);
  if (!s.delta) throw new Error('no delta — run `reaudit` first');
  const { revertDecision, source } = await loadRevertGate();
  const metrics = {
    ...s.delta,
    gatesGreen: v['gates-red'] === true ? false : s.delta.gatesGreen,
    testsGreen: v['tests-red'] === true ? false : s.delta.testsGreen,
    logicApproved: v['logic-approved'] === true || s.delta.logicApproved,
  };
  const res = revertDecision(metrics);
  s.revert = { ...res, gate: source, enforced: false, at: new Date().toISOString() };

  const revCmd = s.apply && s.apply.sha
    ? `git -C ${s.repo || '<repo>'} revert --no-edit ${s.apply.sha}`
    : `git -C ${s.repo || '<repo>'} checkout ${s.branch}~1 -- ${(s.target && s.target.file) || '<file>'}`;

  console.log(`[ds-session] G6 REVERT-GATE -> ${res.decision}  (gate: ${source})`);
  for (const r of res.reasons) console.log(`  - ${r}`);

  if (res.decision === 'REVERT') {
    // SHADOW by default: log + emit the scoped rollback command; never mutate the repo here.
    if (v.enforce && s.apply && s.apply.committed && (v.repo || s.repo) && s.apply.sha) {
      const repo = v.repo || s.repo;
      execFileSync('git', ['-C', repo, 'revert', '--no-edit', s.apply.sha], { encoding: 'utf8' });
      s.revert.enforced = true;
      save(v.out, s);
      console.log(`[ds-session] ENFORCED scoped revert of ${s.apply.sha.slice(0, 8)}`);
      console.error(`FAILED:${s.id}-revert reverted (${res.reasons.length} regression[s])`);
      process.exitCode = 1;
      return;
    }
    save(v.out, s);
    console.log(`[ds-session] SHADOW — recommended rollback (not executed): ${revCmd}`);
    console.log(`FAILED:${s.id}-revert regression detected — REVERT recommended (shadow)`);
    return;
  }
  save(v.out, s);
  console.log(`[ds-session] KEEP — the audit delta IS the evidence the change improved. Do not self-certify; Codex re-audits independently.`);
  console.log(`SUCCESS:${s.id}-revert-keep`);
}

function cmdMingle(v) {
  const s = requireSession(v.out);
  const card = mingleCard(s);
  writeJSON(join(outDir(v.out), 'mingle-card.json'), card);
  console.log(JSON.stringify(card, null, 2));
  console.log(`SUCCESS:${s.id}-mingle`);
}

function cmdStatus(v) {
  const s = requireSession(v.out);
  const steps = s.history.map((h) => h.step).join(' -> ') || '(none)';
  console.log(`[ds-session] ${s.id}  app=${s.app || 'n/a'} flow=${s.flow || 'n/a'} branch=${s.branch}`);
  console.log(`[ds-session] target=${(s.target && s.target.selector) || '(none)'}  candidates=${s.candidates.length}  selected=${s.selected || '(none)'}`);
  if (s.delta) console.log(`[ds-session] delta: composite ${s.delta.compositeBefore}->${s.delta.compositeAfter} critical ${s.delta.criticalBefore}->${s.delta.criticalAfter}`);
  if (s.revert) console.log(`[ds-session] revert-gate: ${s.revert.decision} (gate: ${s.revert.gate})`);
  console.log(`[ds-session] steps: ${steps}`);
  console.log(`SUCCESS:${s.id}-status`);
}

async function main() {
  const sub = process.argv[2];
  const { values } = parseArgs({
    args: process.argv.slice(3),
    options: {
      app: { type: 'string' }, flow: { type: 'string' }, url: { type: 'string' }, repo: { type: 'string' },
      id: { type: 'string' }, out: { type: 'string' },
      selector: { type: 'string' }, file: { type: 'string' }, cid: { type: 'string' }, by: { type: 'string' },
      css: { type: 'string' }, rationale: { type: 'string' }, dims: { type: 'string' },
      before: { type: 'string' }, after: { type: 'string' },
      commit: { type: 'boolean' }, enforce: { type: 'boolean' }, 'emit-script': { type: 'boolean' },
      'logic-touched': { type: 'boolean' }, 'logic-approved': { type: 'boolean' },
      'gates-red': { type: 'boolean' }, 'tests-red': { type: 'boolean' },
    },
    strict: false,
  });
  switch (sub) {
    case 'start': return cmdStart(values);
    case 'pick': return cmdPick(values);
    case 'suggest': return cmdSuggest(values);
    case 'overlay': return cmdOverlay(values);
    case 'gallery': return cmdGallery(values);
    case 'select': return cmdSelect(values);
    case 'apply': return cmdApply(values);
    case 'reaudit': return cmdReaudit(values);
    case 'revert': return cmdRevert(values);
    case 'mingle': return cmdMingle(values);
    case 'status': return cmdStatus(values);
    default:
      console.error('usage: session.mjs <start|pick|suggest|overlay|gallery|select|apply|reaudit|revert|mingle|status> [opts]');
      console.error('  start   --app <n> --flow </path> --url <url> [--repo <path>] [--out dir]');
      console.error('  pick    --selector <sel> --file <path:line> [--out dir] | pick --emit-script');
      console.error('  suggest --cid <id> --selector <sel> --css "<decls>" --by <claude|codex> [--dims "k:+1,..."] [--rationale ..] [--logic-touched]');
      console.error('  overlay --cid <id>   |   gallery   |   select --cid <id|keep>   |   mingle   |   status');
      console.error('  apply   [--commit --repo <path>]   (SHADOW plan by default; --commit does a SCOPED single-file commit)');
      console.error('  reaudit --before <audit.json> --after <audit.json> [--gates-red] [--tests-red] [--logic-approved]');
      console.error('  revert  [--enforce --repo <path>] [--gates-red] [--tests-red] [--logic-approved]   (SHADOW: logs + emits rollback cmd)');
      process.exitCode = 2;
  }
}

const __filename = fileURLToPath(import.meta.url);
if (process.argv[1] && resolve(process.argv[1]) === resolve(__filename)) {
  main().catch((err) => {
    console.error(`FAILED:ds-session ${err.message}`);
    process.exitCode = 1;
  });
}
