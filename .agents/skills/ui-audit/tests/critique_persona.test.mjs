/**
 * critique_persona.test.mjs — Track-B PERSONA + cross-vendor consensus + extended
 * gate surfacing + shadow-sink tests (item C-ui-audit-gates).
 *
 * Pure, hermetic, no browser/network. Covers the additions this item makes to
 * critique.mjs ONLY (critique_schema.mjs is unchanged and its tests stay green):
 *   - PERSONAS registry (claude-critic default + codex-critic 5th, cross-vendor)
 *   - assembleCritique persona routing + filename suffixing + brief sections
 *   - projectSupplementalSignals(): the extended Track-A gates ride the bus as
 *     SHADOW-advisory evidence (Lighthouse/APCA/ARIA-diff/Equal-Access/Guidepup/
 *     Design2Code/Storybook), degrading to empty when a key is absent
 *   - reconcilePersonaVerdicts()/reconcileCritiqueFiles(): conservative min-score
 *     cross-vendor consensus that PASSES the existing validateCritique
 *   - shadowLog(): bounded, env-overridable, fail-open (Council C5-iii)
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdtempSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

// Route shadow logs to a throwaway dir for the whole test run (never the real vault).
const SHADOW = mkdtempSync(join(tmpdir(), 'uia-shadow-'));
process.env.UI_AUDIT_SHADOW_DIR = SHADOW;

const {
  PERSONAS, DEFAULT_PERSONA, resolvePersona, SHADOW_CONTRACT, SUPPLEMENTAL_GATES,
  projectSupplementalSignals, assembleCritique, reconcilePersonaVerdicts,
  reconcileCritiqueFiles, shadowLog,
} = await import('../critique.mjs');
const { validateCritique, SCORING_DIMENSIONS } = await import('../critique_schema.mjs');

function tmp() { return mkdtempSync(join(tmpdir(), 'uia-persona-')); }

/** A minimal Track-A audit with the extended gate arrays populated. */
function suppAudit() {
  return {
    id: 'ui-audit-supp',
    summary: { screens: 1, axeViolations: 0, deadControls: 0, pageErrors: 0, visualRegressions: 0, spacing: { high: 0, low: 0, total: 0 } },
    findings: [], axe: [], pageErrors: [], visual: [],
    lighthouse:  [{ id: 'lh-perf', screen: 'home', severity: 'medium', value: 0.72, detail: 'LCP 3.1s' }],
    apca:        [{ id: 'apca-0', screen: 'home', severity: 'info', value: 58, detail: 'body Lc 58 (advisory ~60)' }],
    ariaDiff:    [{ id: 'aria-0', screen: 'home', severity: 'low', detail: '2 nodes changed role vs baseline' }],
    equalAccess: [{ id: 'ea-0', screen: 'home', severity: 'moderate', detail: 'IBM Equal Access: label missing' }],
    guidepup:    [{ id: 'nvda-0', screen: 'home', severity: 'high', detail: 'NVDA announced empty button' }],
    design2code: [{ id: 'd2c-0', screen: 'home', severity: 'low', value: 0.94, detail: 'CLIP fidelity 0.94 vs Figma' }],
    storybook:   [{ id: 'sb-0', screen: 'Button', severity: 'medium', detail: 'axe: button-name' }],
  };
}

/** A minimal Track-A audit with NONE of the extended gate arrays (backward-compat). */
function bareAudit() {
  return {
    id: 'ui-audit-bare',
    summary: { screens: 1, axeViolations: 0, deadControls: 0, pageErrors: 0, visualRegressions: 0, spacing: { high: 0, low: 0, total: 0 } },
    findings: [], axe: [], pageErrors: [], visual: [],
  };
}

function writeAudit(dir, audit) {
  const p = join(dir, 'audit.json');
  writeFileSync(p, JSON.stringify(audit));
  return p;
}

