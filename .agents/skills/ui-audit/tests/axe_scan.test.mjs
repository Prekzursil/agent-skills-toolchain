/**
 * axe_scan.test.mjs — integration test for WCAG accessibility scanning.
 * Serves fixtures/fixture.html on a local HTTP server, runs axe-core, and asserts:
 *   - A 'color-contrast' violation is reported (the #ccc-on-#fff element)
 */

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { scanUrl } from '../axe_scan.mjs';

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

test('axe_scan returns an array of violations', async () => {
  const violations = await scanUrl(baseUrl);
  assert.ok(Array.isArray(violations), 'scanUrl should return an array');
});

test('axe_scan flags color-contrast violation from #low-contrast element', async () => {
  const violations = await scanUrl(baseUrl);

  const contrastViolation = violations.find(v => v.id === 'color-contrast');
  assert.ok(
    contrastViolation,
    `Expected a 'color-contrast' violation. Got violations: ${JSON.stringify(violations.map(v => v.id))}`,
  );
  assert.ok(
    ['serious', 'critical'].includes(contrastViolation.impact),
    `Expected serious/critical impact, got '${contrastViolation.impact}'`,
  );
});

test('axe violations have required fields', async () => {
  const violations = await scanUrl(baseUrl);

  for (const v of violations) {
    assert.ok(typeof v.id === 'string', 'violation.id required');
    assert.ok(typeof v.description === 'string', 'violation.description required');
    assert.ok(Array.isArray(v.nodes), 'violation.nodes required');
    assert.ok(v.impact, 'violation.impact required');
  }
});
