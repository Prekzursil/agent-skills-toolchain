#!/usr/bin/env node
/**
 * run_audit.mjs — the ui-audit orchestrator.
 *
 * Runs every gate (capture → layout_lint → dead_button_crawl → axe_scan →
 * visual_diff), CONSUMES their findings, and emits ONE annotated findings JSON
 * (`audit.json`) plus the skill's terminal-state marker `SUCCESS:ui-audit-<id>` /
 * `FAILED:ui-audit-<id> <reason>` — the contract promised in SKILL.md's description
 * but absent before this orchestrator (each gate emitted only its own SUCCESS:<gate>).
 *
 * Wiring of the v2 hardening:
 *   - `--include-low-confidence` is threaded into layout_lint so the merged report
 *     can either suppress (default) or surface sub-pixel spacing noise;
 *   - per-finding `confidence` (off-scale-spacing) is rolled up in the summary
 *     (`spacing.high` / `spacing.low`);
 *   - `pageErrors` captured during load (SPA/Reframe crashes) are surfaced both
 *     per-screen and in `summary.pageErrors`;
 *   - dead controls (`effect:'none'`) and non-actionable clicks (`effect:'error'`)
 *     are counted separately so a crawl miss is never mistaken for a dead button.
 *
 * CLI usage:
 *   node run_audit.mjs --url http://localhost:5173 --screens /,/settings --out ./ui-audit-out
 *   node run_audit.mjs --url http://localhost:4200 --include-low-confidence --baseline ./baselines --out ./ui-audit-out
 *   node run_audit.mjs --url http://localhost:5173 --wait-selector "#root > *" --settle 500 --out ./ui-audit-out
 *
 * (Electron renderers like Reframe are served by Vite on a localhost port — point
 *  --url at that port. Use capture.mjs --electron for a main-process snapshot.)
 *
 * Programmatic usage:
 *   import { runAudit, aggregate } from './run_audit.mjs';
 *   const report = await runAudit('http://localhost:5173', { screens: ['/'] });
 */

import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';

import { captureUrl } from './capture.mjs';
import { lintBundle } from './layout_lint.mjs';
import { crawlUrl } from './dead_button_crawl.mjs';
import { scanUrl } from './axe_scan.mjs';
import { compareScreens } from './visual_diff.mjs';

/**
 * Pure aggregation of per-gate outputs into one annotated report + summary.
 * No I/O, no browser — unit-testable.
 *
 * @param {object} input
 * @param {string} [input.id]      - short run id (the report id becomes `ui-audit-<id>`)
 * @param {Array}  [input.screens] - [{ screen, url, lintFindings[], deadFindings[], axeViolations[], pageErrors[] }]
 * @param {Array}  [input.visual]  - visual_diff results [{ screen, percentDiff, ... }]
 */
export function aggregate(input = {}) {
  const { id = 'run', screens = [], visual = [] } = input;

  const findings = [];
  const axe = [];
  const pageErrors = [];

  for (const s of screens) {
    for (const f of (s.lintFindings || [])) findings.push({ gate: 'layout-lint', screen: s.screen, ...f });
    for (const f of (s.deadFindings || [])) findings.push({ gate: 'dead-button', screen: s.screen, ...f });
    for (const v of (s.axeViolations || [])) axe.push({ screen: s.screen, id: v.id, impact: v.impact, description: v.description, nodes: (v.nodes || []).length });
    for (const e of (s.pageErrors || [])) pageErrors.push({ screen: s.screen, ...e });
  }

  const spacing = findings.filter(f => f.rule === 'off-scale-spacing');
  const dead = findings.filter(f => f.effect === 'none');
  const clickErrors = findings.filter(f => f.effect === 'error');
  const regressions = visual.filter(v => (v.percentDiff || 0) > 5);

  const findingsByRule = {};
  for (const f of findings) if (f.rule) findingsByRule[f.rule] = (findingsByRule[f.rule] || 0) + 1;

  const summary = {
    screens: screens.length,
    spacing: {
      high: spacing.filter(f => f.confidence === 'high').length,
      low: spacing.filter(f => f.confidence === 'low').length,
      total: spacing.length,
    },
    findingsByRule,
    deadControls: dead.length,
    clickErrors: clickErrors.length,
    axeViolations: axe.length,
    pageErrors: pageErrors.length,
    visualRegressions: regressions.length,
  };

  return {
    id: `ui-audit-${id}`,
    timestamp: new Date().toISOString(),
    summary,
    findings,
    axe,
    pageErrors,
    visual,
  };
}

/**
 * Run every gate against a live URL and return the aggregated report.
 * Writes <out>/audit.json (+ each gate's artifacts) when `out` is provided.
 */
