// Tests for tools/lib/handled-ledger.mjs (K3).
// WRITTEN, not ported: the origin (agentify-desktop/orchestrator/storage.mjs) had NO test file of
// its own - the salvaged idempotency ledger was entirely uncovered until now.

import test from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';

import {
  atomicWriteJson,
  handledPath,
  handledLedgerDir,
  readJson,
  writeJson,
  loadHandled,
  markHandled,
  isHandled
} from '../handled-ledger.mjs';

async function tmpState() {
  return await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), 'toolslib-ledger-')));
}

test('handled-ledger: on-disk layout is preserved from the origin', async () => {
  const dir = await tmpState();
  assert.equal(handledLedgerDir(dir), path.join(dir, 'orchestrator'));
  assert.equal(handledPath(dir), path.join(dir, 'orchestrator', 'handled.json'));
});

test('handled-ledger: unknown ids are not handled; marking makes them handled', async () => {
  const dir = await tmpState();
  assert.equal(await isHandled(dir, { key: 'wu', id: 'a1' }), false);
  const rec = await markHandled(dir, { key: 'wu', id: 'a1' });
  assert.equal(rec.status, 'done');
  assert.equal(typeof rec.at, 'string');
  assert.equal(await isHandled(dir, { key: 'wu', id: 'a1' }), true);
});

test('handled-ledger: THE idempotency property - a second dispatch of the same id is suppressed', async () => {
  const dir = await tmpState();
  const ids = ['u1', 'u2', 'u1', 'u3', 'u2'];
  const dispatched = [];
  for (const id of ids) {
    if (await isHandled(dir, { key: 'fanout', id })) continue;
    dispatched.push(id);
    await markHandled(dir, { key: 'fanout', id, status: 'done' });
  }
  assert.deepEqual(dispatched, ['u1', 'u2', 'u3']);
});

test('handled-ledger: keys are independent namespaces', async () => {
  const dir = await tmpState();
  await markHandled(dir, { key: 'k1', id: 'same' });
  assert.equal(await isHandled(dir, { key: 'k1', id: 'same' }), true);
  assert.equal(await isHandled(dir, { key: 'k2', id: 'same' }), false);
});

test('handled-ledger: state survives a reload (it is the on-disk file, not memory)', async () => {
  const dir = await tmpState();
  await markHandled(dir, { key: 'k', id: 'persisted', status: 'failed', meta: { reason: 'timeout' } });
  const raw = JSON.parse(await fs.readFile(handledPath(dir), 'utf8'));
  assert.equal(raw.keys.k.persisted.status, 'failed');
  assert.deepEqual(raw.keys.k.persisted.meta, { reason: 'timeout' });
  assert.equal(await isHandled(dir, { key: 'k', id: 'persisted' }), true);
});

test('handled-ledger: markHandled rejects a missing key or id', async () => {
  const dir = await tmpState();
  await assert.rejects(() => markHandled(dir, { key: '', id: 'x' }), /missing_key_or_id/);
  await assert.rejects(() => markHandled(dir, { key: 'x', id: '  ' }), /missing_key_or_id/);
});

test('handled-ledger: a CORRUPT ledger file degrades to empty rather than throwing', async () => {
  const dir = await tmpState();
  await fs.mkdir(handledLedgerDir(dir), { recursive: true });
  await fs.writeFile(handledPath(dir), '{ not json at all', 'utf8');
  assert.deepEqual(await loadHandled(dir), { keys: {} });
  assert.equal(await isHandled(dir, { key: 'k', id: 'i' }), false);
  // ...and it self-heals on the next write.
  await markHandled(dir, { key: 'k', id: 'i' });
  assert.equal(await isHandled(dir, { key: 'k', id: 'i' }), true);
});

test('handled-ledger: a ledger shaped wrongly (missing .keys) is normalised', async () => {
  const dir = await tmpState();
  await fs.mkdir(handledLedgerDir(dir), { recursive: true });
  await fs.writeFile(handledPath(dir), JSON.stringify({ nope: 1 }), 'utf8');
  const data = await loadHandled(dir);
  assert.deepEqual(data.keys, {});
});

test('atomicWriteJson: creates parent dirs, writes pretty JSON with a trailing newline', async () => {
  const dir = await tmpState();
  const target = path.join(dir, 'deep', 'nested', 'out.json');
  await atomicWriteJson(target, { a: 1, b: [2, 3] });
  const text = await fs.readFile(target, 'utf8');
  assert.deepEqual(JSON.parse(text), { a: 1, b: [2, 3] });
  assert.ok(text.endsWith('\n'), 'expected a trailing newline');
  assert.ok(text.includes('\n  "a": 1'), 'expected 2-space pretty printing');
});

test('atomicWriteJson: leaves NO .tmp residue behind', async () => {
  const dir = await tmpState();
  const target = path.join(dir, 'out.json');
  await atomicWriteJson(target, { a: 1 });
  await atomicWriteJson(target, { a: 2 });
  const entries = await fs.readdir(dir);
  assert.deepEqual(entries.filter((e) => e.endsWith('.tmp')), [], `tmp residue: ${entries}`);
  assert.deepEqual(JSON.parse(await fs.readFile(target, 'utf8')), { a: 2 });
});

