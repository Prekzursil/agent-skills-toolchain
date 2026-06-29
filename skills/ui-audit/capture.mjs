#!/usr/bin/env node
/**
 * capture.mjs — evidence bundle capture per screen.
 *
 * Usage (web / SPA app):
 *   node capture.mjs --url http://localhost:3000 --screens /,/settings,/about --out ./ui-audit-out
 *   node capture.mjs --url http://localhost:5173 --wait-selector "#root > *" --settle 500 --out ./ui-audit-out
 *
 * Usage (Electron app):
 *   node capture.mjs --electron ./path/to/main.js --out ./ui-audit-out
 *
 * Programmatic usage (importable, no CLI / no disk required):
 *   import { captureUrl, captureElectron } from './capture.mjs';
 *   const bundles = await captureUrl('http://localhost:5173', { screens: ['/'], waitSelector: '#root' });
 *
 * Writes per screen into <outDir>/<screenName>.bundle.json + <screenName>.png.
 *
 * Bundle shape:
 *   { screen, url, timestamp, screenshotPath, a11ySnapshot, elements[],
 *     consoleMsgs[], networkRequests[], pageErrors[] }
 *
 * elements[]: [{ selector, tagName, textContent, isInteractive, inlineStyle, styles }]
 *   styles includes margins, paddings, gap/rowGap/columnGap, fontSize, fontWeight,
 *   lineHeight, color, backgroundColor, width, height, _rect: {width,height,x,y}
 *
 * BUG-3 robustness for SPA renderers (e.g. Reframe's Vite-served React window):
 *   - console / pageerror / network recorders are attached BEFORE navigation, so a
 *     crash or load-time console error is captured (not an empty bundle);
 *   - the snapshot waits for the app to actually render (networkidle + an optional
 *     --wait-selector + a short --settle delay) before reading the DOM.
 *   Both --url and --electron paths work without any external patch file.
 */

import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';

const STYLE_PROPS = [
  'marginTop', 'marginBottom', 'marginLeft', 'marginRight',
  'paddingTop', 'paddingBottom', 'paddingLeft', 'paddingRight',
  'gap', 'rowGap', 'columnGap',
  'fontSize', 'fontWeight', 'lineHeight',
  'color', 'backgroundColor',
  'width', 'height',
  'display', 'position',
];

const MAX_ELEMENTS = 250;
const DEFAULT_SETTLE_MS = 300;
const DEFAULT_NETWORK_IDLE_TIMEOUT = 6000;

/**
 * Attach console / pageerror / network recorders to a page.
 * MUST be called BEFORE navigation so load-time output is captured.
 */
function attachRecorders(page) {
  const consoleMsgs = [];
  const networkRequests = [];
  const pageErrors = [];

  page.on('console', msg => consoleMsgs.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', err => {
    const rec = { name: err.name || 'Error', message: err.message || String(err) };
    pageErrors.push(rec);
    // Surface uncaught exceptions in consoleMsgs too — a crash must never produce
    // a silent, empty bundle.
    consoleMsgs.push({ type: 'error', text: `[pageerror] ${rec.name}: ${rec.message}` });
  });
  page.on('response', resp => {
    const status = resp.status();
    networkRequests.push({ url: resp.url(), status, flagged: status >= 400 });
  });
  page.on('requestfailed', req => {
    networkRequests.push({
      url: req.url(), status: 0, flagged: true,
      failure: req.failure()?.errorText || 'request failed',
    });
  });

  return { consoleMsgs, networkRequests, pageErrors };
}

/**
 * Wait for an SPA to actually render before snapshotting.
 */
async function waitForRender(page, { waitSelector, settleMs = DEFAULT_SETTLE_MS, networkIdleTimeout = DEFAULT_NETWORK_IDLE_TIMEOUT } = {}) {
  try { await page.waitForLoadState('networkidle', { timeout: networkIdleTimeout }); } catch { /* timeout OK */ }
  if (waitSelector) {
    try { await page.waitForSelector(waitSelector, { timeout: 8000, state: 'attached' }); } catch { /* selector may not appear — record what we have */ }
  }
  if (settleMs > 0) await new Promise(r => setTimeout(r, settleMs));
}

async function getComputedStyles(page) {
  return page.evaluate(({ props, maxEls }) => {
    const INTERACTIVE_TAGS = new Set(['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA']);
    const els = Array.from(document.querySelectorAll('*')).slice(0, maxEls);
    return els.map(el => {
      const cs = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      const styles = {};
      for (const p of props) styles[p] = cs[p] || null;
      styles._rect = { width: rect.width, height: rect.height, x: rect.x, y: rect.y };

      // Build a best-effort unique selector
      let sel = el.tagName.toLowerCase();
      if (el.id) sel = '#' + el.id;
      else if (el.className && typeof el.className === 'string' && el.className.trim()) {
        sel = el.tagName.toLowerCase() + '.' + el.className.trim().split(/\s+/).join('.');
      }

      return {
        selector: sel,
        tagName: el.tagName,
        textContent: (el.textContent || '').slice(0, 100).trim(),
        isInteractive: INTERACTIVE_TAGS.has(el.tagName) ||
          el.getAttribute('role') === 'button' ||
          (el.getAttribute('tabindex') != null && el.getAttribute('tabindex') !== '-1'),
        // Inline style enables authored-vs-computed spacing discrimination in layout_lint.
        inlineStyle: el.getAttribute('style') || '',
        styles,
      };
    });
  }, { props: STYLE_PROPS, maxEls: MAX_ELEMENTS });
}

