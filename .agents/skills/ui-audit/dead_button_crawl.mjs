#!/usr/bin/env node
/**
 * dead_button_crawl.mjs — enumerate interactive elements and detect dead/unwired controls.
 *
 * CLI usage:
 *   node dead_button_crawl.mjs --url http://localhost:3000/page --out ./out/dead.json
 *   node dead_button_crawl.mjs --url http://localhost:3000/page --screen home --out ./out
 *   node dead_button_crawl.mjs --url http://localhost:3000 --wait-selector "#root" --out ./out
 *
 * Programmatic usage:
 *   import { crawlUrl } from './dead_button_crawl.mjs';
 *   const findings = await crawlUrl('http://localhost:3000');
 *
 * Finding shape: { id, selector, tagName, text, screen, effect, clickError? }
 *   effect: 'none' | 'nav' | 'dom' | 'network' | 'console' | 'dialog' | 'error'
 *   selector: a STABLE identifier (NOT a regenerated nth-of-type selector) derived
 *             by preference id > [data-testid] > [aria-label] > visible text > tag.class
 *
 * Strategy (BUG-1 fix):
 *   Component frameworks (Angular/React) render trees where a regenerated
 *   `a:nth-of-type(1)` selector matches the first <a> inside EVERY container, so
 *   Playwright strict-mode silently rejects the click and the old crawler reported
 *   effect:'none' for everything. We therefore crawl by ELEMENT HANDLE: for each
 *   element index we open a fresh isolated context, re-query the interactive set,
 *   click `handles[i]` DIRECTLY (no ambiguous selector), and observe the
 *   URL / DOM-mutation / network / console / dialog delta in a tight click window.
 *   A click that fails to execute is reported as effect:'error' (never as a false
 *   'none' dead control).
 *
 * Degrades gracefully if playwright is not installed — exits with FAILED: prefix.
 */

import { resolve, join } from 'node:path';
import { writeFileSync, mkdirSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';
import { realpathSync } from 'node:fs';

// Interactive set: native controls + ARIA roles + component-framework hooks
// ([onclick] inline handlers, [routerLink] Angular nav). querySelectorAll dedupes,
// so an element matching multiple clauses is returned once, in document order.
const INTERACTIVE_SEL =
  'a, button, input:not([type="hidden"]), select, textarea, ' +
  '[role="button"], [role="link"], [role="menuitem"], [onclick], [routerLink]';

/**
 * Source for the in-page identifier deriver. Inlined (not eval'd) inside the
 * discovery page.evaluate so it is CSP-safe. Preference order:
 *   id > data-testid > aria-label > visible text > tag + short class list > tag[name].
 */

/**
 * Navigate + wait for an (SPA) app to actually render before inspecting it.
 */
async function gotoAndSettle(page, url, { waitSelector, settleMs = 300, timeout = 15000 } = {}) {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout });
  try { await page.waitForLoadState('networkidle', { timeout: 4000 }); } catch { /* OK */ }
  if (waitSelector) {
    try { await page.waitForSelector(waitSelector, { timeout: 5000 }); } catch { /* OK */ }
  }
  if (settleMs > 0) await new Promise(r => setTimeout(r, settleMs));
}

/**
 * Crawl a URL and return dead-button findings.
 * @param {string} url  - page to crawl
 * @param {object} opts - { screen?, timeout?, waitAfterClick?, waitSelector?, settleMs?, launchOptions? }
 * @returns {Promise<Array<{id,selector,tagName,text,screen,effect}>>}
 */
