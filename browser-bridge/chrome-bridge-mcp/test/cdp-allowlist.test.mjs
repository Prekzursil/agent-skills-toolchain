// Hermetic unit gate for the estate CDP allowlist - the security core both the hub and the
// companion extension enforce. The package's full `npm test` needs a live Chrome + extension
// (smoke / multi-client are local-only lanes by design, and the estate's own bridge hub owns
// port 8787 on the dev box); this suite gates the part that can run offline in CI.
//
// Mirrors the hacktricks-mcp-server gate discipline: node --test with all THREE thresholds,
// and every source file under the gate must be IMPORTED by a test (a never-imported file is
// invisible to node coverage - see the measured trap documented in quality.yml).
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  CDP_ALLOWLIST,
  CDP_COOKIE_DENY,
  assertCdpAllowed,
  assertSafePageScript,
} from '../dist/cdp-allowlist.js';

test('allowlist and deny-set are populated and disjoint', () => {
  assert.ok(CDP_ALLOWLIST.size > 20, 'allowlist collapsed');
  assert.ok(CDP_COOKIE_DENY.size > 10, 'deny-set collapsed');
  for (const denied of CDP_COOKIE_DENY) {
    assert.ok(!CDP_ALLOWLIST.has(denied), `${denied} must never appear on the allowlist`);
  }
});

test('assertCdpAllowed: a missing or empty method is rejected before any set lookup', () => {
  assert.throws(() => assertCdpAllowed(null), /CDP method is required/);
  assert.throws(() => assertCdpAllowed(''), /CDP method is required/);
  assert.throws(() => assertCdpAllowed(undefined), /CDP method is required/);
});

test('assertCdpAllowed: named cookie/credential methods are denied explicitly', () => {
  for (const name of ['Network.getAllCookies', 'Storage.clearCookies', 'IndexedDB.requestData']) {
    assert.throws(() => assertCdpAllowed(name), /denied \(cookie\/credential exfil\)/);
  }
});

test('assertCdpAllowed: the suffix regex denies unknown cookie-reading domains too', () => {
  // Not a member of CDP_COOKIE_DENY - caught by the /\.(getAllCookies|...)$/i suffix pattern.
  assert.throws(() => assertCdpAllowed('Foo.getAllCookies'), /denied \(cookie\/credential exfil\)/);
  assert.throws(() => assertCdpAllowed('Bar.setCookies'), /denied \(cookie\/credential exfil\)/);
});

test('assertCdpAllowed: anything not on the allowlist is refused', () => {
  assert.throws(() => assertCdpAllowed('Emulation.setDeviceMetricsOverride'), /not on the estate allowlist/);
});

test('assertCdpAllowed: allowlisted methods pass with or without params', () => {
  assert.doesNotThrow(() => assertCdpAllowed('Page.navigate'));
  assert.doesNotThrow(() => assertCdpAllowed('Page.navigate', null));
});

test('assertCdpAllowed: Runtime.evaluate screens the expression for credential access', () => {
  assert.doesNotThrow(() => assertCdpAllowed('Runtime.evaluate', { expression: '1 + 1' }));
  assert.doesNotThrow(() => assertCdpAllowed('Runtime.evaluate'), 'no params means an empty expression');
  assert.doesNotThrow(() => assertCdpAllowed('Runtime.evaluate', {}), 'absent expression means empty');
  assert.throws(() => assertCdpAllowed('Runtime.evaluate', { expression: 'document . cookie' }), /page script refused/);
});

test('assertCdpAllowed: Runtime.callFunctionOn screens the function declaration', () => {
  assert.doesNotThrow(() => assertCdpAllowed('Runtime.callFunctionOn', { functionDeclaration: '() => 42' }));
  assert.doesNotThrow(() => assertCdpAllowed('Runtime.callFunctionOn', {}), 'absent declaration means empty');
  assert.throws(
    () => assertCdpAllowed('Runtime.callFunctionOn', { functionDeclaration: '() => localStorage.length' }),
    /page script refused/,
  );
});

test('assertSafePageScript: every credential pattern member is refused; clean and nullish pass', () => {
  for (const bad of [
    'document.cookie',
    'document  .  cookie',
    'x = document\n.cookie',
    'o["cookie"]',
    "o['cookie']",
    'cookieStore.get()',
    'window.localStorage',
    'sessionStorage.clear()',
    'indexedDB.open()',
    'navigator.credentials.get()',
    'getAllCookies()',
    'getCookies()',
    'DOMStorage',
  ]) {
    assert.throws(() => assertSafePageScript(bad), /page script refused/, `must refuse: ${bad}`);
  }
  assert.doesNotThrow(() => assertSafePageScript('document.title'));
  assert.doesNotThrow(() => assertSafePageScript(null));
  assert.doesNotThrow(() => assertSafePageScript(undefined));
});
