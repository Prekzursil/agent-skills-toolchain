import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  PERSONA_IDS, DIMENSIONS, DIMENSION_META,
  projectFindingsByDimension, assemblePersonaBrief, renderPersonaMarkdown,
  validatePersona, synthesizePanel, validateSynthesis,
} from '../panel_schema.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const audit = JSON.parse(readFileSync(join(HERE, '..', 'fixtures', 'audit.sample.json'), 'utf8'));

// --- helpers ---------------------------------------------------------------
function dim(dimension, over = {}) {
  return {
    dimension, score: 3, confidence: 'medium', critical: false,
    iLike: ['win a', 'win b'], iWish: [{ severity: 'medium', evidence: 'ev', recommendation: 'fix it' }],
    whatIf: ['a direction'], ...over,
  };
}
function persona(id, dims, scope = ['home']) {
  return { id: `critique-panel-${id}-t`, persona: id, audit_id: 'ui-audit-sample', scope, dimensions: dims };
}

// --- routing ---------------------------------------------------------------
test('projectFindingsByDimension routes Track-A signals to the 9-dim model', () => {
  const by = projectFindingsByDimension(audit);
  const refs = (d) => by[d].map((e) => e.ref);
  assert.ok(refs('color-contrast').includes('contrast-0'), 'wcag-contrast → color-contrast');
  assert.ok(refs('color-contrast').includes('color-contrast'), 'axe color-contrast → color-contrast');
  assert.ok(refs('affordance').includes('tap-0'), 'tap-target → affordance');
  assert.ok(refs('type-scale').includes('type-0'), 'type-scale-sprawl → type-scale');
  assert.ok(refs('empty-error-states').includes('dead-0'), 'dead-control → empty-error-states');
  assert.ok(refs('motion').includes('motion-0'), 'reduced-motion → motion');
  assert.ok(refs('consistency').some((r) => r.startsWith('visual-')), 'visual-regression → consistency');
  assert.ok(refs('visual-hierarchy').includes('heading-order'), 'axe heading-order → visual-hierarchy');
  assert.ok(by.overall.some((e) => e.ref === 'summary-totals'), 'totals → overall');
});

// --- persona brief ---------------------------------------------------------
test('assemblePersonaBrief gives each persona only its owned dims + routed evidence', () => {
  const brief = assemblePersonaBrief({ audit, persona: 'a11y', screenshots: ['home.png'], scope: ['home'] });
  assert.deepEqual(brief.ownedDimensions, ['color-contrast', 'affordance', 'motion']);
  assert.ok(brief.evidenceForYou['color-contrast'].evidence.length >= 2);
  assert.equal(brief.evidenceForYou['color-contrast'].weight, 2.0);
  assert.ok(!brief.evidenceForYou['spacing-rhythm'], 'a11y does not own spacing-rhythm');
  const md = renderPersonaMarkdown(brief);
  assert.match(md, /Accessibility \(WCAG\) Evaluator/);
  assert.match(md, /contrast-0/);
});

test('assemblePersonaBrief rejects an unknown persona', () => {
  assert.throws(() => assemblePersonaBrief({ audit, persona: 'nope' }), /unknown persona/);
});

test('every dimension is owned by at least one persona', () => {
  const owned = new Set();
  for (const id of PERSONA_IDS) for (const d of assemblePersonaBrief({ audit, persona: id }).ownedDimensions) owned.add(d);
  for (const d of DIMENSIONS) assert.ok(owned.has(d), `${d} must be owned`);
});

// --- persona validation ----------------------------------------------------
test('validatePersona accepts a well-formed quota-satisfying verdict', () => {
  const p = persona('a11y', [dim('color-contrast'), dim('affordance'), dim('motion')]);
  const { valid, errors } = validatePersona(p);
  assert.ok(valid, errors.join('; '));
});

test('validatePersona enforces the >=2 wins + 1 fix quota per screen', () => {
  const p = persona('a11y', [dim('color-contrast', { iLike: ['only one'], iWish: [] })]);
  const { valid, errors } = validatePersona(p);
  assert.ok(!valid);
  assert.ok(errors.some((e) => /quota: need >=2 iLike/.test(e)));
  assert.ok(errors.some((e) => /quota: need >=1 iWish/.test(e)));
});

test('validatePersona scales the quota with the number of screens in scope', () => {
  const p = persona('a11y', [dim('color-contrast')], ['home', 'settings']); // 2 screens → need 4 likes / 2 wishes
  const { valid, errors } = validatePersona(p);
  assert.ok(!valid);
  assert.ok(errors.some((e) => /need >=4 iLike/.test(e)));
});

test('validatePersona forbids a dimension a persona does not own', () => {
  const p = persona('a11y', [dim('spacing-rhythm'), dim('color-contrast'), dim('motion')]);
  const { valid, errors } = validatePersona(p);
  assert.ok(!valid);
  assert.ok(errors.some((e) => /not owned by persona 'a11y'/.test(e)));
});

test('validatePersona requires score 0 when critical is true (override)', () => {
  const p = persona('a11y', [dim('color-contrast', { critical: true, score: 2 }), dim('affordance'), dim('motion')]);
  const { valid, errors } = validatePersona(p);
  assert.ok(!valid);
  assert.ok(errors.some((e) => /critical is true so score must be 0/.test(e)));
});