/**
 * Snapshot a (already-navigated) page into a bundle. Writes screenshot + bundle
 * JSON when outDir is provided; otherwise returns the bundle in-memory.
 * @param {object} rec - recorders returned by attachRecorders (attached pre-nav)
 */
async function buildBundle(page, screenName, rec, opts = {}) {
  const { outDir = null, waitSelector, settleMs, networkIdleTimeout } = opts;

  await waitForRender(page, { waitSelector, settleMs, networkIdleTimeout });

  let screenshotPath = null;
  if (outDir) {
    mkdirSync(outDir, { recursive: true });
    screenshotPath = join(outDir, `${screenName}.png`);
    try { await page.screenshot({ path: screenshotPath, fullPage: true }); } catch { screenshotPath = null; }
  }

  let a11ySnapshot = null;
  try { a11ySnapshot = await page.accessibility.snapshot(); } catch { /* optional */ }

  const elements = await getComputedStyles(page);

  const bundle = {
    screen: screenName,
    url: page.url(),
    timestamp: new Date().toISOString(),
    screenshotPath,
    a11ySnapshot,
    elements,
    consoleMsgs: rec.consoleMsgs,
    networkRequests: rec.networkRequests,
    pageErrors: rec.pageErrors,
  };

  if (outDir) {
    writeFileSync(join(outDir, `${screenName}.bundle.json`), JSON.stringify(bundle, null, 2));
    const errNote = rec.pageErrors.length ? ` (${rec.pageErrors.length} page error(s) captured)` : '';
    console.log(`[capture] "${screenName}" → ${outDir}/${screenName}.bundle.json${errNote}`);
  }
  return bundle;
}

function screenNameFor(screen) {
  return screen
    .replace(/^https?:\/\/[^/]+/, '')
    .replace(/^\//, '')
    .replace(/[/?#]/g, '_') || 'home';
}

/**
 * Capture one or more screens of a web/SPA app.
 * @returns {Promise<Array<object>>} bundles
 */
export async function captureUrl(url, opts = {}) {
  const {
    screens = ['/'], out = null, waitSelector,
    settleMs = DEFAULT_SETTLE_MS, networkIdleTimeout = DEFAULT_NETWORK_IDLE_TIMEOUT,
    launchOptions,
  } = opts;

  const browser = await chromium.launch(launchOptions);
  try {
    const context = await browser.newContext();
    const baseUrl = url.replace(/\/$/, '');
    const bundles = [];

    for (const screen of screens) {
      const page = await context.newPage();
      const rec = attachRecorders(page);   // attach BEFORE navigation

      const fullUrl = /^https?:\/\//.test(screen)
        ? screen
        : baseUrl + (screen.startsWith('/') ? screen : '/' + screen);
      const screenName = screenNameFor(screen);

      try {
        await page.goto(fullUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
      } catch (e) {
        const msg = String(e.message).split('\n')[0];
        rec.pageErrors.push({ name: 'NavigationError', message: msg });
        rec.consoleMsgs.push({ type: 'error', text: `[navigation] ${msg}` });
      }

      const bundle = await buildBundle(page, screenName, rec, { outDir: out, waitSelector, settleMs, networkIdleTimeout });
      bundles.push(bundle);
      await page.close().catch(() => {});
    }

    return bundles;
  } finally {
    await browser.close().catch(() => {});
  }
}

/**
 * Capture the first window of an Electron app.
 * @returns {Promise<object>} bundle
 */
export async function captureElectron(entry, opts = {}) {
  const { out = null, waitSelector, settleMs = DEFAULT_SETTLE_MS, networkIdleTimeout = DEFAULT_NETWORK_IDLE_TIMEOUT } = opts;

  const pw = await import('playwright');
  const electronLauncher = pw._electron;
  if (!electronLauncher) throw new Error('_electron not exported by playwright');

  const app = await electronLauncher.launch({ args: [resolve(entry)] });
  try {
    const page = await app.firstWindow();
    const rec = attachRecorders(page);   // firstWindow resolves at window creation; the
    // renderer (and any crash) finishes after — waitForRender below captures it.
    return await buildBundle(page, 'main', rec, { outDir: out, waitSelector, settleMs, networkIdleTimeout });
  } finally {
    await app.close().catch(() => {});
  }
}

// ---------------------------------------------------------------------------
// CLI entrypoint
// ---------------------------------------------------------------------------

async function main() {
  const { values } = parseArgs({
    options: {
      url: { type: 'string' },
      electron: { type: 'string' },
      screens: { type: 'string', default: '/' },
      out: { type: 'string', default: './ui-audit-out' },
      'wait-selector': { type: 'string' },
      settle: { type: 'string' },
    },
    strict: false,
  });

  const outDir = resolve(values.out);
  const waitSelector = values['wait-selector'];
  const settleMs = values.settle != null ? Number(values.settle) : undefined;

  if (values.electron) {
    try {
      await captureElectron(values.electron, { out: outDir, waitSelector, settleMs });
    } catch (err) {
      console.error(`[capture] Cannot launch Electron app: ${err.message}`);
      console.error('[capture] Ensure playwright is installed: npm i playwright');
      process.exit(1);
    }
  } else if (values.url) {
    const screens = (values.screens || '/').split(',').map(s => s.trim()).filter(Boolean);
    await captureUrl(values.url, { screens, out: outDir, waitSelector, settleMs });
  } else {
    console.error('[capture] ERROR: provide --url <url> or --electron <path>');
    process.exit(1);
  }

  console.log('SUCCESS:capture');
}

const __filename = fileURLToPath(import.meta.url);
if (process.argv[1] && resolve(process.argv[1]) === resolve(__filename)) {
  main().catch(err => {
    console.error(`FAILED:capture ${err.message}`);
    process.exit(1);
  });
}
