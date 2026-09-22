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

test('workspace: findRepoRoot and detectWorkspaceRoot default to process.cwd when startDir is omitted', async () => {
  const here = await fs.realpath(new URL('.', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
  assert.equal(await findRepoRoot(), await findRepoRoot(here));
  assert.equal(await detectWorkspaceRoot(), await detectWorkspaceRoot(here));
});

test('workspace: detectPackageManager recognises yarn and pnpm lockfiles', async () => {
  const dir = await tmp();
  try {
    await fs.writeFile(path.join(dir, 'pnpm-lock.yaml'), '', 'utf8');
    assert.equal(await detectPackageManager(dir), 'pnpm');
    await fs.rm(path.join(dir, 'pnpm-lock.yaml'));
    await fs.writeFile(path.join(dir, 'yarn.lock'), '', 'utf8');
    assert.equal(await detectPackageManager(dir), 'yarn');
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
});

test('workspace: detectTestCommand maps the package manager into the npm-family test command', async () => {
  const dir = await tmp();
  try {
    await fs.writeFile(path.join(dir, 'package.json'), JSON.stringify({ scripts: { test: 'node --test' } }), 'utf8');
    await fs.writeFile(path.join(dir, 'pnpm-lock.yaml'), '', 'utf8');
    assert.equal(await detectTestCommand(dir), 'pnpm test');
    await fs.rm(path.join(dir, 'pnpm-lock.yaml'));
    await fs.writeFile(path.join(dir, 'yarn.lock'), '', 'utf8');
    assert.equal(await detectTestCommand(dir), 'yarn test');
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
});

test('workspace: a non-string or whitespace-only test script falls through to null', async () => {
  const dir = await tmp();
  try {
    await fs.writeFile(path.join(dir, 'package.json'), JSON.stringify({ scripts: { test: '   ' } }), 'utf8');
    assert.equal(await detectTestCommand(dir), null);
    await fs.writeFile(path.join(dir, 'package.json'), JSON.stringify({ scripts: { test: 5 } }), 'utf8');
    assert.equal(await detectTestCommand(dir), null);
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
});

test('workspace: each python marker alone selects pytest', async () => {
  for (const marker of ['pytest.ini', 'pyproject.toml', 'requirements.txt']) {
    const dir = await tmp();
    try {
      await fs.writeFile(path.join(dir, marker), '', 'utf8');
      assert.equal(await detectTestCommand(dir), 'pytest -q', `${marker} alone must select pytest`);
    } finally {
      await fs.rm(dir, { recursive: true, force: true });
    }
  }
});

test('workspace: an empty package.json has no test command', async () => {
  const dir = await tmp();
  try {
    await fs.writeFile(path.join(dir, 'package.json'), '{}', 'utf8');
    assert.equal(await detectTestCommand(dir), null);
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
});

test('workspace: the 50-level walk cap gives up instead of looping forever', async () => {
  // A 52-level-deep leaf with no .git and no marker anywhere above it (within the cap window):
  // both walks must hit the iteration cap rather than reach the filesystem root or the home
  // directory's package.json, which sits ~57 levels above the leaf - beyond the 50 cap.
  const base = await tmp();
  try {
    // Single-char segment names keep the leaf path under the Windows chdir limit
    // (ENAMETOOLONG measured with longer names).
    let leaf = path.join(base, ...Array.from({ length: 51 }, () => 'a'));
    await fs.mkdir(leaf, { recursive: true });

    assert.equal(await findRepoRoot(leaf), null);
    assert.equal(await detectWorkspaceRoot(leaf), leaf);

    // With startDir omitted AND cwd deep inside the leaf, both detectors default to
    // process.cwd() (the `startDir || process.cwd()` fallback) and still cap out.
    const oldCwd = process.cwd();
    try {
      process.chdir(leaf);
      assert.equal(await findRepoRoot(), null);
      assert.equal(await detectWorkspaceRoot(), leaf);
    } finally {
      process.chdir(oldCwd);
    }
  } finally {
    await fs.rm(base, { recursive: true, force: true });
  }
});

test('workspace: the marker walk breaks at the drive root when no marker exists above it', async () => {
  // The volume root has no marker files and dirname(root) === root, so the walk breaks
  // immediately and returns the root itself.
  const root = path.parse(await tmp()).root;
  assert.equal(await detectWorkspaceRoot(root), root);
});
