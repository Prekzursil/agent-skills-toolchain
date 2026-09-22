// ORIGIN: tools/web/agentify-desktop/orchestrator/git-diff.mjs
//
// SURVIVED THE RETIREMENT because it builds a priority-ranked, character-budgeted diff packet to
// feed ANY reviewer - a Codex thread, a Claude subagent, a human. Nothing in it knew about the
// browser, the Electron shell, or the ChatGPT page transport the retirement removed. The ranking
// heuristic (tests > auth/security > config > code > docs) and the hard maxChars budget are the
// hard-won parts: they are what stop a review prompt from blowing its context window.
//
// Carried over with ONE change, and no behaviour change: scorePath was module-private and is now
// exported, so the ranking contract the packet depends on can be asserted directly by the tests.
// Every other byte of the logic is identical to the origin (verified by diff).
//
// SECOND change (2026-09-19, 100%-coverage pass), disclosed: buildReviewPacket takes an optional
// `timeoutMs` that overrides the per-call git timeouts. Default behaviour is byte-identical
// (30s stat/name-status, 60s full diff) - the option exists so the SIGTERM kill path in run()
// can be exercised by a test in milliseconds instead of a 30-second stall. Also normalised two
// provably-dead guards: the timer's `unref?.()` (Node Timeout always has unref) and
// `perFile.get(key) || []` (key always comes from perFile.keys()).

import { spawn } from 'node:child_process';
import path from 'node:path';

function run(cmd, args, { cwd, timeoutMs = 60_000 } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] });  // nosemgrep: javascript.lang.security.detect-child-process.detect-child-process -- developer tooling that legitimately spawns child processes
    const out = [];
    const err = [];
    const t = setTimeout(() => {
      try {
        child.kill('SIGTERM');
      } catch {}
    }, timeoutMs);
    t.unref();
    child.stdout.on('data', (b) => out.push(String(b)));
    child.stderr.on('data', (b) => err.push(String(b)));
    child.on('error', reject);
    child.on('close', (code) => {
      clearTimeout(t);
      resolve({ code, stdout: out.join(''), stderr: err.join('') });
    });
  });
}

export function scorePath(p) {
  const s = String(p || '').toLowerCase();
  if (/test|__tests__|spec\./.test(s)) return 90;
  if (/auth|security|token|secret|cors|policy|permission/.test(s)) return 85;
  if (/config|workflow|ci|github|wrangler|docker|k8s|nginx/.test(s)) return 80;
  if (/\.(md|txt)$/.test(s)) return 30;
  return 50;
}

export async function buildReviewPacket({ workspaceDir, maxChars = 35_000, maxFiles = 20, maxHunksPerFile = 6, timeoutMs } = {}) {
  const cwd = path.resolve(workspaceDir || process.cwd());

  const stat = await run('git', ['diff', '--stat'], { cwd, timeoutMs: timeoutMs ?? 30_000 });
  const nameStatus = await run('git', ['diff', '--name-status'], { cwd, timeoutMs: timeoutMs ?? 30_000 });
  const diff = await run('git', ['diff', '--unified=3'], { cwd, timeoutMs: timeoutMs ?? 60_000 });

  const files = String(nameStatus.stdout || '')
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => {
      const [status, ...rest] = l.split(/\s+/);
      const file = rest.join(' ');
      return { status, file, score: scorePath(file) };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, maxFiles);

  // Very simple hunk selection: take first N hunks for prioritized files.
  const full = String(diff.stdout || '');
  const perFile = new Map();
  let current = null;
  for (const line of full.split('\n')) {
    if (line.startsWith('diff --git ')) {
      current = line;
      perFile.set(current, []);
      continue;
    }
    if (!current) continue;
    perFile.get(current).push(line);
  }

  const selected = [];
  let used = 0;
  for (const f of files) {
    // Find the diff section that matches this file (best-effort).
    const key = Array.from(perFile.keys()).find((k) => k.includes(` b/${f.file}`) || k.includes(` a/${f.file}`));
    if (!key) continue;
    const lines = perFile.get(key);

    let hunks = 0;
    const buf = [key];
    for (const l of lines) {
      if (l.startsWith('@@')) hunks += 1;
      if (hunks > maxHunksPerFile) break;
      buf.push(l);
    }

    const block = buf.join('\n').trim() + '\n';
    if (used + block.length > maxChars) break;
    selected.push(block);
    used += block.length;
  }

  const packet = {
    ok: stat.code === 0 && diff.code === 0,
    stat: String(stat.stdout || '').trim(),
    files: files.map((f) => ({ status: f.status, file: f.file })),
    patch: selected.join('\n').trim()
  };
  return packet;
}
