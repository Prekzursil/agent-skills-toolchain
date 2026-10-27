#!/usr/bin/env node
/**
 * critique_panel.mjs — G3 CRITIQUE multi-agent panel harness CLI.
 *
 * The panel runs the SAME two-track contract as ui-audit: Track-A (`ui-audit`) SEES
 * (drives the app, emits `audit.json` + screenshots); this skill is Track-B's
 * multi-persona CRITIQUE. Four named heuristic personas each REASON over the SAME
 * pre-computed numbers + the screenshot, then `synthesize` dedupes + ranks them.
 * This harness is pure plumbing — it never calls a model and never measures pixels.
 *
 *   assemble    — read audit.json + screenshot(s) + rubric, route the numbers onto
 *                 each persona's owned dimensions, and write FOUR persona briefs
 *                 (one .json + one .md each) for the critic to fill.
 *   validate    — type-check a persona verdict (incl. the quota gate) and print
 *                 SUCCESS:critique-panel-<persona>-<id> / FAILED:….
 *   synthesize  — merge the persona verdicts -> ranked findings + weighted composite
 *                 + protected wins + enumerated directions, print SUCCESS:critique-panel-<id>.
 *   schema      — dump the persona + synthesis JSON Schemas (keeps them in sync).
 *
 * CLI:
 *   node critique_panel.mjs assemble --audit ./out/audit.json [--screenshot a.png,b.png] \
 *        [--rubric ./panel_rubric.md] [--scope /,/settings] --out ./out
 *   node critique_panel.mjs validate --input ./out/panel-user-advocate.out.json
 *   node critique_panel.mjs synthesize --inputs ./out/panel-*.out.json --audit ./out/audit.json --out ./out
 *   node critique_panel.mjs schema --out ./
 *
 * Programmatic: import { assemblePanel, synthesizePanelFiles } from './critique_panel.mjs';
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, realpathSync } from 'node:fs';
import { resolve, join, dirname } from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';

import {
  PERSONA_IDS,
  assemblePersonaBrief, renderPersonaMarkdown,
  validatePersona, synthesizePanel, validateSynthesis,
  PERSONA_JSON_SCHEMA, SYNTHESIS_JSON_SCHEMA,
} from './panel_schema.mjs';

const SKILL_DIR = dirname(fileURLToPath(import.meta.url));
const DEFAULT_RUBRIC = join(SKILL_DIR, 'panel_rubric.md');

const readJson = (p) => JSON.parse(readFileSync(resolve(p), 'utf8'));
const readTextSafe = (p) => { try { return readFileSync(resolve(p), 'utf8'); } catch { return ''; } };

/** Discover `<screen>.png` siblings of an audit.json when none are passed. */
function discoverScreenshots(auditPath) {
  const dir = dirname(resolve(auditPath));
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => f.toLowerCase().endsWith('.png') && !f.includes('.diff.'))
    .map((f) => join(dir, f));
}

function splitList(v) {
  if (!v) return [];
  if (Array.isArray(v)) return v;
  return String(v).split(',').map((s) => s.trim()).filter(Boolean);
}

/**
 * Assemble the four persona briefs from Track-A artefacts.
 * @returns {{ briefs: object[], paths: Array<{persona,json,md}> }}
 */
export function assemblePanel({ auditPath, screenshots, rubricPath, scope, out } = {}) {
  if (!auditPath) throw new Error('auditPath (Track-A audit.json) is required');
  const audit = readJson(auditPath);

  let shots = splitList(screenshots);
  if (shots.length === 0) shots = discoverScreenshots(auditPath);
  const rubricText = readTextSafe(rubricPath || DEFAULT_RUBRIC);
  const scopeArr = splitList(scope);

  const outDir = out ? resolve(out) : dirname(resolve(auditPath));
  mkdirSync(outDir, { recursive: true });

  const briefs = [];
  const paths = [];
  for (const persona of PERSONA_IDS) {
    const brief = assemblePersonaBrief({ audit, persona, screenshots: shots, rubricText, scope: scopeArr });
    const jsonPath = join(outDir, `panel-${persona}.brief.json`);
    const mdPath = join(outDir, `panel-${persona}.brief.md`);
    writeFileSync(jsonPath, JSON.stringify(brief, null, 2));
    writeFileSync(mdPath, renderPersonaMarkdown(brief));
    briefs.push(brief);
    paths.push({ persona, json: jsonPath, md: mdPath });
  }
  return { briefs, paths, screenshots: shots, audit_id: audit.id || null };
}

