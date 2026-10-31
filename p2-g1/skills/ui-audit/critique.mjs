#!/usr/bin/env node
/**
 * critique.mjs — Track-B (design critique) harness CLI.
 *
 * Track-A (`run_audit.mjs`) SEES: it drives the app and emits `audit.json` (the
 * deterministic numbers) + screenshots. Track-B REASONS: Claude (the orchestrator)
 * views the screenshot and scores design quality against the rubric. This harness is
 * the plumbing between them — it never calls a model and never measures pixels.
 *
 *   assemble  — read audit.json + screenshot(s) + rubric (+ optional UIClip prior),
 *               project the numbers onto the nine design dimensions, surface the
 *               extended Track-A gate signals (Lighthouse/APCA/ARIA-diff/Equal-Access/
 *               Guidepup/Design2Code/Storybook) as SHADOW-advisory supplemental
 *               evidence, and write the critique INPUT for a chosen PERSONA
 *               (claude-critic default, or the cross-vendor codex-critic 5th persona).
 *   reconcile — merge two or more persona critique-output.json verdicts into ONE
 *               conservative cross-vendor CONSENSUS (per-dimension min-score); advisory
 *               only — it never blocks a merge or nags (Council C5 shadow law).
 *   validate  — type-check the verdict Claude produced against the OUTPUT schema and
 *               print the terminal-state marker SUCCESS:ui-critique-<id> / FAILED:….
 *   compute   — fill verdict.score from the §2.4 weighted composite (never free-hand).
 *   schema    — dump CRITIQUE_JSON_SCHEMA to critique.schema.json (keeps it in sync).
 *
 * CLI:
 *   node critique.mjs assemble --audit ./out/audit.json --screenshot ./out/home.png \
 *        --rubric ./critique_rubric.md [--uiclip ./out/uiclip.json] \
 *        [--persona codex-critic] [--dimension affordance] --out ./out
 *   node critique.mjs reconcile --inputs ./out/claude.json,./out/codex.json --out ./out
 *   node critique.mjs validate  --input ./out/critique-output.json
 *   node critique.mjs compute   --input ./out/critique-output.json [--dry-run]
 *   node critique.mjs schema    --out ./critique.schema.json
 *
 * Programmatic:
 *   import { assembleCritique, validateCritiqueFile, reconcilePersonaVerdicts } from './critique.mjs';
 */

import {
  readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync,
  appendFileSync, statSync, renameSync,
} from 'node:fs';
import { resolve, join, dirname } from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';
import { homedir } from 'node:os';
import { realpathSync } from 'node:fs';

import {
  assembleCritiqueInput, renderPromptMarkdown, validateCritique, CRITIQUE_JSON_SCHEMA,
  computeVerdict, SCORING_DIMENSIONS, DIMENSIONS, rankSeverity,
} from './critique_schema.mjs';

const SKILL_DIR = dirname(fileURLToPath(import.meta.url));
const DEFAULT_RUBRIC = join(SKILL_DIR, 'critique_rubric.md');

function readJson(path) {
  return JSON.parse(readFileSync(resolve(path), 'utf8'));
}

function readTextSafe(path) {
  try { return readFileSync(resolve(path), 'utf8'); } catch { return ''; }
}

/** Discover `<screen>.png` siblings of an audit.json when none are passed. */
function discoverScreenshots(auditPath) {
  const dir = dirname(resolve(auditPath));
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter(f => f.toLowerCase().endsWith('.png') && !f.includes('.diff.'))
    .map(f => join(dir, f));
}

// ---------------------------------------------------------------------------
// Personas — who is doing the reasoning. The DESIGN-EVAL v1 rubric is applied by
// Claude across four in-context reasoning lenses (visual-structure, accessibility,
// interaction, consistency); `codex-critic` is the FIFTH, independent, cross-vendor
// voice — an OpenAI Codex critic reached over the mounted `codex mcp-server`. Its
// value is INDEPENDENT failure modes: where a Claude verdict and a Codex verdict
// agree, that agreement is signal (execution-grounded-bon / feedback_peer_review:
// cross-model review preferred). The consensus is ADVISORY — never a merge gate.
// ---------------------------------------------------------------------------