// REGRESSION: 25 concurrent writers onto one path failed 3/3 runs on Windows with
// `EPERM: operation not permitted, rename` before renameWithRetry was added. The guarantee
// asserted here is precisely: does not throw, and never leaves a torn file or tmp residue.
// It is NOT a claim that writers are serialised - see the lost-update test below.
test('atomicWriteJson: concurrent writers neither throw nor tear the file', async () => {
  const dir = await tmpState();
  const target = path.join(dir, 'race.json');
  await Promise.all(Array.from({ length: 25 }, (_, i) => atomicWriteJson(target, { i })));
  const parsed = JSON.parse(await fs.readFile(target, 'utf8')); // never a half-written file
  assert.equal(typeof parsed.i, 'number');
  assert.deepEqual((await fs.readdir(dir)).filter((e) => e.endsWith('.tmp')), []);
});

// The honest counterpart: the ledger is single-writer. Documented, not implied, so a future
// consumer does not discover it as a data-loss bug in a fan-out.
test('handled-ledger: KNOWN LIMIT - concurrent markHandled on one stateDir loses updates', async () => {
  const dir = await tmpState();
  const ids = Array.from({ length: 20 }, (_, i) => `id${i}`);
  await Promise.all(ids.map((id) => markHandled(dir, { key: 'k', id })));
  const stored = Object.keys((await loadHandled(dir)).keys.k || {});
  // Every id was written, but read-modify-write means the final file need not contain them all.
  assert.ok(stored.length >= 1 && stored.length <= ids.length);
  assert.ok(stored.every((id) => ids.includes(id)), 'no phantom ids');
  // Sequential writes, by contrast, retain everything - that is the supported usage.
  const seqDir = await tmpState();
  for (const id of ids) await markHandled(seqDir, { key: 'k', id });
  assert.equal(Object.keys((await loadHandled(seqDir)).keys.k).length, ids.length);
});

test('readJson/writeJson round-trip and readJson honours its fallback', async () => {
  const dir = await tmpState();
  const target = path.join(dir, 'rt.json');
  assert.deepEqual(await readJson(target, { fallback: true }), { fallback: true });
  await writeJson(target, { v: 42 });
  assert.deepEqual(await readJson(target, null), { v: 42 });
});

test('ledger: a rename onto a directory exhausts retries, cleans the tmp file and rethrows', async () => {
  // The destination being a directory makes rename fail on every attempt: EPERM on Windows
  // (a RENAME_RETRY_CODE -> full 10-attempt backoff), EISDIR on Linux (non-retryable -> first
  // attempt). Either way atomicWriteJson must rethrow and leave NO tmp residue behind.
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'toolslib-ledger-rename-'));
  try {
    const dest = path.join(dir, 'handled.json');
    await fs.mkdir(dest);
    await assert.rejects(atomicWriteJson(dest, { keys: {} }));
    const residue = (await fs.readdir(dir)).filter((e) => e.endsWith('.tmp'));
    assert.deepEqual(residue, [], 'failed publish must not leave tmp files behind');
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
});

test('ledger: loadHandled normalises scalar and shape-less ledger contents', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'toolslib-ledger-shape-'));
  try {
    await fs.mkdir(handledLedgerDir(dir), { recursive: true });
    // A JSON scalar is not a ledger object.
    await fs.writeFile(handledPath(dir), '42', 'utf8');
    assert.deepEqual(await loadHandled(dir), { keys: {} });
    // An object whose `keys` is not an object gets a fresh keys map.
    await fs.writeFile(handledPath(dir), '{"keys": 5}', 'utf8');
    assert.deepEqual(await loadHandled(dir), { keys: {} });
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
});

test('ledger: markHandled rejects blank key/id and isHandled answers false for unknown ones', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'toolslib-ledger-keys-'));
  try {
    await assert.rejects(markHandled(dir, { key: '', id: 'x' }), /missing_key_or_id/);
    await assert.rejects(markHandled(dir, { key: 'x', id: '' }), /missing_key_or_id/);
    await assert.rejects(markHandled(dir, {}), /missing_key_or_id/);
    assert.equal(await isHandled(dir, { key: 'nope', id: 'nope' }), false);
    assert.equal(await isHandled(dir, {}), false);
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
});

test('ledger: atomicWriteJson creates missing parent directories on the way', async () => {
  // path.dirname(filePath) is mkdir'd recursively before the tmp write, so a destination
  // under a not-yet-existing directory is NOT an error - it is published. (The immediate
  // non-retryable rename throw - EISDIR on Linux - is covered by the directory-destination
  // test above on POSIX; on Windows that same scenario takes the EPERM retry path.)
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'toolslib-ledger-mkdir-'));
  try {
    const dest = path.join(dir, 'fresh', 'nested', 'handled.json');
    await atomicWriteJson(dest, { keys: {} });
    assert.deepEqual(await readJson(dest, null), { keys: {} });
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
});
