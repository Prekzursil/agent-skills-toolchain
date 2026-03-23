import fs from 'node:fs/promises';
import { spawn } from 'node:child_process';
import readline from 'node:readline';
import path from 'node:path';

function isUuidLike(s) {
  return typeof s === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(s.trim());
}

function extractSessionIdFromJson(obj) {
  if (!obj || typeof obj !== 'object') return null;
  for (const k of ['session_id', 'sessionId', 'conversation_id', 'conversationId', 'id']) {
    const v = obj[k];
    if (isUuidLike(v)) return String(v).trim();
  }
  // Search any shallow string fields for uuid.
  for (const v of Object.values(obj)) {
    if (isUuidLike(v)) return String(v).trim();
  }
  return null;
}

async function pathExists(file) {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

export async function resolveCodexInvocation({
  env = process.env,
  nodeExecutable = process.execPath,
  platform = process.platform
} = {}) {
  const configured = String(env.CODEX_CLI_BIN || '').trim();
  if (configured) {
    return { command: configured, args: [], shell: platform === 'win32' && configured.toLowerCase().endsWith('.cmd') };
  }

  if (platform !== 'win32') return { command: 'codex', args: [], shell: false };

  const appData = String(env.APPDATA || '').trim();
  const userProfile = String(env.USERPROFILE || '').trim();
  const candidateBases = [
    appData ? path.join(appData, 'npm') : null,
    userProfile ? path.join(userProfile, 'AppData', 'Roaming', 'npm') : null
  ].filter(Boolean);

  for (const baseDir of candidateBases) {
    const scriptPath = path.join(baseDir, 'node_modules', '@openai', 'codex', 'bin', 'codex.js');
    if (await pathExists(scriptPath)) {
      const bundledNode = path.join(baseDir, 'node.exe');
      return {
        command: (await pathExists(bundledNode)) ? bundledNode : nodeExecutable,
        args: [scriptPath],
        shell: false
      };
    }
  }

  return { command: 'codex.exe', args: [], shell: false };
}

export async function runCodexExec({
  workspaceDir,
  prompt,
  sessionId = null,
  ephemeral = false,
  model = null,
  configOverrides = [],
  timeoutMs = 30 * 60_000,
  abortOnStderrPatterns = [],
  onEvent,
  env = process.env
}) {
  const cwd = path.resolve(workspaceDir || process.cwd());
  const args = ['exec'];
  if (ephemeral) args.push('--ephemeral');
  if (model) args.push('-m', String(model));
  for (const entry of Array.isArray(configOverrides) ? configOverrides : []) {
    if (!entry) continue;
    args.push('-c', String(entry));
  }
  args.push('--json', '-C', cwd);
  if (!ephemeral && sessionId) args.push('resume', sessionId);

  // Prompt is an argument to avoid stdin edge cases.
  args.push(String(prompt || ''));

  const codexInvocation = await resolveCodexInvocation({ env, platform: process.platform, nodeExecutable: process.execPath });
  const child = spawn(codexInvocation.command, [...codexInvocation.args, ...args], {
    cwd,
    env,
    shell: codexInvocation.shell || false,
    stdio: ['ignore', 'pipe', 'pipe']
  });

  let resolvedSessionId = sessionId || null;
  const out = [];
  const err = [];
  let abortedReason = null;

  const rl = readline.createInterface({ input: child.stdout });
  rl.on('line', (line) => {
    out.push(line);
    let obj = null;
    try {
      obj = JSON.parse(line);
    } catch {}
    if (obj) {
      const sid = extractSessionIdFromJson(obj);
      if (!resolvedSessionId && sid) resolvedSessionId = sid;
      onEvent?.({ type: 'json', json: obj, raw: line, sessionId: resolvedSessionId });
    } else {
      onEvent?.({ type: 'text', text: line, sessionId: resolvedSessionId });
    }
  });

  child.stderr.on('data', (buf) => {
    const s = String(buf || '');
    err.push(s);
    onEvent?.({ type: 'stderr', text: s, sessionId: resolvedSessionId });
    if (abortedReason || !Array.isArray(abortOnStderrPatterns) || child.exitCode !== null || child.signalCode !== null) return;
    for (const rule of abortOnStderrPatterns) {
      const pattern = rule?.pattern;
      const reason = rule?.reason || 'stderr_pattern_match';
      if (!pattern) continue;
      const matched = pattern instanceof RegExp ? pattern.test(s) : String(s).includes(String(pattern));
      if (!matched) continue;
      abortedReason = reason;
      try {
        child.kill('SIGTERM');
      } catch {}
      break;
    }
  });

  const timer = setTimeout(() => {
    try {
      child.kill('SIGTERM');
    } catch {}
  }, timeoutMs);
  timer.unref?.();

  const exit = await new Promise((resolve) => {
    child.on('exit', (code, signal) => resolve({ code, signal }));
  });
  clearTimeout(timer);
  try {
    rl.close();
  } catch {}

  const stdout = out.join('\n');
  const stderr = err.join('');

  return { ok: exit.code === 0, exit, sessionId: resolvedSessionId, stdout, stderr, abortedReason };
}
