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
 *               project the numbers onto the eight design dimensions, and write the
 *               critique INPUT (critique-input.json + critique-input.md) for Claude.
 *   validate  — type-check the verdict Claude produced against the OUTPUT schema and
 *               print the terminal-state marker SUCCESS:ui-critique-<id> / FAILED:….
 *   schema    — dump CRITIQUE_JSON_SCHEMA to critique.schema.json (keeps it in sync).
 *
 * CLI:
 *   node critique.mjs assemble --audit ./out/audit.json --screenshot ./out/home.png \
 *        --rubric ./critique_rubric.md [--uiclip ./out/uiclip.json] --out ./out
 *   node critique.mjs validate --input ./out/critique-output.json
 *   node critique.mjs schema --out ./critique.schema.json
 *
 * Programmatic:
 *   import { assembleCritique, validateCritiqueFile } from './critique.mjs';
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'node:fs';
import { resolve, join, dirname, basename } from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';

import {
  assembleCritiqueInput, renderPromptMarkdown, validateCritique, CRITIQUE_JSON_SCHEMA,
  computeVerdict,
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

/**
 * Assemble the critique INPUT from Track-A artefacts.
 * @returns {{ input, paths: { inputJson, promptMd } }}
 */
export function assembleCritique({ auditPath, screenshots, rubricPath, uiclipPath, out, dimension } = {}) {
  if (!auditPath) throw new Error('auditPath (Track-A audit.json) is required');
  const audit = readJson(auditPath);

  let shots = screenshots;
  if (!shots || (Array.isArray(shots) && shots.length === 0)) shots = discoverScreenshots(auditPath);
  if (typeof shots === 'string') shots = shots.split(',').map(s => s.trim()).filter(Boolean);

  const rubricText = readTextSafe(rubricPath || DEFAULT_RUBRIC);
  const uiclip = uiclipPath && existsSync(resolve(uiclipPath)) ? readJson(uiclipPath) : null;

  const input = assembleCritiqueInput({ audit, screenshots: shots, rubricText, uiclip, focusDimension: dimension || null });

  const outDir = out ? resolve(out) : dirname(resolve(auditPath));
  mkdirSync(outDir, { recursive: true });
  // One-dimension-per-call (§2.5) writes a dimension-scoped brief alongside the full one.
  const suffix = input.focusDimension ? `-${input.focusDimension}` : '';
  const inputJson = join(outDir, `critique-input${suffix}.json`);
  const promptMd = join(outDir, `critique-input${suffix}.md`);
  writeFileSync(inputJson, JSON.stringify(input, null, 2));
  writeFileSync(promptMd, renderPromptMarkdown(input));

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
  });
  if (input.focusDimension) console.log(`[critique] single-dimension mode → ${input.focusDimension} (weight ${input.dimensionWeights[input.focusDimension]})`);
  const counts = Object.entries(input.evidenceByDimension)
    .map(([d, ev]) => `${d}:${ev.length}`).join('  ');
  console.log(`[critique] audit=${input.audit_id}  screenshots=${input.screenshots.length}`);
  console.log(`[critique] evidence by dimension → ${counts}`);
  console.log(`[critique] INPUT  → ${paths.inputJson}`);
  console.log(`[critique] PROMPT → ${paths.promptMd}`);
  if (input.screenshots.length === 0) {
    console.log('[critique] WARN: no screenshots found — critic must judge from numbers only.');
  }
  console.log('\nNext: view the screenshot(s), fill the verdict per outputSchema, then `node critique.mjs validate --input <file>`.');
  console.log('SUCCESS:ui-critique-assemble');
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
      out: { type: 'string' },
      dimension: { type: 'string' },
      'dry-run': { type: 'boolean' },
    },
    strict: false,
  });

  switch (sub) {
    case 'assemble': return cmdAssemble(values);
    case 'validate': return cmdValidate(values);
    case 'compute': return cmdCompute(values);
    case 'schema': return cmdSchema(values);
    default:
      console.error('usage: critique.mjs <assemble|validate|compute|schema> [opts]');
      console.error('  assemble --audit <audit.json> [--screenshot a.png,b.png] [--rubric r.md] [--uiclip u.json] [--dimension <name>] [--out dir]');
      console.error('  validate --input <critique-output.json>');
      console.error('  compute  --input <critique-output.json> [--dry-run]   # fill verdict.score from the weighted composite');
      console.error('  schema   [--out critique.schema.json]');
      process.exitCode = 2;
  }
}

const __filename = fileURLToPath(import.meta.url);
if (process.argv[1] && resolve(process.argv[1]) === resolve(__filename)) {
  try {
    main();
  } catch (err) {
    console.error(`FAILED:ui-critique ${err.message}`);
    process.exitCode = 1;
  }
}
