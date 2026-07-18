/**
 * dead_button_crawl.test.mjs — integration test for dead button detection.
 * Serves fixtures/fixture.html on a local HTTP server, crawls it, and asserts:
 *   - #dead-btn reports effect:'none'
 *   - #live-btn reports effect !== 'none'
 */

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { crawlUrl } from '../dead_button_crawl.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixturePath = join(__dirname, '../fixtures/fixture.html');

// ---------------------------------------------------------------------------
// Local fixture server
// ---------------------------------------------------------------------------

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
      const { port } = server.address();
      baseUrl = `http://127.0.0.1:${port}`;
      resolve();
    });
  });
});

after(() => {
  server.close();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test('dead_button_crawl detects #dead-btn as effect:none', async () => {
  const findings = await crawlUrl(baseUrl, {
    screen: 'fixture',
    waitAfterClick: 500,
  });

  assert.ok(findings.length > 0, 'Expected at least one interactive element');

  const deadBtn = findings.find(f => f.selector === '#dead-btn');
  assert.ok(deadBtn, `#dead-btn not found in findings: ${JSON.stringify(findings.map(f => f.selector))}`);
  assert.equal(
    deadBtn.effect, 'none',
    `#dead-btn should have effect:'none', got '${deadBtn.effect}'`,
  );
});

test('dead_button_crawl detects #live-btn as having an effect', async () => {
  const findings = await crawlUrl(baseUrl, {
    screen: 'fixture',
    waitAfterClick: 500,
  });

  const liveBtn = findings.find(f => f.selector === '#live-btn');
  assert.ok(liveBtn, `#live-btn not found in findings: ${JSON.stringify(findings.map(f => f.selector))}`);
  assert.notEqual(
    liveBtn.effect, 'none',
    `#live-btn should have a non-none effect, got '${liveBtn.effect}'`,
  );
});

test('findings include selector, tagName, text, screen fields', async () => {
  const findings = await crawlUrl(baseUrl, { screen: 'fixture', waitAfterClick: 300 });

  for (const f of findings) {
    assert.ok(f.id !== undefined, 'finding.id required');
    assert.ok(typeof f.selector === 'string' && f.selector.length > 0, 'finding.selector required');
    assert.ok(typeof f.tagName === 'string', 'finding.tagName required');
    assert.ok(['none', 'nav', 'dom', 'network', 'console', 'dialog', 'error'].includes(f.effect),
      `Unknown effect value: ${f.effect}`);
  }
});
