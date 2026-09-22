// Tests for tools/lib/security.mjs (K4).
//
// Ported from tools/web/agentify-desktop/tests/security.test.mjs (2 cases) and EXTENDED with the
// two containment cases the original suite never had - which is exactly why the cross-volume and
// UNC defects shipped green.
//
// Windows semantics are exercised via path.win32 explicitly, so these assertions are identical on
// a Windows dev box and a Linux CI runner. A test that only ran the host's semantics would be
// silent about the very defect it exists to catch.

import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';

import { isPathWithin, assertWithin, isUncPath, normalizeAbs } from '../security.mjs';

const w = path.win32;
const WIN_ROOT = 'C:\\allowed\\root';

// --- ported from the origin suite (host-platform semantics) ---------------------------------

test('security: isPathWithin respects allowed roots', () => {
  const root = path.resolve('/tmp/agentify-root');
  const ok = path.join(root, 'a', 'b.txt');
  const bad = path.resolve('/tmp/agentify-root-2/x.txt');
  assert.equal(isPathWithin({ filePath: ok, allowedRoots: [root] }), true);
  assert.equal(isPathWithin({ filePath: bad, allowedRoots: [root] }), false);
});

test('security: assertWithin throws', () => {
  const root = path.resolve('/tmp/agentify-root');
  assert.throws(() => assertWithin({ filePath: '/etc/passwd', allowedRoots: [root] }), /path_not_allowed/);
});

// --- DEFECT FIX 1: cross-volume ---------------------------------------------------------------

test('security: rejects a path on ANOTHER WINDOWS VOLUME (regression: shipped as true)', () => {
  assert.equal(isPathWithin({ filePath: 'D:\\anything\\at\\all', allowedRoots: [WIN_ROOT], pathImpl: w }), false);
  assert.throws(
    () => assertWithin({ filePath: 'D:\\anything\\at\\all', allowedRoots: [WIN_ROOT], pathImpl: w }),
    /path_not_allowed/
  );
});

// --- DEFECT FIX 2: UNC ------------------------------------------------------------------------

test('security: rejects a UNC share (regression: shipped as true)', () => {
  assert.equal(isPathWithin({ filePath: '\\\\evil.example\\share\\x', allowedRoots: [WIN_ROOT], pathImpl: w }), false);
  // forward-slash UNC form is the same coercion
  assert.equal(isPathWithin({ filePath: '//evil.example/share/x', allowedRoots: [WIN_ROOT], pathImpl: w }), false);
});

test('security: a UNC ALLOWED ROOT cannot re-open the hole', () => {
  assert.equal(
    isPathWithin({ filePath: '\\\\evil.example\\share\\x', allowedRoots: ['\\\\evil.example\\share'], pathImpl: w }),
    false
  );
});

test('security: isUncPath is win32-only (a backslash is legal in a POSIX filename)', () => {
  assert.equal(isUncPath('\\\\server\\share', w), true);
  assert.equal(isUncPath('C:\\x', w), false);
  assert.equal(isUncPath('\\\\server\\share', path.posix), false);
});

// --- the fix must not over-reject -------------------------------------------------------------

test('security: still admits legitimate same-volume paths', () => {
  assert.equal(isPathWithin({ filePath: 'C:\\allowed\\root\\a\\b.txt', allowedRoots: [WIN_ROOT], pathImpl: w }), true);
  assert.equal(isPathWithin({ filePath: WIN_ROOT, allowedRoots: [WIN_ROOT], pathImpl: w }), true);
});

test('security: drive-letter CASE must not cause a false reject', () => {
  // path.win32.parse('c:\\x').root preserves the lowercase drive, so a case-sensitive volume
  // compare would wrongly deny this. Windows paths are case-insensitive.
  assert.equal(isPathWithin({ filePath: 'c:\\allowed\\root\\a.txt', allowedRoots: [WIN_ROOT], pathImpl: w }), true);
  assert.equal(isPathWithin({ filePath: 'C:\\allowed\\root\\a.txt', allowedRoots: ['c:\\allowed\\root'], pathImpl: w }), true);
});

test('security: prefix-but-not-a-child is rejected (path.relative, not startsWith)', () => {
  assert.equal(isPathWithin({ filePath: 'C:\\allowed\\rootother\\x', allowedRoots: [WIN_ROOT], pathImpl: w }), false);
});

test('security: parent traversal is rejected', () => {
  assert.equal(isPathWithin({ filePath: 'C:\\allowed\\root\\..\\..\\x', allowedRoots: [WIN_ROOT], pathImpl: w }), false);
  assert.equal(isPathWithin({ filePath: 'C:\\allowed', allowedRoots: [WIN_ROOT], pathImpl: w }), false);
});