// ---------------------------------------------------------------------------
describe('PERSONAS registry', () => {
  test('claude-critic is the default; codex-critic is the 5th cross-vendor voice', () => {
    assert.equal(DEFAULT_PERSONA, 'claude-critic');
    assert.equal(PERSONAS['claude-critic'].vendor, 'anthropic');
    assert.equal(PERSONAS['codex-critic'].vendor, 'openai');
    assert.equal(PERSONAS['codex-critic'].order, 5);
    assert.match(PERSONAS['codex-critic'].rail, /codex mcp-server|mcp__codex/);
  });
  test('resolvePersona falls back to the default on unknown/empty', () => {
    assert.equal(resolvePersona(undefined).id, 'claude-critic');
    assert.equal(resolvePersona('nope').id, 'claude-critic');
    assert.equal(resolvePersona('codex-critic').id, 'codex-critic');
  });
});

// ---------------------------------------------------------------------------
describe('assembleCritique — persona routing + filenames + brief sections', () => {
  test('default persona is backward-compatible (critique-input.json, no persona section)', () => {
    const dir = tmp();
    const auditPath = writeAudit(dir, bareAudit());
    const { input, paths } = assembleCritique({ auditPath, out: dir });
    assert.equal(input.persona.id, 'claude-critic');
    assert.ok(paths.inputJson.endsWith('critique-input.json'), paths.inputJson);
    const md = readFileSync(paths.promptMd, 'utf8');
    assert.ok(!/## Persona: `codex-critic`/.test(md), 'default persona adds no persona section');
    assert.equal(input.supplementalSignals.length, 0, 'bare audit → no supplemental signals');
    assert.ok(!/Supplemental Track-A signals/.test(md));
  });

  test('codex-critic persona suffixes the filename and injects the cross-vendor brief', () => {
    const dir = tmp();
    const auditPath = writeAudit(dir, bareAudit());
    const { input, paths } = assembleCritique({ auditPath, out: dir, persona: 'codex-critic' });
    assert.equal(input.persona.id, 'codex-critic');
    assert.ok(paths.promptMd.endsWith('critique-input-codex-critic.md'), paths.promptMd);
    const md = readFileSync(paths.promptMd, 'utf8');
    assert.match(md, /Persona: `codex-critic`/);
    assert.match(md, /codex mcp-server|mcp__codex__codex/);
    assert.match(md, /reconcile --inputs/);
    assert.match(md, /ADVISORY|SHADOW/);
  });

  test('persona + dimension compose the suffix (§2.5 one-dimension-per-call)', () => {
    const dir = tmp();
    const auditPath = writeAudit(dir, bareAudit());
    const { paths } = assembleCritique({ auditPath, out: dir, persona: 'codex-critic', dimension: 'affordance' });
    assert.ok(paths.inputJson.endsWith('critique-input-codex-critic-affordance.json'), paths.inputJson);
  });

  test('extended gate signals ride the bus into the brief (SHADOW-advisory)', () => {
    const dir = tmp();
    const auditPath = writeAudit(dir, suppAudit());
    const { input, paths } = assembleCritique({ auditPath, out: dir });
    assert.equal(input.supplementalSignals.length, 7);
    const gates = input.supplementalSignals.map(s => s.gate).sort();
    assert.deepEqual(gates, ['apca', 'aria-diff', 'design2code', 'equal-access', 'guidepup', 'lighthouse', 'storybook']);
    const md = readFileSync(paths.promptMd, 'utf8');
    assert.match(md, /Supplemental Track-A signals \(SHADOW/);
    assert.match(md, /Lighthouse/);
    assert.match(md, /Guidepup real screen-reader/);
    // Advisory: must be flagged as NOT in the composite so it can't silently move the score.
    assert.match(md, /NOT in the composite/);
  });
});

// ---------------------------------------------------------------------------
describe('projectSupplementalSignals (pure)', () => {
  test('projects every populated extended key with traceable refs', () => {
    const sig = projectSupplementalSignals(suppAudit());
    assert.equal(sig.length, 7);
    for (const s of sig) {
      assert.ok(Object.values(SUPPLEMENTAL_GATES).some(m => m.gate === s.gate));
      assert.equal(s.shadow, true);
      assert.ok(Array.isArray(s.dimHints) && s.dimHints.length >= 1);
      for (const it of s.items) assert.equal(typeof it.ref, 'string');
    }
    const lh = sig.find(s => s.gate === 'lighthouse');
    assert.equal(lh.items[0].ref, 'lh-perf');
  });
  test('absent keys are skipped (degrades to empty)', () => {
    assert.deepEqual(projectSupplementalSignals(bareAudit()), []);
    assert.deepEqual(projectSupplementalSignals({}), []);
  });
  test('a missing id falls back to a synthetic ref', () => {
    const sig = projectSupplementalSignals({ apca: [{ screen: 'home', value: 40 }] });
    assert.equal(sig[0].items[0].ref, 'apca-0');
  });
});

// ---------------------------------------------------------------------------
describe('reconcilePersonaVerdicts — conservative cross-vendor consensus', () => {
  const claude = {
    id: 'ui-critique-claude', audit_id: 'ui-audit-x', persona: { id: 'claude-critic' },
    verdict: { looksGood: 'needs-work', score: 50, headline: 'h', summary: 's' },
    dimensions: [
      { dimension: 'color-contrast', score: 3, rating: 'pass', confidence: 'high', findings: [] },
      { dimension: 'affordance', score: 2, rating: 'warn', confidence: 'medium', findings: [{ severity: 'high', evidence: 'Save has a weak affordance', recommendation: 'add a focus ring' }] },
      { dimension: 'spacing-rhythm', score: 4, rating: 'pass', confidence: 'high', findings: [] },
    ],
    prioritizedFindings: [], uiclip: null,
  };
  const codex = {
    id: 'ui-critique-codex', audit_id: 'ui-audit-x', persona: { id: 'codex-critic' },
    verdict: { looksGood: 'poor', score: 30, headline: 'h', summary: 's' },
    dimensions: [
      { dimension: 'color-contrast', score: 1, rating: 'warn', confidence: 'low', findings: [{ severity: 'high', evidence: 'muted text 3.0:1', recommendation: 'darken to 4.5:1' }] },
      { dimension: 'affordance', score: 3, rating: 'pass', confidence: 'high', findings: [] },
      { dimension: 'spacing-rhythm', score: 2, rating: 'warn', confidence: 'medium', findings: [] },
      { dimension: 'motion', score: 0, rating: 'fail', confidence: 'high', criticalError: true, findings: [{ severity: 'critical', evidence: 'no prefers-reduced-motion; 900ms slide', recommendation: 'add reduced-motion + shorten' }] },
    ],
    prioritizedFindings: [], uiclip: null,
  };

  const consensus = reconcilePersonaVerdicts([claude, codex]);

  test('takes the MIN score per dimension', () => {
    const cc = consensus.dimensions.find(d => d.dimension === 'color-contrast');
    const sp = consensus.dimensions.find(d => d.dimension === 'spacing-rhythm');
    assert.equal(cc.score, 1);   // min(3,1)
    assert.equal(sp.score, 2);   // min(4,2)
  });
  test('takes the WORST rating and the LOWEST confidence', () => {
    const cc = consensus.dimensions.find(d => d.dimension === 'color-contrast');
    assert.equal(cc.rating, 'warn');       // worst(pass,warn)
    assert.equal(cc.confidence, 'low');    // lowest(high,low)
  });
  test('unions findings and enforces the critical-error override (score 0)', () => {
    const m = consensus.dimensions.find(d => d.dimension === 'motion');
    assert.equal(m.score, 0);
    assert.equal(m.criticalError, true);
    const cc = consensus.dimensions.find(d => d.dimension === 'color-contrast');
    assert.equal(cc.findings.length, 1); // codex's contrast finding carried over
  });
  test('records the participating personas', () => {
    assert.deepEqual(consensus.personas, ['claude-critic', 'codex-critic']);
  });
  test('re-derives the verdict via computeVerdict (33 → poor, 1 critical)', () => {
    assert.equal(consensus.verdict.score, 33);
    assert.equal(consensus.verdict.looksGood, 'poor');
    assert.equal(consensus.verdict.eval.criticalCount, 1);
  });
  test('prioritizedFindings collects critical+high, critical ranked first', () => {
    assert.ok(consensus.prioritizedFindings.length >= 3);
    assert.equal(consensus.prioritizedFindings[0].severity, 'critical');
    assert.equal(consensus.prioritizedFindings[0].rank, 1);
  });
  test('the consensus PASSES the existing validateCritique', () => {
    const { valid, errors } = validateCritique(consensus);
    assert.deepEqual(errors, []);
    assert.equal(valid, true);
  });
  test('single scored persona still reconciles cleanly', () => {
    const solo = reconcilePersonaVerdicts([claude]);
    assert.equal(validateCritique(solo).valid, true);
    assert.equal(solo.personas.length, 1);
  });
});

// ---------------------------------------------------------------------------
describe('reconcileCritiqueFiles (I/O)', () => {
  test('writes a consensus file that passes validation', () => {
    const dir = tmp();
    const a = join(dir, 'a.json');
    const b = join(dir, 'b.json');
    writeFileSync(a, JSON.stringify({
      id: 'ui-critique-a', audit_id: 'ui-audit-y', persona: { id: 'claude-critic' },
      dimensions: [{ dimension: 'color-contrast', score: 4, rating: 'pass', confidence: 'high', findings: [] }],
      prioritizedFindings: [], uiclip: null,
    }));
    writeFileSync(b, JSON.stringify({
      id: 'ui-critique-b', audit_id: 'ui-audit-y', persona: { id: 'codex-critic' },
      dimensions: [{ dimension: 'color-contrast', score: 2, rating: 'warn', confidence: 'medium', findings: [] }],
      prioritizedFindings: [], uiclip: null,
    }));
    const { obj, path, valid } = reconcileCritiqueFiles([a, b], { out: dir });
    assert.ok(existsSync(path));
    assert.equal(valid, true);
    const cc = obj.dimensions.find(d => d.dimension === 'color-contrast');
    assert.equal(cc.score, 2); // min(4,2)
  });
  test('needs at least two inputs', () => {
    assert.throws(() => reconcileCritiqueFiles(['only-one.json'], {}), /at least two/);
  });
});

// ---------------------------------------------------------------------------
describe('shadowLog (Council C5-iii — bounded, env-overridable, fail-open)', () => {
  test('writes an observe-only SHADOW line to the overridden sink', () => {
    shadowLog('unit-test', { a: 1 });
    const sink = join(SHADOW, 'ui-critique-shadow.jsonl');
    assert.ok(existsSync(sink));
    const last = readFileSync(sink, 'utf8').trim().split('\n').pop();
    const row = JSON.parse(last);
    assert.equal(row.mode, 'SHADOW');
    assert.equal(row.event, 'unit-test');
    assert.equal(row.contract, SHADOW_CONTRACT.gate);
  });
  test('is fail-open — a non-serialisable payload never throws', () => {
    const circular = {}; circular.self = circular;
    assert.doesNotThrow(() => shadowLog('circular', { circular }));
  });
  test('the anti-zombie contract is fully specified (Council C5-i)', () => {
    for (const k of ['gate', 'mode', 'promotionMetric', 'owner', 'graduationDeadline', 'fireRateHypothesis']) {
      assert.ok(SHADOW_CONTRACT[k], `contract missing ${k}`);
    }
    assert.equal(SHADOW_CONTRACT.mode, 'SHADOW');
  });
});

// A guard so we notice if the scoring-dimension vocabulary drifts under us.
describe('vocabulary anchor', () => {
  test('SCORING_DIMENSIONS still holds the nine DESIGN-EVAL v1 dims', () => {
    assert.equal(SCORING_DIMENSIONS.length, 9);
    assert.ok(SCORING_DIMENSIONS.includes('color-contrast'));
    assert.ok(SCORING_DIMENSIONS.includes('motion'));
  });
});
