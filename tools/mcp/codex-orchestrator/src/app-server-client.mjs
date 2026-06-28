import { spawn } from 'node:child_process';
import readline from 'node:readline';

import { resolveCodexInvocation } from './orchestrator/codex.mjs';

async function terminateChild(child, { graceMs = 2_000 } = {}) {
  if (!child) return;
  if (child.exitCode !== null || child.signalCode !== null) return;
  try {
    child.kill('SIGTERM');
  } catch {}
  const exited = await Promise.race([
    new Promise((resolve) => child.once('exit', () => resolve(true))),
    new Promise((resolve) => setTimeout(() => resolve(false), graceMs))
  ]);
  if (exited) return;
  if (child.exitCode !== null || child.signalCode !== null) return;
  try {
    child.kill('SIGKILL');
  } catch {}
  if (child.exitCode !== null || child.signalCode !== null) return;
  await new Promise((resolve) => child.once('exit', () => resolve())).catch(() => {});
}

export async function withCodexAppServer({
  workspaceDir = process.cwd(),
  env = process.env,
  timeoutMs = 30_000,
  fn
} = {}) {
  const codexInvocation = await resolveCodexInvocation({ env, platform: process.platform, nodeExecutable: process.execPath });
  const child = spawn(codexInvocation.command, [...codexInvocation.args, 'app-server'], {  // nosemgrep: javascript.lang.security.audit.spawn-shell-true.spawn-shell-true -- shell option defaults to false; args controlled internally
    cwd: workspaceDir,
    env,
    shell: codexInvocation.shell || false,
    stdio: ['pipe', 'pipe', 'pipe']
  });

  const pending = new Map();
  let stdout = '';
  let stderr = '';
  let settled = false;
  const rl = readline.createInterface({ input: child.stdout });

  const clearPending = (error) => {
    for (const [id, state] of pending) {
      clearTimeout(state.timer);
      state.reject(error || new Error(`${id}_cleared`));
    }
    pending.clear();
  };

  const send = (message) => {
    child.stdin.write(`${JSON.stringify(message)}\n`);
  };

  const request = (id, method, params, ms = timeoutMs) =>
    new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`${method}_timeout`));
      }, ms);
      pending.set(id, {
        timer,
        resolve: (value) => {
          clearTimeout(timer);
          pending.delete(id);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timer);
          pending.delete(id);
          reject(error);
        }
      });
      send({ jsonrpc: '2.0', id, method, ...(params === undefined ? {} : { params }) });
    });

  child.stderr.on('data', (buf) => {
    stderr += String(buf || '');
  });
  child.on('error', (error) => {
    clearPending(error);
  });
  rl.on('line', (line) => {
    stdout += `${line}\n`;
    let message = null;
    try {
      message = JSON.parse(line);
    } catch {
      return;
    }
    if (!Object.prototype.hasOwnProperty.call(message, 'id') || !pending.has(message.id)) return;
    const state = pending.get(message.id);
    if (message.error) state.reject(new Error(message.error?.message || `${message.id}_error`));
    else state.resolve(message.result);
  });

  const hardTimeout = setTimeout(() => {
    if (settled) return;
    clearPending(new Error('app_server_timeout'));
    void terminateChild(child);
  }, timeoutMs * 2);
  hardTimeout.unref?.();

  try {
    const initialize = await request(1, 'initialize', {
      clientInfo: { name: 'agent-skills-toolchain-manager', version: '0.1.0' },
      capabilities: null
    });
    send({ jsonrpc: '2.0', method: 'initialized', params: {} });
    const result = await fn({ request, initialize, stdoutRef: () => stdout, stderrRef: () => stderr });
    settled = true;
    clearTimeout(hardTimeout);
    await terminateChild(child);
    try {
      rl.close();
    } catch {}
    return result;
  } catch (error) {
    settled = true;
    clearTimeout(hardTimeout);
    await terminateChild(child);
    try {
      rl.close();
    } catch {}
    error.stdout = stdout;
    error.stderr = stderr;
    throw error;
  }
}
