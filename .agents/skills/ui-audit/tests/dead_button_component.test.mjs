/**
 * dead_button_component.test.mjs — BUG 1 regression test.
 *
 * Serves fixtures/component_fixture.html (an Angular/React-style component tree
 * where sibling cards make `a:nth-of-type(1)` / `button:nth-of-type(1)` globally
 * ambiguous). The OLD selector-based crawl reported effect:'none' for EVERY
 * element (strict-mode reject of the ambiguous selector). The handle-based crawl
 * must instead:
 *   - flag only the genuinely dead controls as effect:'none'
 *   - report wired controls (incl. nth-of-type colliders) as a real effect
 *   - never emit a `:nth-of-type` identifier
 *   - derive identifiers via id > data-testid > aria-label > text > tag+class
 */

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { crawlUrl } from '../dead_button_crawl.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixturePath = join(__dirname, '../fixtures/component_fixture.html');

let server;
let baseUrl;
let findings;

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
  // Crawl once; reuse findings across assertions (each click runs on a fresh page).
  findings = await crawlUrl(baseUrl, { screen: 'component', waitAfterClick: 400 });
});

after(() => server.close());

const byText = (t) => findings.find(f => f.text === t);
const bySel = (s) => findings.find(f => f.selector === s);

test('discovers the full component tree (handle-based, not 0 elements)', () => {
  // 1 brand + 3 links + 3 card buttons + 5 control buttons = 12 interactive els
  assert.equal(findings.length, 12, `Expected 12 elements, got ${findings.length}: ${JSON.stringify(findings.map(f => f.selector))}`);
});

test('nth-of-type colliders Save 1 / Save 2 are NOT false-positive dead', () => {
  // The headline bug: these share `button:nth-of-type(1)` with the dead button.
  assert.equal(byText('Save 1')?.effect, 'dom', `Save 1 should be wired (dom): ${JSON.stringify(byText('Save 1'))}`);
  assert.equal(byText('Save 2')?.effect, 'dom', `Save 2 should be wired (dom): ${JSON.stringify(byText('Save 2'))}`);
});

test('genuinely dead button is flagged effect:none', () => {
  assert.equal(byText('Dead Save')?.effect, 'none', `Dead Save should be none: ${JSON.stringify(byText('Dead Save'))}`);
});

test('exactly the 4 dead controls report effect:none', () => {
  const dead = findings.filter(f => f.effect === 'none').map(f => f.selector).sort();
  assert.deepEqual(
    dead,
    ['[aria-label="Close panel"]', 'button.icon-only', 'button:"Dead Save"', 'button:"Ghost"'].sort(),
    `Unexpected dead set: ${JSON.stringify(findings.map(f => ({ s: f.selector, e: f.effect })))}`,
  );
});

test('identifiers follow id > data-testid > aria-label > text > tag.class (never nth-of-type)', () => {
  assert.equal(bySel('#primary-action')?.effect, 'dom', 'id identifier + wired');
  assert.equal(bySel('[data-testid="submit-cta"]')?.effect, 'dom', 'data-testid identifier + wired');
  assert.equal(bySel('[aria-label="Close panel"]')?.effect, 'none', 'aria-label identifier + dead');
  assert.ok(bySel('button:"Ghost"'), 'visible-text identifier');
  assert.ok(bySel('button.icon-only'), 'tag.class identifier (no text)');
  for (const f of findings) {
    assert.ok(!/:nth-of-type/.test(f.selector), `identifier must not be nth-of-type: ${f.selector}`);
  }
});

test('every finding carries id/selector/tagName/text/screen + valid effect', () => {
  for (const f of findings) {
    assert.ok(f.id !== undefined, 'finding.id required');
    assert.ok(typeof f.selector === 'string' && f.selector.length > 0, 'finding.selector required');
    assert.ok(typeof f.tagName === 'string', 'finding.tagName required');
    assert.equal(f.screen, 'component');
    assert.ok(['none', 'nav', 'dom', 'network', 'console', 'dialog', 'error'].includes(f.effect),
      `Unknown effect: ${f.effect}`);
  }
});