export const PERSONAS = {
  'claude-critic': {
    id: 'claude-critic',
    vendor: 'anthropic',
    order: 1,
    role: 'primary in-context design critic',
    rail: 'this Claude session (views the screenshot directly)',
    lenses: ['visual-structure', 'accessibility', 'interaction', 'consistency'],
    note: 'Applies DESIGN-EVAL v1 across four reasoning lenses; the default persona.',
  },
  'codex-critic': {
    id: 'codex-critic',
    vendor: 'openai',
    order: 5,
    role: 'cross-vendor adversarial design critic (5th persona)',
    rail: 'mounted codex mcp-server (mcp__codex__codex / mcp__codex__codex-reply)',
    lenses: ['independent cross-vendor read'],
    note: 'The fifth voice alongside Claude\'s four lenses. Scores the SAME rubric independently; disagreements are surfaced, agreement is the signal. Advisory (Council C5).',
  },
};

export const DEFAULT_PERSONA = 'claude-critic';

/** Normalise/validate a persona id; unknown → default. */
export function resolvePersona(id) {
  if (!id) return PERSONAS[DEFAULT_PERSONA];
  return PERSONAS[id] || PERSONAS[DEFAULT_PERSONA];
}

// ---------------------------------------------------------------------------
// Shadow sink (Council C5-iii) — every NEW behaviour ships OFF→SHADOW: observe/log
// ONLY, never blocks, never nags. Logs go to a SEPARATE, bounded, auto-rotating sink
// (never the already-bloated main ledger). Fail-open: a logging error never changes
// control flow. Override the directory with UI_AUDIT_SHADOW_DIR (tests point it at a
// tmp dir). This is the anti-zombie contract the shadowed gates graduate against.
// ---------------------------------------------------------------------------

export const SHADOW_CONTRACT = {
  gate: 'ui-audit-extended-gates',
  mode: 'SHADOW',                       // observe/log only — never blocks, never nags
  promotionMetric: 'codex-critic↔claude-critic per-dimension agreement rate + supplemental-gate signal precision vs owner claude-reflect corrections',
  owner: 'darias.grama@gmail.com',
  graduationDeadline: '2026-08-11',     // 30 days; auto-RETIRE if unmet (no shadow limbo)
  fireRateHypothesis: 'codex-critic disagrees with claude-critic on ≤1 dimension per audit on ≥80% of runs; supplemental gates surface ≥1 real defect per 5 audits at <10% false-positive vs owner corrections',
};

const SHADOW_DIR = () => process.env.UI_AUDIT_SHADOW_DIR || join(homedir(), '.claude', 'gem-shadow');
const SHADOW_FILE = 'ui-critique-shadow.jsonl';
const SHADOW_MAX_BYTES = 256 * 1024;

/** Append one observe-only line to the bounded, rotating shadow sink. Fail-open. */
export function shadowLog(event, data = {}) {
  try {
    const dir = SHADOW_DIR();
    mkdirSync(dir, { recursive: true });
    const path = join(dir, SHADOW_FILE);
    try {
      if (existsSync(path) && statSync(path).size > SHADOW_MAX_BYTES) renameSync(path, path + '.1');
    } catch { /* rotation best-effort */ }
    appendFileSync(path, JSON.stringify({
      ts: new Date().toISOString(), skill: 'ui-audit', mode: 'SHADOW',
      contract: SHADOW_CONTRACT.gate, event, ...data,
    }) + '\n');
  } catch { /* shadow logging must never affect the run */ }
}

// ---------------------------------------------------------------------------
// Extended Track-A gate signals (SHADOW / advisory). These gates ride the same
// capture→audit.json→critique bus but are NOT yet routed into the deterministic
// §2.4 composite (that stays owned by critique_schema.projectFindingsByDimension so
// the headline math is unchanged). We surface them to the critic as supplemental,
// per-dimension-hinted, fully-traceable evidence so a persona can weigh them
// perceptually. The engine scripts that PRODUCE these arrays (lighthouse_gate.mjs,
// aria_diff.mjs, apca_lint.mjs, equal_access_scan.mjs, guidepup_gate.mjs,
// dual_theme+reflow capture, design2code_fidelity.mjs, storybook_a11y.mjs) ship as
// SEPARATE apply items; this consumer degrades to empty when a key is absent.
// ---------------------------------------------------------------------------

