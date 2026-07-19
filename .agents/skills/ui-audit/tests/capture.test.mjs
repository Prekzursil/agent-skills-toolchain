/**
 * capture.test.mjs — BUG 3 regression test for SPA-renderer robustness.
 *
 * Serves fixtures/spa_fixture.html (empty #root that hydrates asynchronously,
 * emits a console error during load, and throws an uncaught "render crash").
 * The old capture.mjs needed manual patching for exactly this shape (Reframe's
 * Vite-served React renderer). The hardened capture must, WITHOUT patch files:
 *   - wait for the app to actually render before snapshotting (so elements are
 *     present, not an empty shell);
 *   - record console errors that occur DURING load;
 *   - capture an uncaught exception as a pageError (crash -> recorded cause, not
 *     an empty bundle);
 *   - expose --wait-selector / settle and capture inline styles.
 */

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { captureUrl } from '../capture.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixturePath = join(__dirname, '../fixtures/spa_fixture.html');

let server;
let baseUrl;

before(async () => {
  const html = readFileSync(fixturePath, 'utf8');
  server = createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(html);
  });
  await new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => {
      baseUrl = `http://127.0.0.1:${server.address().port}`;
      resolve();
    });
  });
});

after(() => server.close());

test('captureUrl waits for async render (sees hydrated content, not empty shell)', async () => {
  const [bundle] = await captureUrl(baseUrl, { screens: ['/'], settleMs: 600 });
  const selectors = bundle.elements.map(e => e.selector);
  assert.ok(selectors.includes('#app-title'),
    `Expected hydrated #app-title in snapshot. Got: ${JSON.stringify(selectors)}`);
  assert.ok(selectors.includes('#spa-action'), 'Expected hydrated #spa-action button');
});

test('captureUrl records console errors emitted during load', async () => {
  const [bundle] = await captureUrl(baseUrl, { screens: ['/'], settleMs: 600 });
  assert.ok(
    bundle.consoleMsgs.some(m => /synthetic console error during load/.test(m.text)),
    `Expected the load-time console error to be captured. Got: ${JSON.stringify(bundle.consoleMsgs)}`,
  );
});

test('captureUrl captures an uncaught exception as a pageError (Reframe crash)', async () => {
  const [bundle] = await captureUrl(baseUrl, { screens: ['/'], settleMs: 600 });
  assert.ok(Array.isArray(bundle.pageErrors), 'bundle.pageErrors must exist');
  assert.ok(
    bundle.pageErrors.some(e => /render crash/.test(e.message)),
    `Expected the render crash in pageErrors. Got: ${JSON.stringify(bundle.pageErrors)}`,
  );
});

test('--wait-selector short-circuits the render wait', async () => {
  const [bundle] = await captureUrl(baseUrl, {
    screens: ['/'], waitSelector: '#app-title', settleMs: 0,
  });
  assert.ok(bundle.elements.some(e => e.selector === '#app-title'),
    'wait-selector should block until the target renders');
});

test('captured elements include inline style (for authored-spacing detection)', async () => {
  const [bundle] = await captureUrl(baseUrl, { screens: ['/'], settleMs: 600 });
  const title = bundle.elements.find(e => e.selector === '#app-title');
  assert.ok(title, '#app-title element expected');
  assert.ok(/margin/.test(title.inlineStyle || ''),
    `Expected inline style captured. Got: ${JSON.stringify(title.inlineStyle)}`);
});

test('bundle keeps its core shape (screen, url, elements, consoleMsgs, networkRequests)', async () => {
  const [bundle] = await captureUrl(baseUrl, { screens: ['/'], settleMs: 400 });
  assert.equal(bundle.screen, 'home');
  assert.ok(typeof bundle.url === 'string');
  assert.ok(Array.isArray(bundle.elements));
  assert.ok(Array.isArray(bundle.consoleMsgs));
  assert.ok(Array.isArray(bundle.networkRequests));
});
