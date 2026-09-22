// Tests for tools/lib/git-diff.mjs (K1).
// Ported from tools/web/agentify-desktop/tests/git-diff.test.mjs (1 case) and extended to assert
// the two properties that make the packet worth salvaging: the char budget is HONOURED and the
// priority ranking actually orders files.

import test from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';
import { spawn } from 'node:child_process';

import { buildReviewPacket, scorePath } from '../git-diff.mjs';

function run(cmd, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] });  // nosemgrep: javascript.lang.security.detect-child-process.detect-child-process -- developer tooling that legitimately spawns child processes
    const out = [];
    const err = [];
    child.stdout.on('data', (b) => out.push(String(b)));
    child.stderr.on('data', (b) => err.push(String(b)));
    child.on('error', reject);
    child.on('close', (code) => resolve({ code, stdout: out.join(''), stderr: err.join('') }));
  });
}

async function tmpRepo() {
  const dir = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), 'toolslib-git-')));
  await run('git', ['init'], dir);
  await run('git', ['config', 'user.email', 'test@example.com'], dir);
  await run('git', ['config', 'user.name', 'Test'], dir);
  await run('git', ['config', 'commit.gpgsign', 'false'], dir);
  await fs.writeFile(path.join(dir, 'README.md'), 'hi\n', 'utf8');
  await run('git', ['add', '.'], dir);
  await run('git', ['commit', '-m', 'init'], dir);
  return dir;
}

test('git-diff: builds a bounded review packet', async () => {
  const dir = await tmpRepo();
  await fs.writeFile(path.join(dir, 'src.js'), 'export function a(){return 1}\n', 'utf8');

  const pkt = await buildReviewPacket({ workspaceDir: dir, maxChars: 2000, maxFiles: 10, maxHunksPerFile: 2 });
  assert.equal(typeof pkt.stat, 'string');
  assert.ok(Array.isArray(pkt.files));
  assert.ok(typeof pkt.patch === 'string');
  assert.ok(pkt.patch.length <= 2000);
});

test('git-diff: tracked-file edits appear and the packet reports ok', async () => {
  const dir = await tmpRepo();
  await fs.writeFile(path.join(dir, 'README.md'), 'hi\nchanged\n', 'utf8');

  const pkt = await buildReviewPacket({ workspaceDir: dir });
  assert.equal(pkt.ok, true);
  assert.ok(pkt.files.some((f) => f.file === 'README.md'), 'expected README.md in the packet file list');
  assert.ok(pkt.stat.includes('README.md'));
});

test('git-diff: the maxChars budget is HONOURED on a large diff', async () => {
  const dir = await tmpRepo();
  const big = 'x'.repeat(200);
  for (const name of ['a.js', 'b.js', 'c.js', 'd.js']) {
    await fs.writeFile(path.join(dir, name), `${big}\n`.repeat(60), 'utf8');
  }
  await run('git', ['add', '.'], dir);
  await run('git', ['commit', '-m', 'add'], dir);
  for (const name of ['a.js', 'b.js', 'c.js', 'd.js']) {
    await fs.writeFile(path.join(dir, name), `${big}CHANGED\n`.repeat(60), 'utf8');
  }

  const budget = 3000;
  const pkt = await buildReviewPacket({ workspaceDir: dir, maxChars: budget });
  assert.ok(pkt.patch.length <= budget, `patch ${pkt.patch.length} exceeded budget ${budget}`);
  // CONTROL: the unbudgeted diff really is bigger, so the assertion above is not vacuous.
  const unbounded = await buildReviewPacket({ workspaceDir: dir, maxChars: 10_000_000 });
  assert.ok(unbounded.patch.length > budget, 'diff is too small to exercise the budget - control broken');
});

test('git-diff: maxFiles caps the ranked file list', async () => {
  const dir = await tmpRepo();
  for (const name of ['a.js', 'b.js', 'c.js']) await fs.writeFile(path.join(dir, name), 'v1\n', 'utf8');
  await run('git', ['add', '.'], dir);
  await run('git', ['commit', '-m', 'add'], dir);
  for (const name of ['a.js', 'b.js', 'c.js']) await fs.writeFile(path.join(dir, name), 'v2\n', 'utf8');

  const pkt = await buildReviewPacket({ workspaceDir: dir, maxFiles: 2 });
  assert.equal(pkt.files.length, 2);
});

test('git-diff: scorePath ranks tests > security > config > code > docs', () => {
  assert.equal(scorePath('src/foo.test.js'), 90);
  assert.equal(scorePath('src/auth/token.js'), 85);
  assert.equal(scorePath('.github/workflows/ci.yml'), 80);
  assert.equal(scorePath('src/plain.js'), 50);
  assert.equal(scorePath('README.md'), 30);
  // The ordering, not just the numbers, is the contract the packet relies on.
  assert.ok(scorePath('a.test.js') > scorePath('auth.js'));
  assert.ok(scorePath('auth.js') > scorePath('docker-compose.yml'));
  assert.ok(scorePath('docker-compose.yml') > scorePath('plain.js'));
  assert.ok(scorePath('plain.js') > scorePath('notes.md'));
});

test('git-diff: a security-relevant file outranks a doc in the emitted order', async () => {
  const dir = await tmpRepo();
  await fs.writeFile(path.join(dir, 'notes.md'), 'v1\n', 'utf8');
  await fs.writeFile(path.join(dir, 'auth.js'), 'v1\n', 'utf8');
  await run('git', ['add', '.'], dir);
  await run('git', ['commit', '-m', 'add'], dir);
  await fs.writeFile(path.join(dir, 'notes.md'), 'v2\n', 'utf8');
  await fs.writeFile(path.join(dir, 'auth.js'), 'v2\n', 'utf8');

  const pkt = await buildReviewPacket({ workspaceDir: dir });
  const names = pkt.files.map((f) => f.file);
  assert.ok(names.indexOf('auth.js') < names.indexOf('notes.md'), `expected auth.js before notes.md, got ${names}`);
});

test('git-diff: a clean tree yields an empty packet without throwing', async () => {
  const dir = await tmpRepo();
  const pkt = await buildReviewPacket({ workspaceDir: dir });
  assert.equal(pkt.ok, true);
  assert.deepEqual(pkt.files, []);
  assert.equal(pkt.patch, '');
});

test('git-diff: a directory that is not a git repo yields ok:false and an empty packet', async () => {
  const dir = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), 'toolslib-nogit-')));
  try {
    const pkt = await buildReviewPacket({ workspaceDir: dir });
    assert.equal(pkt.ok, false);
    assert.deepEqual(pkt.files, []);
    assert.equal(pkt.patch, '');
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
});

test('git-diff: scorePath treats nullish and empty paths as unranked code', () => {
  assert.equal(scorePath(''), 50);
  assert.equal(scorePath(null), 50);
  assert.equal(scorePath(undefined), 50);
});

test('git-diff: a sub-50ms timeout kills git and the packet reports ok:false', async () => {
  // timeoutMs:0 fires before any child process can complete, so the SIGTERM path in run()
  // is exercised deterministically in milliseconds instead of a 30-second stall.
  const dir = await tmpRepo();
  const pkt = await buildReviewPacket({ workspaceDir: dir, timeoutMs: 0 });
  assert.equal(pkt.ok, false);
  assert.deepEqual(pkt.files, []);
  assert.equal(pkt.patch, '');
});
