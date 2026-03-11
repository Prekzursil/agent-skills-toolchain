import { execFile, spawn } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import { legacyStateDir, migrateLegacyStateDir, readState, readToken } from './state.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const execFileAsync = promisify(execFile);

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function fileExists(p) {
  try {
    await fs.stat(p);
    return true;
  } catch {
    return false;
  }
}

function desktopAutostartEnabled({ env = process.env } = {}) {
  const raw = String(env.PROMPTBRIDGE_DESKTOP_AUTOSTART || env.AGENTIFY_DESKTOP_AUTOSTART || '').trim().toLowerCase();
  if (!raw) return true;
  if (['0', 'false', 'no', 'off'].includes(raw)) return false;
  if (['1', 'true', 'yes', 'on'].includes(raw)) return true;
  return true;
}

function isWslEnvironment({ platform = process.platform, env = process.env } = {}) {
  return platform === 'linux' && !!(env.WSL_DISTRO_NAME || env.WSL_INTEROP);
}

async function readWslNameserver({ resolvConfPath = '/etc/resolv.conf' } = {}) {
  try {
    const raw = await fs.readFile(resolvConfPath, 'utf8');
    const line = raw
      .split(/\r?\n/)
      .map((entry) => entry.trim())
      .find((entry) => /^nameserver\s+\S+$/i.test(entry));
    if (!line) return null;
    return line.split(/\s+/)[1] || null;
  } catch {
    return null;
  }
}

function dedupe(values) {
  return [...new Set(values.filter(Boolean))];
}

export async function connectionBaseUrlCandidates({
  state,
  port,
  platform = process.platform,
  env = process.env,
  resolvConfPath = '/etc/resolv.conf',
  wslHostCandidates = null
} = {}) {
  const resolvedPort = Number(port ?? state?.port ?? 0);
  if (!resolvedPort) return [];

  const candidates = [];
  const explicitBaseUrl = String(env.PROMPTBRIDGE_DESKTOP_BASE_URL || env.AGENTIFY_DESKTOP_BASE_URL || '').trim();
  if (explicitBaseUrl) {
    candidates.push(explicitBaseUrl);
  }

  const stateBaseUrl = String(state?.baseUrl || '').trim();
  if (stateBaseUrl) {
    candidates.push(stateBaseUrl);
  }

  const stateHost = String(state?.host || '').trim();
  if (stateHost && stateHost !== '0.0.0.0') {
    candidates.push(`http://${stateHost}:${resolvedPort}`);
  }

  candidates.push(`http://127.0.0.1:${resolvedPort}`);

  if (isWslEnvironment({ platform, env })) {
    const hostCandidates = Array.isArray(wslHostCandidates)
      ? wslHostCandidates
      : await detectWslHostCandidates({ resolvConfPath });
    for (const host of hostCandidates) candidates.push(`http://${host}:${resolvedPort}`);
  }

  return dedupe(candidates);
}

export async function loadConnection({
  stateDir,
  platform = process.platform,
  env = process.env,
  resolvConfPath = '/etc/resolv.conf',
  wslHostCandidates = null
} = {}) {
  const primary = await loadConnectionFromDir(stateDir, { platform, env, resolvConfPath, wslHostCandidates });
  if (primary) return primary;

  const fallbackDir = deriveLegacyFallbackDir(stateDir);
  if (!fallbackDir || fallbackDir === stateDir) return null;

  await migrateLegacyStateDir({ targetDir: stateDir, legacyDir: fallbackDir }).catch(() => null);
  const migrated = await loadConnectionFromDir(stateDir, { platform, env, resolvConfPath, wslHostCandidates });
  if (migrated) return migrated;

  return await loadConnectionFromDir(fallbackDir, { platform, env, resolvConfPath, wslHostCandidates });
}