export const SUPPLEMENTAL_GATES = {
  lighthouse:  { label: 'Lighthouse (perf / Core-Web-Vitals / a11y)', gate: 'lighthouse',   dimHints: ['motion', 'visual-hierarchy'] },
  apca:        { label: 'APCA advisory contrast (WCAG-3 lightness-contrast)', gate: 'apca',  dimHints: ['color-contrast'] },
  ariaDiff:    { label: 'ARIA-snapshot a11y-tree diff', gate: 'aria-diff',                   dimHints: ['consistency', 'affordance'] },
  equalAccess: { label: 'IBM Equal Access (2nd a11y engine, cross-corroboration)', gate: 'equal-access', dimHints: ['color-contrast', 'affordance'] },
  guidepup:    { label: 'Guidepup real screen-reader (NVDA / VoiceOver)', gate: 'guidepup',  dimHints: ['affordance'] },
  design2code: { label: 'Design2Code mirror fidelity (code↔Figma drift)', gate: 'design2code', dimHints: ['consistency'] },
  storybook:   { label: 'Storybook 9 a11y (Vitest test-runner)', gate: 'storybook',          dimHints: ['affordance', 'consistency'] },
};

/**
 * Project the extended Track-A gate arrays onto advisory supplemental signals.
 * Reads the new top-level audit.json keys (empty/absent → skipped). Every item is
 * traceable by `ref`. SHADOW: advisory, not folded into the composite.
 * @returns {Array<{gate,label,count,shadow:true,dimHints:string[],items:object[]}>}
 */
