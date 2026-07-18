/**
 * run_audit.test.mjs — orchestrator/aggregator tests.
 *
 * Pure `aggregate()` tests assert the v2 fields are wired into the merged report
 * (confidence roll-up, pageErrors surfaced, dead vs click-error split). One
 * integration test runs the full orchestrator against the component fixture and
 * asserts the `ui-audit-<id>` contract + the dead-control count.
 */

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { aggregate, runAudit } from '../run_audit.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// Pure aggregate() — no browser
// ---------------------------------------------------------------------------
describe('aggregate', () => {
  const sample = {
    id: 'x',
    screens: [{
      screen: 'home',
      url: 'http://x/',
      lintFindings: [
        { rule: 'off-scale-spacing', confidence: 'high', severity: 'warning', selector: 'a' },
        { rule: 'off-scale-spacing', confidence: 'low', severity: 'info', selector: 'b' },
        { rule: 'wcag-contrast', severity: 'error', selector: 'c' },
      ],
      deadFindings: [
        { selector: '#dead', effect: 'none' },
        { selector: '#wired', effect: 'dom' },
        { selector: '#hidden', effect: 'error', clickError: 'not actionable' },
      ],
      axeViolations: [{ id: 'color-contrast', impact: 'serious', description: 'x', nodes: [{}, {}] }],
      pageErrors: [{ name: 'Error', message: 'render crash' }],
    }],
    visual: [{ screen: 'home', percentDiff: 9 }, { screen: 'about', percentDiff: 1 }],
  };

  test('report id is namespaced ui-audit-<id>', () => {
    assert.equal(aggregate(sample).id, 'ui-audit-x');
  });

  test('off-scale-spacing confidence is rolled up (high vs low)', () => {
    const s = aggregate(sample).summary.spacing;
    assert.deepEqual(s, { high: 1, low: 1, total: 2 });
  });

  test('dead controls and click errors are counted separately', () => {
    const s = aggregate(sample).summary;
    assert.equal(s.deadControls, 1, 'only effect:none counts as dead');
    assert.equal(s.clickErrors, 1, 'effect:error is a non-actionable click, not dead');
  });

  test('pageErrors are surfaced (count + list with screen)', () => {
    const r = aggregate(sample);
    assert.equal(r.summary.pageErrors, 1);
    assert.equal(r.pageErrors[0].screen, 'home');
    assert.match(r.pageErrors[0].message, /render crash/);
  });

  test('axe + visual regressions summarised', () => {
    const s = aggregate(sample).summary;
    assert.equal(s.axeViolations, 1);
    assert.equal(s.visualRegressions, 1);   // only percentDiff>5
  });

  test('empty input is safe', () => {
    const r = aggregate();
    assert.equal(r.summary.screens, 0);
    assert.equal(r.summary.deadControls, 0);
    assert.ok(Array.isArray(r.findings));
  });
});

// ---------------------------------------------------------------------------
// Integration — full orchestrator against the component fixture
// ---------------------------------------------------------------------------
describe('runAudit (integration)', () => {
  let server, baseUrl;

  before(async () => {
    const html = readFileSync(join(__dirname, '../fixtures/component_fixture.html'), 'utf8');
    server = createServer((req, res) => {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(html);
    });
    await new Promise(r => server.listen(0, '127.0.0.1', () => {
      baseUrl = `http://127.0.0.1:${server.address().port}`;
      r();
    }));
  });

  after(() => server.close());

  test('runs all gates and emits the ui-audit-<id> contract', async () => {
    const report = await runAudit(baseUrl, { id: 'test', screens: ['/'] });
    assert.equal(report.id, 'ui-audit-test');
    assert.equal(report.summary.screens, 1);
    assert.equal(report.summary.deadControls, 4, 'component fixture has exactly 4 dead controls');
    assert.ok(report.findings.some(f => f.gate === 'dead-button'), 'dead-button findings merged');
    assert.equal(typeof report.summary.axeViolations, 'number');
    assert.equal(report.summary.pageErrors, 0, 'static fixture has no page errors');
  });
});