async function loadConnectionFromDir(
  stateDir,
  { platform = process.platform, env = process.env, resolvConfPath = '/etc/resolv.conf', wslHostCandidates = null } = {}
) {
  const state = await readState(stateDir);
  const token = await readToken(stateDir);
  if (!state?.port || !token) return null;
  const baseUrlCandidates = await connectionBaseUrlCandidates({ state, platform, env, resolvConfPath, wslHostCandidates });
  return {
    baseUrl: baseUrlCandidates[0] || `http://127.0.0.1:${state.port}`,
    baseUrlCandidates,
    token,
    serverId: state.serverId || null
  };
}

async function detectWslHostCandidates({ resolvConfPath = '/etc/resolv.conf' } = {}) {
  const candidates = [];
  const nameserver = await readWslNameserver({ resolvConfPath });
  if (nameserver) candidates.push(nameserver);

  try {
    const { stdout } = await execFileAsync('powershell.exe', [
      '-NoProfile',
      '-Command',
      "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -like '*WSL*' -or $_.InterfaceAlias -like '*vEthernet*' } | ForEach-Object { $_.IPAddress }"
    ]);
    for (const line of String(stdout || '')
      .split(/\r?\n/)
      .map((entry) => entry.trim())
      .filter(Boolean)) {
      candidates.push(line);
    }
  } catch {}

  return dedupe(candidates);
}

function detectInstalledDesktopLauncher({ env = process.env, platform = process.platform } = {}) {
  const explicit = String(env.PROMPTBRIDGE_DESKTOP_LAUNCHER || env.AGENTIFY_DESKTOP_LAUNCHER || '').trim();
  if (explicit) return { command: explicit, args: [] };

  if (platform === 'win32') {
    const localAppData = String(env.LOCALAPPDATA || '').trim();
    const candidates = [
      localAppData ? path.join(localAppData, 'PromptBridgeDesktop', 'launch-agentify-desktop.cmd') : null,
      localAppData ? path.join(localAppData, 'AgentifyDesktop', 'launch-agentify-desktop.cmd') : null
    ].filter(Boolean);
    for (const candidate of candidates) {
      return { command: candidate, args: [] };
    }
  }

  return null;
}

function deriveLegacyFallbackDir(stateDir) {
  if (!stateDir) return legacyStateDir();
  const normalized = path.resolve(stateDir);
  if (path.basename(normalized) === '.promptbridge-desktop') {
    return path.join(path.dirname(normalized), '.agentify-desktop');
  }
  return legacyStateDir({ homeDir: path.dirname(normalized) });
}

async function validateConn({ conn, fetchImpl }) {
  const attempts = [];
  const baseUrls = conn?.baseUrlCandidates?.length ? conn.baseUrlCandidates : [conn?.baseUrl].filter(Boolean);

  for (const baseUrl of baseUrls) {
    try {
      const health = await fetchImpl(`${baseUrl}/health`);
      const healthData = await health.json().catch(() => ({}));
      if (!health.ok) {
        attempts.push({ baseUrl, reason: 'health_not_ok', status: health.status });
        continue;
      }
      if (conn.serverId && healthData?.serverId && conn.serverId !== healthData.serverId) {
        attempts.push({ baseUrl, reason: 'server_id_mismatch', healthServerId: healthData?.serverId || null });
        continue;
      }

      const status = await fetchImpl(`${baseUrl}/status`, { headers: { authorization: `Bearer ${conn.token}` } });
      const statusData = await status.json().catch(() => ({}));
      if (!status.ok) {
        attempts.push({ baseUrl, reason: 'status_not_ok', status: status.status });
        continue;
      }
      if (statusData?.error === 'unauthorized') {
        attempts.push({ baseUrl, reason: 'unauthorized' });
        continue;
      }
      if (statusData?.ok !== true) {
        attempts.push({ baseUrl, reason: 'unexpected_status_payload' });
        continue;
      }
      return { ok: true, serverId: healthData?.serverId || null, baseUrl };
    } catch (error) {
      attempts.push({ baseUrl, reason: 'request_failed', error: error?.message || String(error) });
    }
  }

  const last = attempts.at(-1) || { reason: 'no_base_urls' };
  return { ok: false, ...last, attempts };
}