export async function runAudit(url, opts = {}) {
  const {
    id = String(Date.now()).slice(-6),
    screens = ['/'],
    out = null,
    baseline = null,
    includeLowConfidence = false,
    waitSelector,
    settleMs,
    tags,
    launchOptions,
  } = opts;

  const outDir = out ? resolve(out) : null;

  // 1. Capture every screen (writes bundles + PNGs when outDir is set).
  const bundles = await captureUrl(url, { screens, out: outDir, waitSelector, settleMs, launchOptions });

  const baseUrl = url.replace(/\/$/, '');
  const screenResults = [];

  for (let i = 0; i < screens.length; i++) {
    const screen = screens[i];
    const bundle = bundles[i] || { screen: 'home', elements: [], pageErrors: [] };
    const screenName = bundle.screen;
    const fullUrl = /^https?:\/\//.test(screen)
      ? screen
      : baseUrl + (screen.startsWith('/') ? screen : '/' + screen);

    // 2. Layout lint — confidence wiring (suppress sub-pixel noise unless opted in).
    const lintFindings = lintBundle(bundle, { includeLowConfidence });
    // 3. Dead-button crawl (handle-based).
    const deadFindings = await crawlUrl(fullUrl, { screen: screenName, waitSelector, settleMs, launchOptions });
    // 4. axe WCAG scan.
    const axeViolations = await scanUrl(fullUrl, { screen: screenName, tags, launchOptions });

    screenResults.push({
      screen: screenName,
      url: fullUrl,
      lintFindings,
      deadFindings,
      axeViolations,
      pageErrors: bundle.pageErrors || [],
    });
  }

  // 5. Visual diff (needs both an out dir of fresh PNGs and a baseline dir).
  let visual = [];
  if (outDir && baseline) {
    visual = await compareScreens(outDir, resolve(baseline), join(outDir, 'diffs'));
  }

  const report = aggregate({ id, screens: screenResults, visual });

  if (outDir) {
    mkdirSync(outDir, { recursive: true });
    writeFileSync(join(outDir, 'audit.json'), JSON.stringify(report, null, 2));
  }

  return report;
}

// ---------------------------------------------------------------------------
// CLI entrypoint
// ---------------------------------------------------------------------------

function printSummary(report) {
  const s = report.summary;
  console.log(`\n=== ${report.id} ===`);
  console.log(`screens            : ${s.screens}`);
  console.log(`off-scale-spacing  : ${s.spacing.total} (high ${s.spacing.high} / low ${s.spacing.low})`);
  console.log(`dead controls      : ${s.deadControls}`);
  console.log(`click errors       : ${s.clickErrors} (non-actionable — not dead)`);
  console.log(`axe violations     : ${s.axeViolations}`);
  console.log(`page errors        : ${s.pageErrors}`);
  console.log(`visual regressions : ${s.visualRegressions}`);
  if (s.pageErrors > 0) {
    for (const e of report.pageErrors) console.log(`  PAGEERROR [${e.screen}] ${e.name || 'Error'}: ${e.message}`);
  }
}

async function main() {
  const { values } = parseArgs({
    options: {
      url: { type: 'string' },
      screens: { type: 'string', default: '/' },
      out: { type: 'string', default: './ui-audit-out' },
      baseline: { type: 'string' },
      'include-low-confidence': { type: 'boolean', default: false },
      'wait-selector': { type: 'string' },
      settle: { type: 'string' },
      tags: { type: 'string' },
      id: { type: 'string' },
    },
    strict: false,
  });

  if (!values.url) {
    console.error('[run_audit] ERROR: --url <url> required (point at the live app / Vite renderer port)');
    process.exit(1);
  }

  const id = values.id || String(Date.now()).slice(-6);
  const report = await runAudit(values.url, {
    id,
    screens: (values.screens || '/').split(',').map(s => s.trim()).filter(Boolean),
    out: values.out,
    baseline: values.baseline,
    includeLowConfidence: !!values['include-low-confidence'],
    waitSelector: values['wait-selector'],
    settleMs: values.settle != null ? Number(values.settle) : undefined,
    tags: values.tags ? values.tags.split(',').map(t => t.trim()) : undefined,
  });

  printSummary(report);
  if (values.out) console.log(`\n[run_audit] annotated findings → ${resolve(values.out)}/audit.json`);
  if (!values['include-low-confidence']) {
    console.log('(low-confidence sub-pixel spacing suppressed — pass --include-low-confidence to include)');
  }
  console.log(`\nSUCCESS:${report.id}`);
}

const __filename = fileURLToPath(import.meta.url);
if (process.argv[1] && resolve(process.argv[1]) === resolve(__filename)) {
  const id = (() => {
    const ix = process.argv.indexOf('--id');
    return ix >= 0 ? process.argv[ix + 1] : String(Date.now()).slice(-6);
  })();
  main().catch(err => {
    console.error(`FAILED:ui-audit-${id} ${err.message}`);
    process.exit(1);
  });
}