export async function crawlUrl(url, opts = {}) {
  const { chromium } = await import('playwright').catch(() => {
    throw new Error('playwright not installed — run: npm i playwright && npx playwright install chromium');
  });

  const screen = opts.screen || 'page';
  const clickTimeout = opts.timeout ?? 2000;
  const waitAfterClick = opts.waitAfterClick ?? 400;
  const waitSelector = opts.waitSelector;
  const settleMs = opts.settleMs ?? 300;

  const browser = await chromium.launch(opts.launchOptions);

  try {
    // --- Discovery pass: collect identifier + metadata for each element ---
    const discoveryCtx = await browser.newContext();
    const discoveryPage = await discoveryCtx.newPage();
    await gotoAndSettle(discoveryPage, url, { waitSelector, settleMs });

    const elements = await discoveryPage.evaluate((sel) => {
      // Inlined identifier deriver — CSP-safe (no eval/new Function).
      const describe = (el) => {
        if (el.id) return '#' + el.id;
        const testid = el.getAttribute('data-testid') || el.getAttribute('data-test-id');
        if (testid) return '[data-testid="' + testid + '"]';
        const aria = el.getAttribute('aria-label');
        if (aria && aria.trim()) return '[aria-label="' + aria.trim() + '"]';
        const tag = el.tagName.toLowerCase();
        const text = (el.textContent || '').replace(/\s+/g, ' ').trim();
        if (text) return tag + ':"' + text.slice(0, 40) + '"';
        if (el.classList && el.classList.length) {
          return tag + '.' + Array.from(el.classList).slice(0, 3).join('.');
        }
        const name = el.getAttribute('name');
        if (name) return tag + '[name="' + name + '"]';
        return tag;
      };
      const els = Array.from(document.querySelectorAll(sel));
      return els.map((el, i) => ({
        index: i,
        selector: describe(el),
        tagName: el.tagName,
        text: (el.textContent || el.value || el.getAttribute('aria-label') || '')
          .replace(/\s+/g, ' ').slice(0, 80).trim(),
      }));
    }, INTERACTIVE_SEL);

    await discoveryCtx.close();

    // --- Click-test pass: one fresh isolated context per element ---
    const findings = [];
    let idCounter = 0;

    for (let i = 0; i < elements.length; i++) {
      const elem = elements[i];
      const testCtx = await browser.newContext();
      const testPage = await testCtx.newPage();

      let dialogOpened = false;
      let reqCount = 0;
      let consoleCount = 0;

      // Dismiss dialogs (so click doesn't hang) but record that one opened.
      testPage.on('dialog', dlg => { dialogOpened = true; dlg.dismiss().catch(() => {}); });

      const onReq = () => { reqCount++; };
      const onConsole = () => { consoleCount++; };
      // An UNCAUGHT handler throw surfaces as 'pageerror', NOT as a console event
      // (measured). Such a control is WIRED BUT BROKEN — a different defect from a
      // dead one — so it is reported as its own flag rather than folded into effect.
      const pageErrors = [];
      const onPageError = (e) => { pageErrors.push((e && e.message) ? e.message.split('\n')[0] : String(e)); };

      try {
        await gotoAndSettle(testPage, url, { waitSelector, settleMs });

        // Install a mutation RECORDER (not a bare counter) — see BUG-2 below.
        await testPage.evaluate(() => {
          window.__uiAuditSigs = new Set();
          // A stable per-mutation signature: type + element identity + a shallow
          // child-index path. Ambient churn (a ticking clock, a polling list)
          // re-emits the SAME signature every tick, so it can be subtracted;
          // a click that appends a node emits a signature the ambient set lacks.
          const sig = (m) => {
            const el = m.target instanceof Element
              ? m.target
              : (m.target && m.target.parentElement) || null;
            if (!el) return m.type + '|<detached>';
            let path = '';
            let node = el;
            for (let d = 0; d < 4 && node && node.parentElement; d++) {
              path = Array.prototype.indexOf.call(node.parentElement.children, node) + '/' + path;
              node = node.parentElement;
            }
            const cls = el.classList ? Array.from(el.classList).slice(0, 3).join('.') : '';
            return m.type + '|' + el.tagName + '#' + (el.id || '') + '.' + cls + '|' + path;
          };
          if (window.__uiAuditMo) window.__uiAuditMo.disconnect();
          window.__uiAuditMo = new MutationObserver((recs) => {
            for (const m of recs) window.__uiAuditSigs.add(sig(m));
          });
          window.__uiAuditMo.observe(document.documentElement, {
            childList: true, subtree: true, attributes: true, characterData: true,
          });
        });

        testPage.on('request', onReq);
        testPage.on('console', onConsole);
        testPage.on('pageerror', onPageError);

        // --- BUG-2 fix: ambient-noise control window ---------------------------
        // Observe for the SAME duration WITHOUT clicking, to learn what this page
        // mutates on its own. Measured motivation: against a page with a 100ms
        // ticker, the old bare-count classifier reported effect:'dom' for EVERY
        // control and found 0 of 2 planted dead buttons — a false green on any
        // app that polls or animates. The no-click window is the control that
        // makes the post-click reading mean something.
        reqCount = 0;
        await new Promise(r => setTimeout(r, waitAfterClick));
        let noiseSigs = [];
        try { noiseSigs = await testPage.evaluate(() => Array.from(window.__uiAuditSigs)); } catch { /* OK */ }
        const noiseReq = reqCount;

        // Re-query handles on THIS fresh page and click the exact element by handle.
        // No selector string is passed to click(), so strict-mode ambiguity is impossible.
        const handles = await testPage.$$(INTERACTIVE_SEL);
        const handle = handles[i];

        // Zero the counters at the click instant to tighten the observation window.
        reqCount = 0;
        consoleCount = 0;
        dialogOpened = false;
        pageErrors.length = 0;
        try { await testPage.evaluate(() => { window.__uiAuditSigs.clear(); }); } catch { /* OK */ }

        const urlBefore = testPage.url();
        let clickError = null;

        if (handle) {
          try {
            await handle.click({ timeout: clickTimeout });
          } catch (e) {
            clickError = e.message.split('\n')[0];
          }
        } else {
          clickError = `element index ${i} absent at click time (found ${handles.length})`;
        }

        await new Promise(r => setTimeout(r, waitAfterClick));

        const urlAfter = testPage.url();
        const navHappened = urlAfter !== urlBefore;

        let postSigs = [];
        if (!navHappened) {
          try { postSigs = await testPage.evaluate(() => Array.from(window.__uiAuditSigs)); } catch { /* navigated mid-eval */ }
        }
        // Subtract the ambient set: only mutations this page did NOT do on its own
        // count as an effect of the click. Errs toward reporting MORE dead controls
        // (a click that only touches an ambiently-churning node reads as 'none'),
        // which is the safe direction — a false 'dead' gets filtered by review,
        // whereas a false 'alive' silently hides a real broken control.
        const noiseSet = new Set(noiseSigs);
        const attributed = postSigs.filter(s => !noiseSet.has(s));

        let effect;
        if (navHappened) effect = 'nav';
        else if (dialogOpened) effect = 'dialog';
        else if (attributed.length > 0) effect = 'dom';
        else if (reqCount > noiseReq) effect = 'network';
        else if (consoleCount > 0) effect = 'console';
        else if (clickError) effect = 'error';   // click failed AND nothing observed -> uncertain, NOT dead
        else effect = 'none';

        const finding = {
          id: `dead-${idCounter++}`,
          selector: elem.selector,
          tagName: elem.tagName,
          text: elem.text,
          screen,
          effect,
          // Evidence for the classification, so a reader can audit it instead of
          // trusting the label: how noisy the page was vs what the click added.
          noise: { mutationSigs: noiseSigs.length, requests: noiseReq },
          attributedMutations: attributed.length,
        };
        if (pageErrors.length) {
          finding.pageError = true;
          finding.pageErrorMessage = pageErrors[0];
        }
        if (clickError) finding.clickError = clickError;
        findings.push(finding);
      } catch (err) {
        findings.push({
          id: `dead-${idCounter++}`,
          selector: elem.selector,
          tagName: elem.tagName,
          text: elem.text,
          screen,
          effect: 'error',
          error: err.message,
        });
      } finally {
        testPage.off('request', onReq);
        testPage.off('console', onConsole);
        testPage.off('pageerror', onPageError);
        await testPage.close().catch(() => {});
        await testCtx.close().catch(() => {});
      }
    }

    return findings;
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
      'wait-selector': { type: 'string' },
      settle: { type: 'string' },
      out: { type: 'string' },
    },
    strict: false,
  });

  if (!values.url) {
    console.error('[dead_button_crawl] ERROR: --url <url> required');
    process.exit(1);
  }

  console.log(`[dead_button_crawl] Crawling ${values.url} …`);
  const findings = await crawlUrl(values.url, {
    screen: values.screen,
    waitSelector: values['wait-selector'],
    settleMs: values.settle != null ? Number(values.settle) : undefined,
  });

  const dead = findings.filter(f => f.effect === 'none');
  const errored = findings.filter(f => f.effect === 'error');
  const throwing = findings.filter(f => f.pageError);
  const noisiest = findings.reduce((m, f) => Math.max(m, f.noise?.mutationSigs ?? 0), 0);
  console.log(`\nFound ${dead.length} dead control(s) out of ${findings.length} interactive elements` +
    (errored.length ? ` (${errored.length} not actionable — reported as 'error', not 'dead')` : '') + ':');
  for (const f of dead) {
    console.log(`  DEAD  ${f.selector}  (${f.tagName}) "${f.text}"`);
  }
  // A wired-but-throwing control is a DIFFERENT defect from a dead one; report it
  // separately so it cannot hide inside a reassuring "0 dead" headline.
  if (throwing.length) {
    console.log(`\n${throwing.length} control(s) raised an uncaught page error when clicked:`);
    for (const f of throwing) {
      console.log(`  THROWS  ${f.selector}  (${f.tagName}) "${f.text}" -> ${f.pageErrorMessage}`);
    }
  }
  // Disclose the ambient-noise level: a high number means the page churns on its
  // own, so the classification leaned heavily on noise subtraction. Silence here
  // would let a reader assume a quiet page.
  console.log(`\nAmbient noise: up to ${noisiest} mutation signature(s) per no-click control window.`);

  if (values.out) {
    const outPath = resolve(values.out);
    if (outPath.endsWith('.json')) {
      writeFileSync(outPath, JSON.stringify({ findings }, null, 2));
    } else {
      mkdirSync(outPath, { recursive: true });
      writeFileSync(join(outPath, `${values.screen}-dead.json`), JSON.stringify({ findings }, null, 2));
    }
  }

  console.log('\nSUCCESS:dead-button-crawl');
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
    console.error(`FAILED:dead-button-crawl ${err.message}`);
    process.exit(1);
  });
}