export function projectSupplementalSignals(audit = {}) {
  const out = [];
  for (const [key, meta] of Object.entries(SUPPLEMENTAL_GATES)) {
    const raw = audit[key];
    if (!Array.isArray(raw) || raw.length === 0) continue;
    const items = raw.map((r, i) => ({
      ref: (r && (r.id || r.ref)) || `${meta.gate}-${i}`,
      screen: (r && r.screen) || 'unknown',
      severity: (r && r.severity) || 'info',
      value: r && (r.value ?? r.score ?? r.metric ?? ''),
      detail: (r && (r.detail || r.message || r.description)) || '',
    }));
    out.push({ gate: meta.gate, label: meta.label, count: items.length, shadow: true, dimHints: meta.dimHints, items });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Render the persona + supplemental markdown sections appended to the schema's brief.
// ---------------------------------------------------------------------------

function renderPersonaSection(persona) {
  if (!persona || persona.id === DEFAULT_PERSONA) return '';
  const L = [];
  L.push('');
  L.push(`## Persona: \`${persona.id}\` — ${persona.role}`);
  L.push(`- **Vendor:** ${persona.vendor}  ·  **Order:** #${persona.order}  ·  **Rail:** ${persona.rail}`);
  L.push(`- ${persona.note}`);
  if (persona.id === 'codex-critic') {
    L.push('- **How to run it:** hand THIS brief to Codex via the mounted `codex mcp-server` (`mcp__codex__codex`), instructing it to score the SAME DESIGN-EVAL v1 rubric INDEPENDENTLY and emit a `critique-output` JSON with `id: ui-critique-codex-<id>` and `persona: codex-critic`.');
    L.push('- **Then reconcile:** `node critique.mjs reconcile --inputs <claude-output>.json,<codex-output>.json --out <dir>` → a conservative min-score cross-vendor CONSENSUS. Cross-vendor agreement is the signal; disagreement lowers confidence, never inflates the score.');
  }
  L.push('- **SHADOW (Council C5):** this persona and its consensus are ADVISORY — they never block a merge, gate a PR, or nag. Observe + log only.');
  L.push('');
  return L.join('\n');
}

function renderSupplementalSection(signals) {
  if (!Array.isArray(signals) || signals.length === 0) return '';
  const L = [];
  L.push('');
  L.push('## Supplemental Track-A signals (SHADOW — advisory, NOT in the composite)');
  L.push('_These extended gates ride the same bus but are not routed into the deterministic §2.4 composite. Weigh them perceptually; cite by `ref`; do not let them silently move the headline score._');
  L.push('');
  for (const s of signals) {
    L.push(`### ${s.label} — ${s.count} signal(s) [${s.gate}] → hints: ${s.dimHints.join(', ')}`);
    for (const it of s.items) {
      L.push(`- \`${it.ref}\` (${it.severity}) ${it.screen}: ${it.value ?? ''} ${it.detail ? '— ' + it.detail : ''}`.trim());
    }
    L.push('');
  }
  return L.join('\n');
}

/**
 * Assemble the critique INPUT from Track-A artefacts.
 * @param {object} args
 * @param {string} args.auditPath   - Track-A audit.json path (required)
 * @param {string|string[]} [args.screenshots]
 * @param {string} [args.rubricPath]
 * @param {string} [args.uiclipPath]
 * @param {string} [args.out]
 * @param {string} [args.dimension] - one-dimension-per-call (§2.5)
 * @param {string} [args.persona]   - 'claude-critic' (default) | 'codex-critic'
 * @returns {{ input, paths: { inputJson, promptMd } }}
 */
export function assembleCritique({ auditPath, screenshots, rubricPath, uiclipPath, out, dimension, persona } = {}) {
  if (!auditPath) throw new Error('auditPath (Track-A audit.json) is required');
  const audit = readJson(auditPath);

  let shots = screenshots;
  if (!shots || (Array.isArray(shots) && shots.length === 0)) shots = discoverScreenshots(auditPath);
  if (typeof shots === 'string') shots = shots.split(',').map(s => s.trim()).filter(Boolean);

  const rubricText = readTextSafe(rubricPath || DEFAULT_RUBRIC);
  const uiclip = uiclipPath && existsSync(resolve(uiclipPath)) ? readJson(uiclipPath) : null;

  const input = assembleCritiqueInput({ audit, screenshots: shots, rubricText, uiclip, focusDimension: dimension || null });

  // ---- additive (in this scope; critique_schema.mjs is unchanged) ----
  const personaObj = resolvePersona(persona);
  const supplemental = projectSupplementalSignals(audit);
  input.persona = personaObj;
  input.supplementalSignals = supplemental;
  input.shadowContract = SHADOW_CONTRACT;

  const outDir = out ? resolve(out) : dirname(resolve(auditPath));
  mkdirSync(outDir, { recursive: true });
  // filename suffix: persona (non-default) then one-dimension-per-call (§2.5).
  const personaPart = personaObj.id !== DEFAULT_PERSONA ? `-${personaObj.id}` : '';
  const dimPart = input.focusDimension ? `-${input.focusDimension}` : '';
  const suffix = `${personaPart}${dimPart}`;
  const inputJson = join(outDir, `critique-input${suffix}.json`);
  const promptMd = join(outDir, `critique-input${suffix}.md`);

  const md = renderPromptMarkdown(input)
    + renderPersonaSection(personaObj)
    + renderSupplementalSection(supplemental);

  writeFileSync(inputJson, JSON.stringify(input, null, 2));
  writeFileSync(promptMd, md);

  shadowLog('assemble', {
    audit_id: input.audit_id, persona: personaObj.id, dimension: input.focusDimension || null,
    screenshots: input.screenshots.length, supplementalGates: supplemental.map(s => s.gate),
  });

  return { input, paths: { inputJson, promptMd } };
}

/** Validate a critique-output.json file. @returns {{ valid, errors, id }} */
export function validateCritiqueFile(path) {
  const obj = readJson(path);
  return validateCritique(obj);
}

/**
 * Compute the DESIGN-EVAL v1 weighted composite + critical-error cap from a critique
 * file's per-dimension scores and WRITE the headline back into `verdict` (score +
 * looksGood), so the headline is never free-handed (§2.4). Also stamps `verdict.eval`
 * with the full breakdown (composite/mean/criticalCount/shipGate/referenceGate).
 * @returns {{ obj, verdict }}
 */
export function computeVerdictFile(path, { write = true } = {}) {
  const obj = readJson(path);
  const cv = computeVerdict(obj.dimensions || []);
  if (write && cv.score != null) {
    obj.verdict = obj.verdict && typeof obj.verdict === 'object' ? obj.verdict : {};
    obj.verdict.score = cv.score;
    obj.verdict.looksGood = cv.looksGood;
    obj.verdict.eval = {
      composite: cv.composite, capped: cv.capped, mean: cv.mean, minScore: cv.minScore,
      criticalCount: cv.criticalCount, shipGate: cv.shipGate, referenceGate: cv.referenceGate,
    };
    writeFileSync(resolve(path), JSON.stringify(obj, null, 2));
  }
  return { obj, verdict: cv };
}

// ---------------------------------------------------------------------------
// Cross-vendor CONSENSUS — reconcile N persona verdicts into ONE, conservatively.
// Per scoring dimension: score = MIN across personas ("keep the lower score if they
// disagree", rubric §2.5), rating = WORST, confidence = LOWEST, findings = UNION,
// criticalError = OR (and a tripped critical forces score 0 per §2.3). The verdict is
// then re-derived by the SAME computeVerdict() the harness uses. Advisory — the
// consensus is never a blocking gate (Council C5).
// ---------------------------------------------------------------------------

const RATING_RANK = { fail: 3, warn: 2, pass: 1 };
const CONF_RANK = { low: 1, medium: 2, high: 3 };
const worseRating = (a, b) => ((RATING_RANK[b] || 0) > (RATING_RANK[a] || 0) ? b : a);
const lowerConf = (a, b) => ((CONF_RANK[b] || 99) < (CONF_RANK[a] || 99) ? b : a);

/**
 * Merge persona critique objects into one consensus critique object.
 * @param {object[]} critiques - each an assembled/validated critique-output shape
 * @returns {object} consensus critique-output (passes validateCritique)
 */
export function reconcilePersonaVerdicts(critiques = []) {
  const list = (critiques || []).filter(c => c && typeof c === 'object');
  const personas = [];
  const byDim = new Map();
  let audit_id = null, uiclip = null;

  for (const c of list) {
    const pid = (c.persona && (c.persona.id || c.persona)) || c.id || 'unknown';
    personas.push(String(pid));
    if (!audit_id && c.audit_id) audit_id = c.audit_id;
    if (uiclip == null && c.uiclip) uiclip = c.uiclip;

    for (const d of (c.dimensions || [])) {
      if (!d || !DIMENSIONS.includes(d.dimension)) continue;
      const cur = byDim.get(d.dimension) || {
        dimension: d.dimension, score: undefined, rating: 'pass', confidence: 'high',
        findings: [], criticalError: false, _seen: new Set(),
      };
      if (typeof d.score === 'number') cur.score = (cur.score === undefined) ? d.score : Math.min(cur.score, d.score);
      if (d.rating) cur.rating = worseRating(cur.rating, d.rating);
      if (d.confidence) cur.confidence = lowerConf(cur.confidence, d.confidence);
      for (const f of (d.findings || [])) {
        const k = `${f.severity}|${f.evidence}`;
        if (!cur._seen.has(k)) { cur._seen.add(k); cur.findings.push({ ...f }); }
      }
      cur.criticalError = cur.criticalError || d.criticalError === true
        || (d.findings || []).some(f => f && f.severity === 'critical');
      byDim.set(d.dimension, cur);
    }
  }

  const dimensions = [];
  for (const d of byDim.values()) {
    const isScoring = SCORING_DIMENSIONS.includes(d.dimension);
    let score = d.score;
    if (d.criticalError) score = 0;                 // §2.3 critical-error override
    if (isScoring && score === undefined) continue; // nobody scored this scoring dim → omit
    const entry = { dimension: d.dimension, rating: d.rating, confidence: d.confidence, findings: d.findings };
    if (isScoring || typeof score === 'number') entry.score = score;
    if (d.criticalError) entry.criticalError = true;
    dimensions.push(entry);
  }

  const cv = computeVerdict(dimensions);
  const n = personas.length;

  // Prioritised findings: union of critical+high, ranked by severity.
  const prioritizedFindings = [];
  for (const dim of dimensions) {
    for (const f of dim.findings) {
      if (f.severity === 'critical' || f.severity === 'high') {
        prioritizedFindings.push({
          dimension: dim.dimension, severity: f.severity,
          evidence: f.evidence, recommendation: f.recommendation || 'Address the flagged issue.',
        });
      }
    }
  }
  prioritizedFindings.sort((a, b) => rankSeverity(b.severity) - rankSeverity(a.severity));
  prioritizedFindings.forEach((p, i) => { p.rank = i + 1; });

  const score = cv.score == null ? 0 : cv.score;
  const looksGood = cv.looksGood || 'needs-work';
  const headline = `Cross-vendor consensus of ${n} persona(s): ${looksGood} (score ${score}).`;
  const summary = `Conservative min-score merge across [${personas.join(', ')}]. `
    + `${cv.criticalCount || 0} critical dimension(s); mean ${cv.mean ?? 'n/a'}, min ${cv.minScore ?? 'n/a'}. `
    + `ADVISORY (Council C5) — this consensus never blocks or nags.`;

  return {
    id: 'ui-critique-consensus',
    audit_id: audit_id || 'ui-audit-unknown',
    personas,
    verdict: {
      looksGood, score, headline, summary,
      eval: {
        composite: cv.composite, capped: cv.capped, mean: cv.mean, minScore: cv.minScore,
        criticalCount: cv.criticalCount, shipGate: cv.shipGate, referenceGate: cv.referenceGate,
      },
    },
    dimensions,
    prioritizedFindings,
    uiclip: uiclip ?? null,
  };
}

/**
 * Read N persona critique-output files, reconcile them, and write the consensus.
 * @returns {{ obj, path, valid, errors }}
 */
export function reconcileCritiqueFiles(paths = [], { out } = {}) {
  const files = (paths || []).filter(Boolean);
  if (files.length < 2) throw new Error('reconcile needs at least two --inputs critique files');
  const critiques = files.map(readJson);
  const obj = reconcilePersonaVerdicts(critiques);
  const outDir = out ? resolve(out) : dirname(resolve(files[0]));
  mkdirSync(outDir, { recursive: true });
  const path = join(outDir, 'critique-consensus.json');
  writeFileSync(path, JSON.stringify(obj, null, 2));
  const { valid, errors } = validateCritique(obj);
  shadowLog('reconcile', { audit_id: obj.audit_id, personas: obj.personas, score: obj.verdict.score, valid });
  return { obj, path, valid, errors };
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function cmdAssemble(values) {
  const { input, paths } = assembleCritique({
    auditPath: values.audit,
    screenshots: values.screenshot,
    rubricPath: values.rubric,
    uiclipPath: values.uiclip,
    out: values.out,
    dimension: values.dimension,
    persona: values.persona,
  });
  if (input.persona && input.persona.id !== DEFAULT_PERSONA) {
    console.log(`[critique] persona → ${input.persona.id} (#${input.persona.order}, ${input.persona.vendor}) via ${input.persona.rail}`);
  }
  if (input.focusDimension) console.log(`[critique] single-dimension mode → ${input.focusDimension} (weight ${input.dimensionWeights[input.focusDimension]})`);
  const counts = Object.entries(input.evidenceByDimension)
    .map(([d, ev]) => `${d}:${ev.length}`).join('  ');
  console.log(`[critique] audit=${input.audit_id}  screenshots=${input.screenshots.length}`);
  console.log(`[critique] evidence by dimension → ${counts}`);
  if (input.supplementalSignals.length) {
    console.log(`[critique] supplemental (SHADOW) → ${input.supplementalSignals.map(s => `${s.gate}:${s.count}`).join('  ')}`);
  }
  console.log(`[critique] INPUT  → ${paths.inputJson}`);
  console.log(`[critique] PROMPT → ${paths.promptMd}`);
  if (input.screenshots.length === 0) {
    console.log('[critique] WARN: no screenshots found — critic must judge from numbers only.');
  }
  console.log('\nNext: view the screenshot(s), fill the verdict per outputSchema, then `node critique.mjs validate --input <file>`.');
  console.log('SUCCESS:ui-critique-assemble');
}

function cmdReconcile(values) {
  const inputs = (values.inputs || '').split(',').map(s => s.trim()).filter(Boolean);
  const { obj, path, valid, errors } = reconcileCritiqueFiles(inputs, { out: values.out });
  console.log(`[critique] consensus of [${obj.personas.join(', ')}] → ${path}`);
  console.log(`[critique] verdict: ${obj.verdict.looksGood} score=${obj.verdict.score} critical=${obj.verdict.eval.criticalCount} (ADVISORY — never blocks)`);
  if (!valid) {
    for (const e of errors) console.error(`  - ${e}`);
    console.error(`FAILED:ui-critique-consensus ${errors.length} schema violation(s)`);
    process.exitCode = 1;
    return;
  }
  console.log('SUCCESS:ui-critique-consensus');
}

function cmdValidate(values) {
  if (!values.input) throw new Error('--input <critique-output.json> required');
  const { valid, errors, id } = validateCritiqueFile(values.input);
  const tag = id || 'ui-critique-unknown';
  if (valid) {
    console.log(`[critique] verdict OK (${tag})`);
    console.log(`SUCCESS:${tag}`);
    return;
  }
  for (const e of errors) console.error(`  - ${e}`);
  console.error(`FAILED:${tag} ${errors.length} schema violation(s)`);
  process.exitCode = 1;
}

function cmdCompute(values) {
  if (!values.input) throw new Error('--input <critique-output.json> required');
  const { verdict } = computeVerdictFile(values.input, { write: values['dry-run'] !== true });
  if (verdict.score == null) {
    console.error('FAILED:ui-critique-compute no scored dimensions to composite');
    process.exitCode = 1;
    return;
  }
  console.log(`[critique] composite=${verdict.composite} → capped=${verdict.capped} → score=${verdict.score}  looksGood=${verdict.looksGood}`);
  console.log(`[critique] mean=${verdict.mean}  minScore=${verdict.minScore}  critical=${verdict.criticalCount}  ship=${verdict.shipGate}  reference=${verdict.referenceGate}`);
  if (values['dry-run'] !== true) console.log(`[critique] wrote verdict back → ${resolve(values.input)}`);
  console.log('SUCCESS:ui-critique-compute');
}

function cmdSchema(values) {
  const outPath = values.out ? resolve(values.out) : join(SKILL_DIR, 'critique.schema.json');
  writeFileSync(outPath, JSON.stringify(CRITIQUE_JSON_SCHEMA, null, 2));
  console.log(`[critique] wrote JSON schema → ${outPath}`);
  console.log('SUCCESS:ui-critique-schema');
}

function main() {
  const sub = process.argv[2];
  const { values } = parseArgs({
    args: process.argv.slice(3),
    options: {
      audit: { type: 'string' },
      screenshot: { type: 'string' },
      rubric: { type: 'string' },
      uiclip: { type: 'string' },
      input: { type: 'string' },
      inputs: { type: 'string' },
      out: { type: 'string' },
      dimension: { type: 'string' },
      persona: { type: 'string' },
      'dry-run': { type: 'boolean' },
    },
    strict: false,
  });

  switch (sub) {
    case 'assemble': return cmdAssemble(values);
    case 'reconcile': return cmdReconcile(values);
    case 'validate': return cmdValidate(values);
    case 'compute': return cmdCompute(values);
    case 'schema': return cmdSchema(values);
    default:
      console.error('usage: critique.mjs <assemble|reconcile|validate|compute|schema> [opts]');
      console.error('  assemble  --audit <audit.json> [--screenshot a.png,b.png] [--rubric r.md] [--uiclip u.json] [--persona claude-critic|codex-critic] [--dimension <name>] [--out dir]');
      console.error('  reconcile --inputs <claude-output>.json,<codex-output>.json [--out dir]   # cross-vendor consensus (advisory)');
      console.error('  validate  --input <critique-output.json>');
      console.error('  compute   --input <critique-output.json> [--dry-run]   # fill verdict.score from the weighted composite');
      console.error('  schema    [--out critique.schema.json]');
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
    console.error(`FAILED:ui-critique ${err.message}`);
    process.exitCode = 1;
  }
}
