// Tests for tools/lib/workspace.mjs (K2).
// Ported from tools/web/agentify-desktop/tests/workspace-detect.test.mjs (3 cases), plus coverage
// for findRepoRoot and the non-node test-command branches the origin never exercised.

import test from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';

import { detectWorkspaceRoot, detectTestCommand, detectPackageManager, findRepoRoot } from '../workspace.mjs';

async function tmp() {
  // realpath: macOS/Windows tmpdir can be a symlink/8.3 alias, which would break equality asserts.
  return await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), 'toolslib-ws-')));
}

// --- ported from the origin suite --------------------------------------------------------------

test('workspace: detects workspace root by markers', async () => {
  const dir = await tmp();
  const nested = path.join(dir, 'a', 'b');
  await fs.mkdir(nested, { recursive: true });
  await fs.writeFile(path.join(dir, 'package.json'), JSON.stringify({ name: 'x', scripts: { test: 'node -v' } }), 'utf8');
  const root = await detectWorkspaceRoot(nested);
  assert.equal(root, dir);
});

test('workspace: detects npm by lockfile', async () => {
  const dir = await tmp();
  await fs.writeFile(path.join(dir, 'package.json'), JSON.stringify({ name: 'x', scripts: { test: 'node -v' } }), 'utf8');
  await fs.writeFile(path.join(dir, 'package-lock.json'), 'x', 'utf8');
  assert.equal(await detectPackageManager(dir), 'npm');
  assert.equal(await detectTestCommand(dir), 'npm test');
});

test('workspace: detects pnpm by lockfile', async () => {
  const dir = await tmp();
  await fs.writeFile(path.join(dir, 'package.json'), JSON.stringify({ name: 'x', scripts: { test: 'node -v' } }), 'utf8');
  await fs.writeFile(path.join(dir, 'pnpm-lock.yaml'), 'x', 'utf8');
  assert.equal(await detectPackageManager(dir), 'pnpm');
  assert.equal(await detectTestCommand(dir), 'pnpm test');
});

// --- added coverage -----------------------------------------------------------------------------

test('workspace: detects yarn by lockfile', async () => {
  const dir = await tmp();
  await fs.writeFile(path.join(dir, 'package.json'), JSON.stringify({ name: 'x', scripts: { test: 'node -v' } }), 'utf8');
  await fs.writeFile(path.join(dir, 'yarn.lock'), 'x', 'utf8');
  assert.equal(await detectPackageManager(dir), 'yarn');
  assert.equal(await detectTestCommand(dir), 'yarn test');
});

test('workspace: package manager defaults to npm when no lockfile is present', async () => {
  const dir = await tmp();
  assert.equal(await detectPackageManager(dir), 'npm');
});

test('workspace: findRepoRoot finds a .git ancestor and returns null when there is none', async () => {
  const dir = await tmp();
  const nested = path.join(dir, 'a', 'b', 'c');
  await fs.mkdir(nested, { recursive: true });
  assert.equal(await findRepoRoot(nested), null);

  await fs.mkdir(path.join(dir, '.git'), { recursive: true });
  assert.equal(await findRepoRoot(nested), dir);
});

test('workspace: a .git FILE (worktree/submodule) counts as a repo root', async () => {
  const dir = await tmp();
  const nested = path.join(dir, 'a');
  await fs.mkdir(nested, { recursive: true });
  await fs.writeFile(path.join(dir, '.git'), 'gitdir: /elsewhere/.git/worktrees/x\n', 'utf8');
  assert.equal(await findRepoRoot(nested), dir);
});

test('workspace: git root WINS over marker fallback in detectWorkspaceRoot', async () => {
  const dir = await tmp();
  const inner = path.join(dir, 'pkg');
  await fs.mkdir(inner, { recursive: true });
  await fs.mkdir(path.join(dir, '.git'), { recursive: true });
  await fs.writeFile(path.join(inner, 'package.json'), '{}', 'utf8');
  assert.equal(await detectWorkspaceRoot(inner), dir);
});

test('workspace: non-node test commands', async () => {
  const py = await tmp();
  await fs.writeFile(path.join(py, 'pyproject.toml'), '[project]\n', 'utf8');
  assert.equal(await detectTestCommand(py), 'pytest -q');

  const go = await tmp();
  await fs.writeFile(path.join(go, 'go.mod'), 'module x\n', 'utf8');
  assert.equal(await detectTestCommand(go), 'go test ./...');

  const rs = await tmp();
  await fs.writeFile(path.join(rs, 'Cargo.toml'), '[package]\n', 'utf8');
  assert.equal(await detectTestCommand(rs), 'cargo test');
});

test('workspace: no recognisable project yields null test command', async () => {
  const dir = await tmp();
  assert.equal(await detectTestCommand(dir), null);
});

test('workspace: a package.json with no test script falls through, and malformed JSON does not throw', async () => {
  const noTest = await tmp();
  await fs.writeFile(path.join(noTest, 'package.json'), JSON.stringify({ name: 'x' }), 'utf8');
  assert.equal(await detectTestCommand(noTest), null);

  const broken = await tmp();
  await fs.writeFile(path.join(broken, 'package.json'), '{ not json', 'utf8');
  assert.equal(await detectTestCommand(broken), null);
});