test('security: empty/absent inputs deny', () => {
  assert.equal(isPathWithin({ filePath: '', allowedRoots: [WIN_ROOT], pathImpl: w }), false);
  assert.equal(isPathWithin({ filePath: 'C:\\allowed\\root\\a', allowedRoots: [], pathImpl: w }), false);
  assert.equal(isPathWithin({ filePath: 'C:\\allowed\\root\\a', allowedRoots: null, pathImpl: w }), false);
});

test('security: multiple roots - any match admits', () => {
  const roots = ['E:\\other', WIN_ROOT];
  assert.equal(isPathWithin({ filePath: 'C:\\allowed\\root\\a', allowedRoots: roots, pathImpl: w }), true);
  assert.equal(isPathWithin({ filePath: 'E:\\other\\a', allowedRoots: roots, pathImpl: w }), true);
  assert.equal(isPathWithin({ filePath: 'F:\\nope\\a', allowedRoots: roots, pathImpl: w }), false);
});

test('security: normalizeAbs is exported and resolves through the injected impl', () => {
  assert.equal(normalizeAbs('C:\\a\\..\\b', w), 'C:\\b');
});

// --- MUTATION / KNOWN-BAD CONTROL -------------------------------------------------------------
// Rule 3b (both-states test): prove these assertions can FAIL. This reconstructs the ORIGINAL
// shipped predicate and requires it to get the two cases WRONG. If this test ever goes red, the
// two cases above have stopped being discriminating and their green means nothing.

function shippedOriginalPredicate(filePath, allowedRoots, p = w) {
  const fp = p.resolve(String(filePath || '').trim());
  const roots = allowedRoots.map((r) => p.resolve(String(r || '').trim()));
  for (const r of roots) {
    const rel = p.relative(r, fp);
    if (!rel || (!rel.startsWith('..' + p.sep) && rel !== '..')) return true;
  }
  return false;
}

test('security: CONTROL - the original predicate really did admit both attacks', () => {
  assert.equal(shippedOriginalPredicate('D:\\anything\\at\\all', [WIN_ROOT]), true, 'cross-volume defect not reproduced');
  assert.equal(shippedOriginalPredicate('\\\\evil.example\\share\\x', [WIN_ROOT]), true, 'UNC defect not reproduced');
  // ...and still got the good case right, so the fix is a narrowing, not a rewrite.
  assert.equal(shippedOriginalPredicate('C:\\allowed\\root\\a.txt', [WIN_ROOT]), true);
});

test('security: POSIX semantics - same-volume containment, backslash names are legal, never UNC', () => {
  const p = path.posix;
  // The POSIX same-volume compare (line 46) only runs under posix semantics.
  assert.equal(isPathWithin({ filePath: '/allowed/root/x', allowedRoots: ['/allowed/root'], pathImpl: p }), true);
  assert.equal(isPathWithin({ filePath: '/elsewhere/x', allowedRoots: ['/allowed/root'], pathImpl: p }), false);
  assert.equal(isPathWithin({ filePath: '/allowed/root/x', allowedRoots: [], pathImpl: p }), false);
  // A leading double backslash is a legal POSIX filename, not a UNC share - must NOT be
  // special-cased under posix semantics.
  assert.equal(isUncPath('\\\\server\\share', p), false);
});

test('security: nullish inputs, non-array roots and UNC roots all reject containment', () => {
  assert.equal(normalizeAbs(null), path.resolve(''));
  assert.equal(isUncPath(null), false);
  assert.equal(isPathWithin({ filePath: null, allowedRoots: [WIN_ROOT] }), false);
  assert.equal(isPathWithin({ filePath: 'C:\\allowed\\root\\x', allowedRoots: 'not-an-array' }), false);
  // A UNC allowed-root admits nothing: it would re-open the hole the UNC fix closes.
  assert.equal(isPathWithin({ filePath: '\\\\evil.example\\share\\x', allowedRoots: ['\\\\somewhere\\share'] }), false);
  // assertWithin reports the offending inputs in err.data even when they are nullish.
  assert.throws(
    () => assertWithin({ filePath: null, allowedRoots: null }),
    (err) => err.message === 'path_not_allowed' &&
      err.data.filePath === '' &&
      err.data.allowedRoots.length === 0,
  );
});

test('security: a filePath exactly equal to an allowed root is within it', () => {
  assert.equal(isPathWithin({ filePath: WIN_ROOT, allowedRoots: [WIN_ROOT] }), true);
  assert.equal(
    isPathWithin({ filePath: '/allowed/root', allowedRoots: ['/allowed/root'], pathImpl: path.posix }),
    true,
  );
});
