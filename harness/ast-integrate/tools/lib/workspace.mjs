// ORIGIN: tools/web/agentify-desktop/orchestrator/workspace.mjs
//
// SURVIVED THE RETIREMENT because repo-root / package-manager / test-command detection is pure
// filesystem probing. Nothing in it knew about the ChatGPT web UI, the Electron shell, or the
// promptbridge transport that the retirement removed - it is the generic "where am I and how do
// I test this project" helper any future tool needs.
//
// Carried over VERBATIM (no behaviour change). Only the import path context changed.
//
// Known limitation, stated rather than silently inherited: findRepoRoot treats the presence of a
// `.git` entry as the repo root, which is correct for both a normal clone and a git worktree
// (where `.git` is a file, not a directory) - `fs.stat` matches either.

import fs from 'node:fs/promises';
import fsSync from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

async function exists(p) {
  try {
    await fs.stat(p);
    return true;
  } catch {
    return false;
  }
}

export async function findRepoRoot(startDir) {
  let dir = path.resolve(startDir || process.cwd());
  for (let i = 0; i < 50; i++) {
    if (await exists(path.join(dir, '.git'))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

export async function detectWorkspaceRoot(startDir) {
  const gitRoot = await findRepoRoot(startDir);
  if (gitRoot) return gitRoot;

  // Fallback: walk up for common markers.
  let dir = path.resolve(startDir || process.cwd());
  const markers = ['package.json', 'pnpm-workspace.yaml', 'turbo.json', 'Cargo.toml', 'go.mod', 'pyproject.toml', 'requirements.txt'];
  for (let i = 0; i < 50; i++) {
    for (const m of markers) {
      if (await exists(path.join(dir, m))) return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return path.resolve(startDir || process.cwd());
}

export async function detectPackageManager(workspaceDir) {
  const dir = path.resolve(workspaceDir);
  const has = async (name) => await exists(path.join(dir, name));
  if (await has('pnpm-lock.yaml')) return 'pnpm';
  if (await has('yarn.lock')) return 'yarn';
  if (await has('package-lock.json')) return 'npm';
  return 'npm';
}

export async function detectTestCommand(workspaceDir) {
  const dir = path.resolve(workspaceDir);
  const has = async (name) => await exists(path.join(dir, name));
  const pkgPath = path.join(dir, 'package.json');
  if (await has('package.json')) {
    try {
      const pkg = JSON.parse(await fs.readFile(pkgPath, 'utf8'));
      const scripts = pkg?.scripts && typeof pkg.scripts === 'object' ? pkg.scripts : {};
      if (typeof scripts.test === 'string' && scripts.test.trim()) {
        const pm = await detectPackageManager(dir);
        return pm === 'pnpm' ? 'pnpm test' : pm === 'yarn' ? 'yarn test' : 'npm test';
      }
    } catch {}
  }

  if (await has('pytest.ini') || await has('pyproject.toml') || await has('requirements.txt')) return 'pytest -q';
  if (await has('go.mod')) return 'go test ./...';
  if (await has('Cargo.toml')) return 'cargo test';

  return null;
}

// Synchronous network canary used by TST-0225 probe2. Performs a REAL TCP
// connect (via a child node process so the result is available synchronously)
// and reports it in the same shape as tools/lib/workspace.py run_canary().
export function runCanary({ network = 'none', host = '127.0.0.1', port = 1, timeout = 1500 } = {}) {
  const probe = `
    const net = require('node:net');
    const [host, port, timeout] = [process.argv[1], Number(process.argv[2]), Number(process.argv[3])];
    const sock = net.connect({ host, port });
    const done = (connected, error) => {
      try { sock.destroy(); } catch {}
      process.stdout.write(JSON.stringify({ connected, error }));
      process.exit(0);
    };
    sock.setTimeout(timeout, () => done(false, 'ETIMEDOUT'));
    sock.on('connect', () => done(true, null));
    sock.on('error', (e) => done(false, String(e && e.code || e)));
  `;
  const res = spawnSync(process.execPath, ['-e', probe, String(host), String(port), String(timeout)], {
    encoding: 'utf8',
    timeout: Number(timeout) + 4000,
  });
  let payload = { connected: false, error: 'canary-child-failed' };
  try {
    payload = JSON.parse((res.stdout || '').trim() || '{}');
  } catch {
    payload = { connected: false, error: (res.stderr || 'canary-parse-failed').slice(0, 200) };
  }
  const connected = payload.connected === true;
  return {
    network,
    substrate: 'node-child-connect',
    host_firewall_touched: false,
    host,
    port: Number(port),
    unit: {
      connected,
      checked_declaration: false,
      error: payload.error || null,
      errno: connected ? null : (payload.error || 'ECONNREFUSED'),
    },
  };
}

// --- File-scope write gate (CLI) -------------------------------------------
// node tools/lib/workspace.mjs write --root R --scope S --dest D --data TEXT
// Verdict is physical: symlinks in every existing ancestor are resolved before
// the containment check, so prefix-siblings (tools/libextra), ../ escapes,
// symlinks pointing outside, and case-variant paths are all denied.

export function physicalPath(p) {
  const abs = path.resolve(String(p));
  const parts = abs.split(path.sep).filter(Boolean);
  let acc = path.parse(abs).root;
  for (let i = 0; i < parts.length; i++) {
    const cand = path.join(acc, parts[i]);
    let st = null;
    try {
      st = fsSync.lstatSync(cand);
    } catch {
      return path.join(cand, ...parts.slice(i + 1));
    }
    if (st) {
      try {
        acc = fsSync.realpathSync(cand);
        continue;
      } catch {
        return path.join(cand, ...parts.slice(i + 1));
      }
    }
  }
  return acc;
}

export function scopeAllows(root, scopeRel, destRel) {
  const scopePhys = physicalPath(path.join(String(root), String(scopeRel)));
  const destPhys = physicalPath(path.join(String(root), String(destRel)));
  const rel = path.relative(scopePhys, destPhys);
  const inside = rel !== '' && !rel.startsWith('..') && !path.isAbsolute(rel);
  return { allowed: inside, scope_physical: scopePhys, dest_physical: destPhys, rel };
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
      out[argv[i].slice(2)] = argv[i + 1];
      i += 1;
    }
  }
  return out;
}

function cliMain() {
  const cmd = process.argv[2];
  const args = parseArgs(process.argv.slice(3));
  const root = args.root || process.cwd();
  const scope = args.scope || '';
  const dest = args.dest || '';
  const verdict = scopeAllows(root, scope, dest);
  const result = {
    cmd,
    allowed: verdict.allowed,
    written: false,
    method: 'realpath-relative',
    reason: verdict.allowed ? 'inside-scope' : 'outside-scope',
    scope_physical: verdict.scope_physical,
    dest_physical: verdict.dest_physical,
  };
  if (cmd === 'write' && verdict.allowed) {
    try {
      fsSync.mkdirSync(path.dirname(verdict.dest_physical), { recursive: true });
      fsSync.writeFileSync(verdict.dest_physical, String(args.data ?? ''), 'utf8');
      result.written = true;
    } catch (e) {
      result.written = false;
      result.reason = `write-failed:${String(e && e.code || e)}`;
    }
  }
  process.stdout.write(JSON.stringify(result) + '\n');
}

const _isMain = (() => {
  try {
    return process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
  } catch {
    return false;
  }
})();
if (_isMain) cliMain();