/** Synthesize from a glob/list of persona-output files. */
export function synthesizePanelFiles({ inputs, auditPath, out, runId } = {}) {
  const files = splitList(inputs);
  if (files.length === 0) throw new Error('--inputs <persona-output files> required');
  const outputs = [];
  for (const f of files) {
    const obj = readJson(f);
    const { valid, errors } = validatePersona(obj);
    if (!valid) throw new Error(`persona file ${f} is invalid: ${errors[0]}`);
    outputs.push(obj);
  }
  let audit_id = null;
  let summary = {};
  if (auditPath && existsSync(resolve(auditPath))) {
    const a = readJson(auditPath);
    audit_id = a.id || null;
    summary = a.summary || {};
  } else if (outputs[0]) {
    audit_id = outputs[0].audit_id || null;
  }
  const synth = synthesizePanel(outputs, { auditId: audit_id, summary, runId });
  let synthPath = null;
  if (out) {
    const outDir = resolve(out);
    mkdirSync(outDir, { recursive: true });
    synthPath = join(outDir, 'panel-synthesis.json');
    writeFileSync(synthPath, JSON.stringify(synth, null, 2));
  }
  return { synth, synthPath, personaCount: outputs.length };
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function cmdAssemble(values) {
  const { paths, screenshots, audit_id } = assemblePanel({
    auditPath: values.audit,
    screenshots: values.screenshot,
    rubricPath: values.rubric,
    scope: values.scope,
    out: values.out,
  });
  console.log(`[panel] audit=${audit_id || 'n/a'}  screenshots=${screenshots.length}  personas=${paths.length}`);
  for (const p of paths) console.log(`[panel] ${p.persona.padEnd(20)} → ${p.md}`);
  if (screenshots.length === 0) console.log('[panel] WARN: no screenshots found — personas must judge from numbers only (low confidence).');
  console.log('\nNext: for EACH persona, view the screenshot(s), read its .brief.md, fill the verdict per outputSchema, and');
  console.log('`node critique_panel.mjs validate --input panel-<persona>.out.json`. Then run `synthesize`.');
  console.log('SUCCESS:critique-panel-assemble');
}

function cmdValidate(values) {
  if (!values.input) throw new Error('--input <persona-output.json> required');
  const obj = readJson(values.input);
  const { valid, errors, id, persona } = validatePersona(obj);
  const tag = id || `critique-panel-${persona || 'unknown'}`;
  if (valid) {
    console.log(`[panel] persona verdict OK (${tag})`);
    console.log(`SUCCESS:${tag}`);
    return;
  }
  for (const e of errors) console.error(`  - ${e}`);
  console.error(`FAILED:${tag} ${errors.length} schema/quota violation(s)`);
  process.exitCode = 1;
}

function cmdSynthesize(values) {
  const { synth, synthPath, personaCount } = synthesizePanelFiles({
    inputs: values.inputs,
    auditPath: values.audit,
    out: values.out,
    runId: values.id,
  });
  const { valid, errors } = validateSynthesis(synth);
  if (!valid) {
    for (const e of errors) console.error(`  - ${e}`);
    console.error(`FAILED:${synth.id} ${errors.length} synthesis violation(s)`);
    process.exitCode = 1;
    return;
  }
  const v = synth.verdict;
  console.log(`[panel] personas=${personaCount}  composite=${v.composite}/100  mean=${v.meanScore}/4  critical=${v.criticalErrors}  verdict=${v.looksGood}`);
  console.log(`[panel] ${v.headline}`);
  console.log(`[panel] findings=${synth.prioritizedFindings.length}  wins=${synth.protectedWins.length}  directions=${synth.directions.length}`);
  if (synthPath) console.log(`[panel] SYNTHESIS → ${synthPath}`);
  console.log('[panel] DECISION: triage only — the human decides direction at G4.');
  console.log(`SUCCESS:${synth.id}`);
}

function cmdSchema(values) {
  const outDir = values.out ? resolve(values.out) : SKILL_DIR;
  mkdirSync(outDir, { recursive: true });
  const pPath = join(outDir, 'persona.schema.json');
  const sPath = join(outDir, 'synthesis.schema.json');
  writeFileSync(pPath, JSON.stringify(PERSONA_JSON_SCHEMA, null, 2));
  writeFileSync(sPath, JSON.stringify(SYNTHESIS_JSON_SCHEMA, null, 2));
  console.log(`[panel] wrote ${pPath}`);
  console.log(`[panel] wrote ${sPath}`);
  console.log('SUCCESS:critique-panel-schema');
}

function main() {
  const sub = process.argv[2];
  const { values } = parseArgs({
    args: process.argv.slice(3),
    options: {
      audit: { type: 'string' },
      screenshot: { type: 'string' },
      rubric: { type: 'string' },
      scope: { type: 'string' },
      input: { type: 'string' },
      inputs: { type: 'string' },
      out: { type: 'string' },
      id: { type: 'string' },
    },
    strict: false,
  });

  switch (sub) {
    case 'assemble': return cmdAssemble(values);
    case 'validate': return cmdValidate(values);
    case 'synthesize': return cmdSynthesize(values);
    case 'schema': return cmdSchema(values);
    default:
      console.error('usage: critique_panel.mjs <assemble|validate|synthesize|schema> [opts]');
      console.error('  assemble   --audit <audit.json> [--screenshot a.png,b.png] [--rubric r.md] [--scope /,/settings] [--out dir]');
      console.error('  validate   --input <persona-output.json>');
      console.error('  synthesize --inputs <a.out.json,b.out.json,...> [--audit audit.json] [--out dir] [--id runId]');
      console.error('  schema     [--out dir]');
      process.exitCode = 2;
  }
}

const __filename = fileURLToPath(import.meta.url);
/**
 * True when this file is the CLI entry point. Compares REAL paths so the guard
 * still fires when the skill dir is reached through a symlink/junction (e.g.
 * `~/.claude/skills` → `~/.agents/skills`): Node realpaths `import.meta.url`
 * but `path.resolve(argv[1])` does not, so a plain `===` would silently skip
 * `main()` and the CLI would no-op. Falls back to `resolve` if realpath throws.
 */
function isCliEntry() {
  const entry = process.argv[1];
  if (!entry) return false;
  try {
    return realpathSync(entry) === realpathSync(__filename);
  } catch {
    return resolve(entry) === resolve(__filename);
  }
}
if (isCliEntry()) {
  try {
    main();
  } catch (err) {
    console.error(`FAILED:critique-panel ${err.message}`);
    process.exitCode = 1;
  }
}
