// Tests for tools/lib/net-allowlist.mjs (K5).
//
// The origin (tools/web/agentify-desktop/http-api.mjs) had a retire-class test file that exercised
// the whole HTTP server; isAllowedRemoteAddress arrives here with dedicated coverage for the first
// time. Written, not ported.

import test from 'node:test';
import assert from 'node:assert/strict';

import { isAllowedRemoteAddress, normalizeRemoteAddress, isPrivateIpv4 } from '../net-allowlist.mjs';

test('net-allowlist: loopback is always allowed', () => {
  assert.equal(isAllowedRemoteAddress('127.0.0.1'), true);
  assert.equal(isAllowedRemoteAddress('::1'), true);
  assert.equal(isAllowedRemoteAddress('::ffff:127.0.0.1'), true);
});

test('net-allowlist: DEFAULT IS DENY for everything non-loopback', () => {
  assert.equal(isAllowedRemoteAddress('10.0.0.5'), false);
  assert.equal(isAllowedRemoteAddress('192.168.1.7'), false);
  assert.equal(isAllowedRemoteAddress('172.16.0.1'), false);
  assert.equal(isAllowedRemoteAddress('fd00::1'), false);
  assert.equal(isAllowedRemoteAddress('8.8.8.8'), false);
});

test('net-allowlist: private ranges admitted only on explicit opt-in', () => {
  const opt = { allowPrivateNetwork: true };
  assert.equal(isAllowedRemoteAddress('10.0.0.5', opt), true);
  assert.equal(isAllowedRemoteAddress('192.168.1.7', opt), true);
  assert.equal(isAllowedRemoteAddress('172.16.0.1', opt), true);
  assert.equal(isAllowedRemoteAddress('172.31.255.254', opt), true);
  assert.equal(isAllowedRemoteAddress('::ffff:10.1.2.3', opt), true);
  // IPv6 unique-local
  assert.equal(isAllowedRemoteAddress('fc00::1', opt), true);
  assert.equal(isAllowedRemoteAddress('fd12:3456::1', opt), true);
});

test('net-allowlist: public addresses stay denied even with opt-in', () => {
  const opt = { allowPrivateNetwork: true };
  assert.equal(isAllowedRemoteAddress('8.8.8.8', opt), false);
  assert.equal(isAllowedRemoteAddress('172.15.0.1', opt), false, '172.15 is BELOW the private block');
  assert.equal(isAllowedRemoteAddress('172.32.0.1', opt), false, '172.32 is ABOVE the private block');
  assert.equal(isAllowedRemoteAddress('11.0.0.1', opt), false);
  assert.equal(isAllowedRemoteAddress('192.169.1.1', opt), false);
  assert.equal(isAllowedRemoteAddress('2001:db8::1', opt), false);
});

test('net-allowlist: empty / malformed input denies', () => {
  assert.equal(isAllowedRemoteAddress(''), false);
  assert.equal(isAllowedRemoteAddress(null), false);
  assert.equal(isAllowedRemoteAddress(undefined), false);
  assert.equal(isAllowedRemoteAddress('   '), false);
  assert.equal(isAllowedRemoteAddress('not-an-ip', { allowPrivateNetwork: true }), false);
  assert.equal(isAllowedRemoteAddress('10.0.0', { allowPrivateNetwork: true }), false);
  assert.equal(isAllowedRemoteAddress('10.0.0.999', { allowPrivateNetwork: true }), false);
});

test('net-allowlist: normalizeRemoteAddress strips the ::ffff: mapping', () => {
  assert.equal(normalizeRemoteAddress('::ffff:192.168.0.1'), '192.168.0.1');
  assert.equal(normalizeRemoteAddress('  ::ffff:127.0.0.1  '), '127.0.0.1');
  assert.equal(normalizeRemoteAddress('::1'), '::1');
  assert.equal(normalizeRemoteAddress(''), '');
});

test('net-allowlist: isPrivateIpv4 boundaries', () => {
  assert.equal(isPrivateIpv4('10.255.255.255'), true);
  assert.equal(isPrivateIpv4('192.168.255.255'), true);
  assert.equal(isPrivateIpv4('172.16.0.0'), true);
  assert.equal(isPrivateIpv4('172.31.0.0'), true);
  assert.equal(isPrivateIpv4('172.15.0.0'), false);
  assert.equal(isPrivateIpv4('172.32.0.0'), false);
  assert.equal(isPrivateIpv4('fd00::1'), false, 'no dot -> not an IPv4');
});

// MUTATION / KNOWN-BAD CONTROL (rule 3b): a naive prefix check - the obvious wrong
// implementation - must disagree with the real one, proving these cases discriminate.
test('net-allowlist: CONTROL - a naive startsWith allowlist would admit a public address', () => {
  const naive = (a) => a.startsWith('10.') || a.startsWith('192.168.') || a.startsWith('172.');
  assert.equal(naive('172.32.0.1'), true, 'naive check does not admit the bad case - control broken');
  assert.equal(isAllowedRemoteAddress('172.32.0.1', { allowPrivateNetwork: true }), false);
});
