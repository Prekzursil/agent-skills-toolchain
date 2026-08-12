#!/usr/bin/env node
/**
 * axe_scan.mjs — run @axe-core/playwright against each captured page.
 *
 * CLI usage:
 *   node axe_scan.mjs --url http://localhost:3000 [--out ./out/axe.json]
 *
 * Programmatic usage:
 *   import { scanUrl } from './axe_scan.mjs';
 *   const violations = await scanUrl('http://localhost:3000');
 *   // violations: array of axe-core Violation objects
 *
 * Degrades gracefully if @axe-core/playwright is not installed — returns [] and logs
 * a warning.  Install with: npm i @axe-core/playwright
 */

import { resolve, join } from 'node:path';
import { writeFileSync, mkdirSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';
import { realpathSync } from 'node:fs';

/**
 * Run axe-core against a URL and return WCAG violations.
 * @param {string} url
 * @param {object} opts - { screen?, tags?, launchOptions? }
 * @returns {Promise<Array>}  axe-core Violation[]
 */
export async function scanUrl(url, opts = {}) {
  let chromium, AxeBuilder;

  try {
    ({ chromium } = await import('playwright'));
  } catch {
    console.warn('[axe_scan] playwright not installed — skipping axe gate');
    return [];
  }

  try {
    ({ AxeBuilder } = await import('@axe-core/playwright'));
  } catch {
    console.warn('[axe_scan] @axe-core/playwright not installed — skipping axe gate');
    console.warn('[axe_scan] Install with: npm i @axe-core/playwright');
    return [];
  }

  const browser = await chromium.launch(opts.launchOptions);
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
    try { await page.waitForLoadState('networkidle', { timeout: 4000 }); } catch { /* OK */ }

    let builder = new AxeBuilder({ page });
    if (opts.tags && opts.tags.length) {
      builder = builder.withTags(opts.tags);
    }

    const results = await builder.analyze();
    return results.violations;
  } finally {
    await browser.close().catch(() => {});
  }
}

// ---------------------------------------------------------------------------
// CLI entrypoint
// ---------------------------------------------------------------------------

async function main() {
  const { values } = parseArgs({
    options: {
      url: { type: 'string' },
      screen: { type: 'string', default: 'page' },
      tags: { type: 'string' },   // e.g. "wcag2a,wcag2aa"
      out: { type: 'string' },
    },
    strict: false,
  });

  if (!values.url) {
    console.error('[axe_scan] ERROR: --url <url> required');
    process.exit(1);
  }

  const tags = values.tags ? values.tags.split(',').map(t => t.trim()) : undefined;
  console.log(`[axe_scan] Scanning ${values.url} …`);
  const violations = await scanUrl(values.url, { screen: values.screen, tags });

  if (violations.length === 0) {
    console.log('[axe_scan] No violations found.');
  } else {
    console.log(`\n${violations.length} violation(s):`);
    for (const v of violations) {
      console.log(`  [${v.impact?.toUpperCase() ?? 'UNKNOWN'}] ${v.id}: ${v.description}`);
      for (const node of (v.nodes || []).slice(0, 3)) {
        console.log(`    • ${node.target?.[0] ?? '?'}: ${node.failureSummary?.split('\n')[0]}`);
      }
    }
  }

  if (values.out) {
    const outPath = resolve(values.out);
    if (outPath.endsWith('.json')) {
      writeFileSync(outPath, JSON.stringify({ violations }, null, 2));
    } else {
      mkdirSync(outPath, { recursive: true });
      writeFileSync(join(outPath, `${values.screen}-axe.json`), JSON.stringify({ violations }, null, 2));
    }
  }

  console.log(`\nSUCCESS:axe-scan`);
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
  main().catch(err => {
    console.error(`FAILED:axe-scan ${err.message}`);
    process.exit(1);
  });
}