export async function requestJson({ baseUrl, token, method, path: pth, body, fetchImpl = fetch }) {
  const res = await fetchImpl(`${baseUrl}${pth}`, {
    method,
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${token}`
    },
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data?.error) {
    const err = new Error(data?.message || data?.error || `http_${res.status}`);
    err.data = { status: res.status, body: data };
    throw err;
  }
  return data;
}

export async function ensureDesktopRunning({
  stateDir,
  fetchImpl = fetch,
  spawnImpl = spawn,
  timeoutMs = 30_000,
  showTabs = false,
  platform = process.platform,
  env = process.env,
  resolvConfPath = '/etc/resolv.conf',
  wslHostCandidates = null
}) {
  const conn = await loadConnection({ stateDir, platform, env, resolvConfPath, wslHostCandidates });
  if (conn) {
    try {
      const v = await validateConn({ conn, fetchImpl });
      if (v.ok) return { ...conn, baseUrl: v.baseUrl };
    } catch {
      // fallthrough to spawn
    }
  }

  if (!desktopAutostartEnabled({ env })) {
    const error = new Error('desktop_autostart_disabled');
    error.data = { reason: 'desktop_autostart_disabled', stateDir };
    throw error;
  }

  const defaultElectronBin = path.resolve('node_modules', '.bin', process.platform === 'win32' ? 'electron.cmd' : 'electron');
  const entry = path.join(__dirname, 'main.mjs');
  const usingCustomSpawn = spawnImpl !== spawn;
  const installedLauncher = detectInstalledDesktopLauncher({ env, platform });
  let launchCommand = null;
  let launchArgs = [];
  if (await fileExists(entry)) {
    let electronBin = defaultElectronBin;
    if (!(await fileExists(electronBin))) {
      if (usingCustomSpawn) {
        electronBin = process.env.AGENTIFY_DESKTOP_ELECTRON_BIN || 'electron';
      } else {
        throw new Error('missing_electron_binary');
      }
    }
    launchCommand = electronBin;
    launchArgs = [entry];
  } else if (installedLauncher?.command) {
    launchCommand = installedLauncher.command;
    launchArgs = installedLauncher.args || [];
  } else if (usingCustomSpawn) {
    launchCommand = process.env.AGENTIFY_DESKTOP_ELECTRON_BIN || 'electron';
    launchArgs = [entry];
  } else {
    throw new Error('missing_desktop_entry');
  }

  let resolvedLaunchCommand = launchCommand;
  let resolvedLaunchArgs = launchArgs;
  if (platform === 'win32' && /\.(cmd|bat)$/i.test(launchCommand)) {
    const commandLine = [
      `"${launchCommand}"`,
      ...launchArgs.map((arg) => /[\s"]/u.test(arg) ? `"${String(arg).replace(/"/g, '\\"')}"` : String(arg))
    ].join(' ');
    resolvedLaunchCommand = 'cmd.exe';
    resolvedLaunchArgs = ['/d', '/s', '/c', commandLine];
  }

  spawnImpl(resolvedLaunchCommand, resolvedLaunchArgs, {
    stdio: 'ignore',
    env: {
      ...process.env,
      AGENTIFY_DESKTOP_STATE_DIR: stateDir,
      ...(showTabs ? { AGENTIFY_DESKTOP_SHOW_TABS: 'true' } : {})
    }
  })?.unref?.();

  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const c = await loadConnection({ stateDir, platform, env, resolvConfPath, wslHostCandidates });
    if (c) {
      try {
        const v = await validateConn({ conn: c, fetchImpl });
        if (v.ok) return { ...c, baseUrl: v.baseUrl };
      } catch {}
    }
    await sleep(300);
  }
  throw new Error('desktop_start_timeout');
}

