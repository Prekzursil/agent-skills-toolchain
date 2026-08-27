/**
 * critique.test.mjs — Track-B (design critique) harness + schema tests.
 *
 * Pure, hermetic, no browser/network. Covers:
 *   - projectFindingsByDimension(): deterministic Track-A rule -> design-dimension routing
 *   - assembleCritiqueInput() + renderPromptMarkdown(): the critique INPUT the orchestrator fills
 *   - validateCritique(): the typed OUTPUT schema (golden pass + every rejection)
 *   - CRITIQUE_JSON_SCHEMA: enum self-consistency
 *   - critique.mjs file API end-to-end on the REAL reframe sample fixture
 *
 * The actual "does it look good" reasoning is Claude's job (it views the screenshot
 * and fills the schema); these tests pin the deterministic scaffolding around it.
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdtempSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

import {
  DIMENSIONS, SCORING_DIMENSIONS, DIMENSION_WEIGHTS, SEVERITIES, VERDICTS, RATINGS, CONFIDENCES,
  projectFindingsByDimension, assembleCritiqueInput, renderPromptMarkdown,
  validateCritique, CRITIQUE_JSON_SCHEMA, rankSeverity,
  computeComposite, applyCriticalCap, countCriticalDimensions, computeVerdict, isCriticalDimension,
} from '../critique_schema.mjs';
import { assembleCritique, validateCritiqueFile, computeVerdictFile } from '../critique.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIX = join(__dirname, '..', 'fixtures');
const richAudit = JSON.parse(readFileSync(join(FIX, 'rich_audit.json'), 'utf8'));
const sampleAudit = JSON.parse(readFileSync(join(FIX, 'sample_audit.json'), 'utf8'));

// A fully-valid Track-B verdict object — cloned + mutated by rejection tests.
// DESIGN-EVAL v1: per-dimension scores 0-4, the critical-error override (contrast=0),
// and a verdict.score that equals the §2.4 weighted composite after the §2.3 cap.
//   composite = 100*Σ(w·s)/(4·Σw) over color-contrast(0,2.0) affordance(2,1.5)
//   spacing-rhythm(3,1.0) alignment(4,0.75) motion(3,0.75)
//   = 100*11.25/(4*6.0) = 46.88 → 1 critical caps ≤60 → score 47, needs-work.
function makeValidCritique() {
  return {
    id: 'ui-critique-rich',
    audit_id: 'ui-audit-rich',
    verdict: {
      looksGood: 'needs-work',
      score: 47,
      headline: 'Solid bones, but a contrast fail and a dead Save button undercut it.',
      summary: 'Layout reads clearly but a 2.1:1 muted paragraph fails WCAG (critical) and the Save control is unwired.',
    },
    dimensions: [
      {
        dimension: 'color-contrast',
        score: 0,
        rating: 'fail',
        confidence: 'high',
        findings: [
          {
            severity: 'critical',
            evidence: 'layout-lint contrast-0: p.muted is 2.10:1 (< 4.5:1); axe color-contrast flags 3 nodes.',
            evidenceRefs: ['contrast-0', 'color-contrast'],
            recommendation: 'Darken muted text to at least #595959 on white to clear 4.5:1.',
          },
        ],
      },
      {
        dimension: 'affordance',
        score: 2,
        rating: 'fail',
        confidence: 'high',
        findings: [
          {
            severity: 'high',
            evidence: 'dead-button dead-0: #save Save has effect:none — no feedback on the primary action.',
            evidenceRefs: ['dead-0'],
            recommendation: 'Wire the Save handler so the primary action gives feedback.',
          },
        ],
      },
      {
        dimension: 'spacing-rhythm',
        score: 3,
        rating: 'warn',
        confidence: 'medium',
        findings: [
          {
            severity: 'medium',
            evidence: 'spacing-0: div.card marginTop 13px is off the 4px grid (high confidence).',
            recommendation: 'Snap card marginTop to 12px or 16px.',
          },
        ],
      },
      { dimension: 'alignment', score: 4, rating: 'pass', confidence: 'low', findings: [] },
      { dimension: 'motion', score: 3, rating: 'pass', confidence: 'low', findings: [] },
    ],
    prioritizedFindings: [
      { rank: 1, dimension: 'color-contrast', severity: 'critical', evidence: 'p.muted 2.10:1', recommendation: 'Darken muted text.' },
      { rank: 2, dimension: 'affordance', severity: 'high', evidence: '#save dead', recommendation: 'Wire Save handler.' },
    ],
    uiclip: null,
  };
}

// ---------------------------------------------------------------------------
describe('projectFindingsByDimension (deterministic Track-A -> dimension routing)', () => {
  const ev = projectFindingsByDimension(richAudit);

  test('returns an array for every known dimension', () => {
    for (const d of DIMENSIONS) assert.ok(Array.isArray(ev[d]), `missing dimension ${d}`);
  });
  test('off-scale-spacing routes to spacing-rhythm (both high + low)', () => {
    assert.equal(ev['spacing-rhythm'].length, 2);
    assert.ok(ev['spacing-rhythm'].every(e => e.rule === 'off-scale-spacing'));
  });
  test('contrast signals (lint + sprawl + axe) all route to color-contrast', () => {
    const rules = ev['color-contrast'].map(e => e.rule).sort();
    assert.equal(ev['color-contrast'].length, 3);
    assert.deepEqual(rules, ['color-contrast', 'color-inventory-sprawl', 'wcag-contrast']);
  });
  test('type-scale-sprawl routes to type-scale', () => {
    assert.equal(ev['type-scale'].length, 1);
    assert.equal(ev['type-scale'][0].rule, 'type-scale-sprawl');
  });
  test('landmark axe routes to visual-hierarchy (tap-target no longer does)', () => {
    const rules = ev['visual-hierarchy'].map(e => e.rule).sort();
    assert.deepEqual(rules, ['landmark-one-main']);
  });
  test('DESIGN-EVAL v1: tap-target + dead control + click error route to affordance', () => {
    const rules = ev['affordance'].map(e => e.rule).sort();
    assert.deepEqual(rules, ['click-error', 'dead-control', 'tap-target']);
  });
  test('pageError (render crash) still routes to empty-error-states', () => {
    const sources = ev['empty-error-states'].map(e => e.source).sort();
    assert.deepEqual(sources, ['pageError']);
  });
  test('only >5% visual regressions route to consistency', () => {
    assert.equal(ev['consistency'].length, 1);
    assert.equal(ev['consistency'][0].screen, 'home');
  });
  test('alignment has no deterministic signal (screenshot-only dimension)', () => {
    assert.equal(ev['alignment'].length, 0);
  });
  test('overall carries a synthetic totals signal', () => {
    assert.ok(ev['overall'].some(e => e.rule === 'totals'));
  });
  test('every evidence item is traceable (ref + screen)', () => {
    for (const d of DIMENSIONS) for (const e of ev[d]) {
      assert.equal(typeof e.ref, 'string');
      assert.equal(typeof e.screen, 'string');
    }
  });
  test('empty audit is safe', () => {
    const e = projectFindingsByDimension({});
    for (const d of DIMENSIONS) assert.ok(Array.isArray(e[d]));
  });
});

// ---------------------------------------------------------------------------
describe('assembleCritiqueInput', () => {
  const rubricText = '# Rubric\nVisual hierarchy first.';
  const input = assembleCritiqueInput({
    audit: richAudit,
    screenshots: 'C:/out/home.png',
    rubricText,
  });

  test('re-anchors the goal and task', () => {
    assert.match(input.goal.toLowerCase(), /design|critique|look/);
    assert.equal(input.task, 'design-critique');
  });
  test('carries audit_id + summary from Track-A', () => {
    assert.equal(input.audit_id, 'ui-audit-rich');
    assert.equal(input.summary.axeViolations, 2);
  });
  test('normalizes a single screenshot to an array', () => {
    assert.deepEqual(input.screenshots, ['C:/out/home.png']);
  });
  test('embeds the rubric text verbatim', () => {
    assert.equal(input.rubric, rubricText);
  });
  test('projects evidence by dimension', () => {
    assert.equal(input.evidenceByDimension['color-contrast'].length, 3);
  });
  test('embeds the output schema + enums for the filler', () => {
    assert.ok(input.outputSchema.$schema);
    assert.deepEqual(input.dimensions, DIMENSIONS);
    assert.deepEqual(input.severities, SEVERITIES);
  });
  test('uiclip defaults to null and passes through when supplied', () => {
    assert.equal(input.uiclip, null);
    const withClip = assembleCritiqueInput({ audit: richAudit, screenshots: ['a.png'], uiclip: { score: 0.62, status: 'ok' } });
    assert.equal(withClip.uiclip.score, 0.62);
  });
  test('instructions enforce the planner-safe no-pixel-measure rule', () => {
    const joined = input.instructions.join(' ').toLowerCase();
    assert.match(joined, /pixel|measure|coordinate/);
    assert.match(joined, /screenshot/);
  });
});

describe('renderPromptMarkdown', () => {
  const input = assembleCritiqueInput({ audit: richAudit, screenshots: ['C:/out/home.png'], rubricText: '# R' });
  const md = renderPromptMarkdown(input);
  test('is a non-empty markdown string', () => {
    assert.equal(typeof md, 'string');
    assert.ok(md.length > 200);
  });
  test('references the screenshot path the orchestrator must view', () => {
    assert.match(md, /C:\/out\/home\.png/);
  });
  test('lists every design dimension to assess', () => {
    for (const d of DIMENSIONS) assert.ok(md.includes(d), `prompt missing ${d}`);
  });
  test('includes the fill-in output skeleton', () => {
    assert.match(md, /ui-critique-/);
    assert.match(md.toLowerCase(), /verdict/);
  });
});

// ---------------------------------------------------------------------------
describe('validateCritique (typed OUTPUT schema)', () => {
  test('accepts a fully-formed golden verdict', () => {
    const { valid, errors } = validateCritique(makeValidCritique());
    assert.deepEqual(errors, []);
    assert.equal(valid, true);
  });
  test('rejects a missing verdict', () => {
    const c = makeValidCritique(); delete c.verdict;
    const { valid, errors } = validateCritique(c);
    assert.equal(valid, false);
    assert.ok(errors.some(e => /verdict/i.test(e)));
  });
  test('rejects an out-of-range score', () => {
    const c = makeValidCritique(); c.verdict.score = 140;
    assert.equal(validateCritique(c).valid, false);
  });
  test('rejects an unknown looksGood verdict value', () => {
    const c = makeValidCritique(); c.verdict.looksGood = 'amazing';
    assert.ok(validateCritique(c).errors.some(e => /looksGood/i.test(e)));
  });
  test('rejects an unknown dimension', () => {
    const c = makeValidCritique(); c.dimensions[0].dimension = 'vibes';
    assert.ok(validateCritique(c).errors.some(e => /dimension/i.test(e)));
  });
  test('rejects a bad severity enum', () => {
    const c = makeValidCritique(); c.dimensions[0].findings[0].severity = 'apocalyptic';
    assert.ok(validateCritique(c).errors.some(e => /severity/i.test(e)));
  });
  test('rejects a finding missing a recommendation', () => {
    const c = makeValidCritique(); delete c.dimensions[0].findings[0].recommendation;
    assert.ok(validateCritique(c).errors.some(e => /recommendation/i.test(e)));
  });
  test('rejects a finding with empty evidence', () => {
    const c = makeValidCritique(); c.dimensions[0].findings[0].evidence = '   ';
    assert.ok(validateCritique(c).errors.some(e => /evidence/i.test(e)));
  });
  test('rejects an empty dimensions array', () => {
    const c = makeValidCritique(); c.dimensions = [];
    assert.equal(validateCritique(c).valid, false);
  });
  test('rejects a bad id namespace', () => {
    const c = makeValidCritique(); c.id = 'whatever';
    assert.ok(validateCritique(c).errors.some(e => /id/i.test(e)));
  });
  test('rejects a missing prioritizedFindings list', () => {
    const c = makeValidCritique(); delete c.prioritizedFindings;
    assert.equal(validateCritique(c).valid, false);
  });
  test('accepts uiclip when present and well-formed', () => {
    const c = makeValidCritique(); c.uiclip = { score: 0.7, status: 'ok' };
    assert.equal(validateCritique(c).valid, true);
  });
  test('collects multiple errors rather than throwing on the first', () => {
    const { errors } = validateCritique({ id: 'x', dimensions: [] });
    assert.ok(errors.length >= 2);
  });
});

describe('CRITIQUE_JSON_SCHEMA + helpers', () => {
  test('is a draft-07-style object schema', () => {
    assert.equal(CRITIQUE_JSON_SCHEMA.type, 'object');
    assert.ok(CRITIQUE_JSON_SCHEMA.$schema);
  });
  test('dimension enum matches the DIMENSIONS constant', () => {
    const enumVals = CRITIQUE_JSON_SCHEMA.properties.dimensions.items.properties.dimension.enum;
    assert.deepEqual([...enumVals].sort(), [...DIMENSIONS].sort());
  });
  test('rankSeverity orders critical highest', () => {
    assert.ok(rankSeverity('critical') > rankSeverity('high'));
    assert.ok(rankSeverity('high') > rankSeverity('info'));
  });
  test('all enum constants are non-empty', () => {
    for (const arr of [DIMENSIONS, SEVERITIES, VERDICTS, RATINGS, CONFIDENCES]) {
      assert.ok(Array.isArray(arr) && arr.length > 0);
    }
  });
});

// ---------------------------------------------------------------------------
describe('DESIGN-EVAL v1 scoring — composite + critical override (§2.3/§2.4)', () => {
  test('SCORING_DIMENSIONS has nine; DIMENSIONS adds overall; weights cover all nine', () => {
    assert.equal(SCORING_DIMENSIONS.length, 9);
    assert.ok(SCORING_DIMENSIONS.includes('affordance'));
    assert.ok(SCORING_DIMENSIONS.includes('motion'));
    assert.deepEqual(DIMENSIONS, [...SCORING_DIMENSIONS, 'overall']);
    for (const d of SCORING_DIMENSIONS) assert.equal(typeof DIMENSION_WEIGHTS[d], 'number');
    assert.equal(DIMENSION_WEIGHTS['color-contrast'], 2.0, 'color-contrast carries the highest weight');
    assert.equal(DIMENSION_WEIGHTS.overall, undefined, 'overall is not weighted');
  });

  test('computeComposite is the §2.4 weighted formula', () => {
    // color-contrast(4,2.0) + spacing-rhythm(2,1.0): 100*(8+2)/(4*3) = 83.33
    const c = computeComposite([
      { dimension: 'color-contrast', score: 4 },
      { dimension: 'spacing-rhythm', score: 2 },
    ]);
    assert.ok(Math.abs(c - 83.333) < 0.01);
    assert.equal(computeComposite([]), null, 'nothing scored → null');
    assert.equal(computeComposite([{ dimension: 'overall', score: 3 }]), null, 'overall is excluded');
  });

  test('isCriticalDimension fires on a critical finding or the explicit flag', () => {
    assert.ok(isCriticalDimension({ dimension: 'color-contrast', findings: [{ severity: 'critical' }] }));
    assert.ok(isCriticalDimension({ dimension: 'motion', criticalError: true, findings: [] }));
    assert.ok(!isCriticalDimension({ dimension: 'motion', findings: [{ severity: 'high' }] }));
  });

  test('applyCriticalCap caps at 60 (one critical) and 39 (two+)', () => {
    assert.equal(applyCriticalCap(90, 0), 90);
    assert.equal(applyCriticalCap(90, 1), 60);
    assert.equal(applyCriticalCap(90, 2), 39);
    assert.equal(applyCriticalCap(30, 1), 30, 'cap never raises a low score');
  });

  test('computeVerdict on the golden matches the documented 46.88→47 needs-work', () => {
    const cv = computeVerdict(makeValidCritique().dimensions);
    assert.equal(cv.criticalCount, 1);
    assert.ok(Math.abs(cv.composite - 46.88) < 0.05);
    assert.equal(cv.score, 47);
    assert.equal(cv.looksGood, 'needs-work');
    assert.equal(cv.minScore, 0);
    assert.equal(cv.shipGate, false);
  });

  test('a clean board reaches the ship/reference gates and good verdict', () => {
    const allGood = SCORING_DIMENSIONS.map(d => ({ dimension: d, score: 4, rating: 'pass', confidence: 'high', findings: [] }));
    const cv = computeVerdict(allGood);
    assert.equal(cv.score, 100);
    assert.equal(cv.looksGood, 'good');
    assert.ok(cv.shipGate && cv.referenceGate);
  });

  test('two criticals force poor (capped ≤39)', () => {
    const cv = computeVerdict([
      { dimension: 'color-contrast', score: 0, findings: [{ severity: 'critical' }] },
      { dimension: 'empty-error-states', score: 0, findings: [{ severity: 'critical' }] },
      { dimension: 'spacing-rhythm', score: 4, findings: [] },
    ]);
    assert.equal(cv.criticalCount, 2);
    assert.ok(cv.score <= 39);
    assert.equal(cv.looksGood, 'poor');
  });

  test('validate rejects a missing per-dimension score', () => {
    const c = makeValidCritique(); delete c.dimensions[2].score;   // spacing-rhythm
    assert.ok(validateCritique(c).errors.some(e => /score must be a number/i.test(e)));
  });
  test('validate rejects an out-of-range per-dimension score', () => {
    const c = makeValidCritique(); c.dimensions[2].score = 7;
    assert.ok(validateCritique(c).errors.some(e => /score/i.test(e)));
  });
  test('validate enforces the critical-error override (critical finding ⇒ score 0)', () => {
    const c = makeValidCritique(); c.dimensions[0].score = 2;   // color-contrast has a critical finding
    assert.ok(validateCritique(c).errors.some(e => /critical-error override/i.test(e)));
  });
  test('validate rejects a free-handed verdict.score that defies the composite', () => {
    const c = makeValidCritique(); c.verdict.score = 90;        // composite is ~47
    const { errors } = validateCritique(c);
    assert.ok(errors.some(e => /weighted composite/i.test(e)));
  });
  test('validate rejects a looksGood inconsistent with the composite', () => {
    const c = makeValidCritique(); c.verdict.looksGood = 'good';
    assert.ok(validateCritique(c).errors.some(e => /!= computed/i.test(e)));
  });

  test('computeVerdictFile fills verdict.score + looksGood + eval from the dimensions', () => {
    const out = mkdtempSync(join(tmpdir(), 'uicompute-'));
    const f = join(out, 'c.json');
    const draft = makeValidCritique();
    draft.verdict.score = 0; draft.verdict.looksGood = 'poor';   // wrong on purpose
    writeFileSync(f, JSON.stringify(draft));
    const { verdict } = computeVerdictFile(f);
    assert.equal(verdict.score, 47);
    const written = JSON.parse(readFileSync(f, 'utf8'));
    assert.equal(written.verdict.score, 47);
    assert.equal(written.verdict.looksGood, 'needs-work');
    assert.equal(written.verdict.eval.criticalCount, 1);
    assert.equal(validateCritique(written).valid, true, 'computed file passes validation');
  });
});

// ---------------------------------------------------------------------------
describe('critique.mjs file API on the REAL reframe sample', () => {
  test('assembleCritique writes input json + prompt md grounded in the real audit', () => {
    const out = mkdtempSync(join(tmpdir(), 'uicritique-'));
    const res = assembleCritique({
      auditPath: join(FIX, 'sample_audit.json'),
      screenshots: [join(FIX, 'sample_home.png')],
      rubricPath: join(__dirname, '..', 'critique_rubric.md'),
      out,
    });
    assert.equal(res.input.audit_id, 'ui-audit-reframe');
    assert.equal(res.input.summary.axeViolations, 2);
    // The near-blank render: axe says no main landmark + no h1 -> visual-hierarchy evidence.
    assert.ok(res.input.evidenceByDimension['visual-hierarchy'].length >= 1);
    assert.ok(existsSync(res.paths.inputJson));
    assert.ok(existsSync(res.paths.promptMd));
    assert.ok(res.input.rubric.length > 100, 'real rubric embedded');
  });

  test('validateCritiqueFile passes a golden verdict and fails a broken one', () => {
    const out = mkdtempSync(join(tmpdir(), 'uicritique-'));
    const good = join(out, 'good.json');
    const bad = join(out, 'bad.json');
    writeFileSync(good, JSON.stringify(makeValidCritique()));
    writeFileSync(bad, JSON.stringify({ id: 'ui-critique-x', dimensions: [] }));
    assert.equal(validateCritiqueFile(good).valid, true);
    assert.equal(validateCritiqueFile(bad).valid, false);
  });
});