test('validatePersona rejects an out-of-range score', () => {
  const p = persona('a11y', [dim('color-contrast', { score: 5 }), dim('affordance'), dim('motion')]);
  const { valid, errors } = validatePersona(p);
  assert.ok(!valid);
  assert.ok(errors.some((e) => /score must be an integer 0\.\.4/.test(e)));
});

// --- synthesis -------------------------------------------------------------
test('synthesizePanel dedupes a finding raised by two personas into consensus 2', () => {
  const shared = { severity: 'high', evidence: 'cta is weak', evidenceRefs: ['tap-0'], recommendation: 'strengthen CTA' };
  const ua = persona('user-advocate', [dim('visual-hierarchy', { iWish: [shared] }), dim('affordance'), dim('empty-error-states'), dim('consistency')]);
  const ba = persona('brand-aesthetic', [dim('visual-hierarchy', { iWish: [shared] }), dim('color-contrast'), dim('type-scale'), dim('motion')]);
  const synth = synthesizePanel([ua, ba], { auditId: 'ui-audit-sample' });
  const merged = synth.prioritizedFindings.filter((f) => f.dimension === 'visual-hierarchy');
  assert.equal(merged.length, 1, 'duplicate finding merged');
  assert.equal(merged[0].consensus, 2);
  assert.deepEqual(merged[0].raisedBy.sort(), ['brand-aesthetic', 'user-advocate']);
});

test('synthesizePanel applies the critical-error override + cap and ranks critical first', () => {
  const a11y = persona('a11y', [
    dim('color-contrast', { score: 0, critical: true, iWish: [{ severity: 'critical', evidence: 'body 3.1:1', evidenceRefs: ['contrast-0'], recommendation: 'raise to 4.5:1' }] }),
    dim('affordance', { score: 2 }), dim('motion', { score: 3 }),
  ]);
  const synth = synthesizePanel([a11y], { auditId: 'ui-audit-sample' });
  const cc = synth.dimensionScores.find((d) => d.dimension === 'color-contrast');
  assert.equal(cc.score, 0);
  assert.equal(cc.critical, true);
  assert.equal(synth.verdict.criticalErrors, 1);
  assert.ok(synth.verdict.composite <= 60, 'one critical caps composite at 60');
  assert.equal(synth.prioritizedFindings[0].severity, 'critical', 'critical ranked first');
  assert.equal(synth.verdict.shipGate, false);
});

test('synthesizePanel two criticals → poor and composite <= 39', () => {
  const a11y = persona('a11y', [
    dim('color-contrast', { score: 0, critical: true, iWish: [{ severity: 'critical', evidence: 'contrast', recommendation: 'fix' }] }),
    dim('affordance', { score: 0, critical: true, iWish: [{ severity: 'critical', evidence: 'dead', recommendation: 'wire' }] }),
    dim('motion', { score: 3 }),
  ]);
  const synth = synthesizePanel([a11y], { auditId: 'ui-audit-sample' });
  assert.equal(synth.verdict.looksGood, 'poor');
  assert.ok(synth.verdict.composite <= 39);
});

test('synthesizePanel computes the weighted composite from clean scores', () => {
  // all owned dims score 4 across personas → composite 100, good, ship gate true
  const all = PERSONA_IDS.map((id) => persona(id, assemblePersonaBrief({ audit, persona: id }).ownedDimensions.map((d) => dim(d, { score: 4 }))));
  const synth = synthesizePanel(all, { auditId: 'ui-audit-sample' });
  assert.equal(synth.verdict.composite, 100);
  assert.equal(synth.verdict.meanScore, 4);
  assert.equal(synth.verdict.looksGood, 'good');
  assert.equal(synth.verdict.shipGate, true);
  assert.equal(synth.verdict.criticalErrors, 0);
});

test('synthesizePanel dedupes protected wins and validates against the schema', () => {
  const ua = persona('user-advocate', [dim('visual-hierarchy', { iLike: ['clean header', 'shared win'] }), dim('affordance'), dim('empty-error-states'), dim('consistency')]);
  const ba = persona('brand-aesthetic', [dim('color-contrast', { iLike: ['shared win', 'nice accent'] }), dim('visual-hierarchy'), dim('type-scale'), dim('motion')]);
  const synth = synthesizePanel([ua, ba], { auditId: 'ui-audit-sample' });
  const shared = synth.protectedWins.find((w) => w.win === 'shared win');
  assert.equal(shared.raisedBy.length, 2, 'shared win merged across personas');
  const { valid, errors } = validateSynthesis(synth);
  assert.ok(valid, errors.join('; '));
  assert.match(synth.decision, /HUMAN decides|human decides/i);
});

test('dimension weights match the spec (color-contrast 2.0 is heaviest)', () => {
  assert.equal(DIMENSION_META['color-contrast'].weight, 2.0);
  const max = Math.max(...DIMENSIONS.map((d) => DIMENSION_META[d].weight));
  assert.equal(DIMENSION_META['color-contrast'].weight, max);
});
