import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import readline from 'node:readline';

import { ensureDesktopRunning, loadConnection, requestJson } from '../../../../web/promptbridge-talk-lane/src/mcp-lib.mjs';
import { resolveCodexInvocation, runCodexExec } from '../../src/orchestrator/codex.mjs';
import {
  defaultCodexHome,
  defaultMirrorCodexHome,
  detectBootstrapEnvironment,
  getBootstrapStatus,
  promptBridgeRepoRoot,
  stateDirForBootstrap
} from './bootstrap.mjs';

const PROMPTBRIDGE_TOOL_BASE_NAMES = [
  'query',
  'read_page',
  'navigate',
  'ensure_ready',
  'show',
  'hide',
  'status',
  'session_state',
  'session_configure',
  'image_gen',
  'download_images',
  'tabs',
  'tab_create',
  'tab_close',
  'shutdown',
  'rotate_token',
  'discuss',
  'curate'
];

const CODEX_TOOL_NAMES = [
  'codex_consult',
  'codex_brainstorm',
  'codex_review',
  'codex_discuss',
  'codex_coordinate',
  'codex_curate'
];

export function expectedCodexToolNames() {
  return [...CODEX_TOOL_NAMES];
}

export function expectedPromptbridgeToolNames() {
  return PROMPTBRIDGE_TOOL_BASE_NAMES.flatMap((name) => [`promptbridge_${name}`, `agentify_${name}`]);
}

export function expectedToolNames() {
  return [...expectedCodexToolNames(), ...expectedPromptbridgeToolNames()];
}

export function parseAgentJsonResult(stdout) {
  const lines = String(stdout || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

  for (let idx = lines.length - 1; idx >= 0; idx -= 1) {
    let outer;
    try {
      outer = JSON.parse(lines[idx]);
    } catch {
      continue;
    }
    const item = outer?.item;
    if (item?.type !== 'agent_message' || typeof item?.text !== 'string') continue;
    try {
      return JSON.parse(item.text);
    } catch {
      continue;
    }
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

async function readJsonIfPresent(file) {
  try {
    return JSON.parse(await fs.readFile(file, 'utf8'));
  } catch {
    return null;
  }
}

export async function resolveProbeClientModulePaths({
  serverEntrypoint = null,
  cwd = promptBridgeRepoRoot()
} = {}) {
  const runtimeRoot = serverEntrypoint ? path.dirname(serverEntrypoint) : cwd;
  const resolutionBase = serverEntrypoint || path.join(runtimeRoot, '__promptbridge_probe__.mjs');

  let searchDir = runtimeRoot;
  while (true) {
    const sdkClientDir = path.join(searchDir, 'node_modules', '@modelcontextprotocol', 'sdk', 'dist', 'esm', 'client');
    const clientIndexPath = path.join(sdkClientDir, 'index.js');
    const clientStdioPath = path.join(sdkClientDir, 'stdio.js');
    if ((await pathExists(clientIndexPath)) && (await pathExists(clientStdioPath))) {
      return {
        ok: true,
        runtimeRoot,
        resolutionBase,
        moduleSearchRoot: searchDir,
        clientIndexPath,
        clientStdioPath
      };
    }

    const parentDir = path.dirname(searchDir);
    if (parentDir === searchDir) {
      return {
        ok: false,
        runtimeRoot,
        resolutionBase,
        moduleSearchRoot: searchDir,
        reason: 'missing_runtime_modules',
        error: 'Unable to locate @modelcontextprotocol/sdk/dist/esm/client under the server entrypoint or any parent directory.',
        clientIndexPath,
        clientStdioPath
      };
    }
    searchDir = parentDir;
  }
}

function parseProcEnv(raw) {
  const env = {};
  for (const entry of String(raw || '').split('\0')) {
    if (!entry) continue;
    const idx = entry.indexOf('=');
    if (idx <= 0) continue;
    env[entry.slice(0, idx)] = entry.slice(idx + 1);
  }
  return env;
}

async function detectVsCodeOriginatorCodexHome({
  spawnImpl = spawn,
  timeoutMs = 5_000
} = {}) {
  const env = { ...process.env, CODEX_INTERNAL_ORIGINATOR_OVERRIDE: 'codex_vscode' };
  delete env.CODEX_HOME;

  return await new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    let settled = false;
    const child = spawnImpl('bash', ['-lc', 'printf "%s" "$CODEX_HOME"'], {
      env,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    const finish = (payload) => {
      if (settled) return;
      settled = true;
      resolve(payload);
    };

    const timer = setTimeout(() => {
      try {
        child.kill('SIGTERM');
      } catch {}
      finish({ ok: false, reason: 'originator_home_timeout', stdout, stderr });
    }, timeoutMs);

    child.stdout.on('data', (buf) => {
      stdout += String(buf || '');
    });
    child.stderr.on('data', (buf) => {
      stderr += String(buf || '');
    });
    child.on('error', (error) => {
      clearTimeout(timer);
      finish({ ok: false, reason: 'originator_home_spawn_error', error: error?.message || String(error), stdout, stderr });
    });
    child.on('exit', (code) => {
      clearTimeout(timer);
      const codexHome = stdout.trim() || null;
      finish({
        ok: code === 0 && !!codexHome,
        reason: code === 0 && codexHome ? null : 'originator_home_missing',
        codexHome,
        stdout,
        stderr,
        code
      });
    });
  });
}

async function listLiveVsCodeAppServers({
  procRoot = '/proc'
} = {}) {
  const out = [];
  let entries = [];
  try {
    entries = await fs.readdir(procRoot, { withFileTypes: true });
  } catch {
    return out;
  }

  for (const entry of entries) {
    if (!entry.isDirectory() || !/^\d+$/.test(entry.name)) continue;
    const pid = Number(entry.name);
    const cmdlinePath = path.join(procRoot, entry.name, 'cmdline');
    const environPath = path.join(procRoot, entry.name, 'environ');
    let cmdline = '';
    try {
      cmdline = await fs.readFile(cmdlinePath, 'utf8');
    } catch {
      continue;
    }
    const cmd = cmdline.replace(/\0+/g, ' ').trim();
    if (!/openai\.chatgpt-.*codex app-server/i.test(cmd)) continue;

    let env = {};
    try {
      env = parseProcEnv(await fs.readFile(environPath, 'utf8'));
    } catch {
      env = {};
    }
    out.push({
      pid,
      cmd,
      codexHome: env.CODEX_HOME || null,
      originatorOverride: env.CODEX_INTERNAL_ORIGINATOR_OVERRIDE || null
    });
  }

  return out;
}

async function findOpenAiExtension({ extensionsRoot }) {
  try {
    const entries = await fs.readdir(extensionsRoot, { withFileTypes: true });
    const matches = entries
      .filter((entry) => entry.isDirectory() && /^openai\.chatgpt-/i.test(entry.name))
      .map((entry) => path.join(extensionsRoot, entry.name))
      .sort((a, b) => b.localeCompare(a));
    return matches[0] || null;
  } catch {
    return null;
  }
}

function detectVsCodePaths({ platform = process.platform, isWsl = false, windowsHome = null, homeDir = os.homedir() } = {}) {
  if (isWsl && windowsHome) {
    return {
      settingsPath: path.join(windowsHome, 'AppData', 'Roaming', 'Code', 'User', 'settings.json'),
      extensionsRoot: path.join(windowsHome, '.vscode', 'extensions')
    };
  }
  if (platform === 'win32') {
    const base = windowsHome || process.env.USERPROFILE || homeDir;
    const appData = process.env.APPDATA || path.join(base, 'AppData', 'Roaming');
    return {
      settingsPath: path.join(appData, 'Code', 'User', 'settings.json'),
      extensionsRoot: path.join(base, '.vscode', 'extensions')
    };
  }
  return {
    settingsPath: path.join(homeDir, '.config', 'Code', 'User', 'settings.json'),
    extensionsRoot: path.join(homeDir, '.vscode', 'extensions')
  };
}

function mirrorFailureLayer(profile) {
  const reasons = Array.isArray(profile?.driftReasons) ? profile.driftReasons : [];
  const hasFiles = Object.values(profile?.presentFiles || {}).some(Boolean);
  return reasons.length > 0 && !hasFiles ? 'mirror_missing' : 'mirror_drift';
}

export async function probeDesktopConnection({ stateDir, fetchImpl = fetch } = {}) {
  const initialConn = await loadConnection({ stateDir });
  const baseUrls = initialConn?.baseUrlCandidates?.length ? initialConn.baseUrlCandidates : [initialConn?.baseUrl].filter(Boolean);
  const attempts = [];

  const inspectConnection = async (conn) => {
    const urls = conn?.baseUrlCandidates?.length ? conn.baseUrlCandidates : [conn?.baseUrl].filter(Boolean);
    for (const baseUrl of urls) {
      let health;
      try {
        health = await fetchImpl(`${baseUrl}/health`);
      } catch (error) {
        attempts.push({ baseUrl, reason: 'health_request_failed', error: error?.message || String(error) });
        continue;
      }
      const healthBody = await health.json().catch(() => ({}));
      if (!health.ok) {
        attempts.push({ baseUrl, reason: 'health_not_ok', status: health.status, health: healthBody });
        continue;
      }

      try {
        const status = await requestJson({
          baseUrl,
          token: conn.token,
          method: 'GET',
          path: '/status',
          fetchImpl
        });
        return { ok: true, conn: { ...conn, baseUrl }, health: healthBody, status, stateDir };
      } catch (error) {
        attempts.push({
          baseUrl,
          reason: error?.message || 'status_request_failed',
          error: { status: error?.data?.status || null, body: error?.data?.body || null }
        });
      }
    }
    return null;
  };

  if (initialConn) {
    const initialResult = await inspectConnection(initialConn);
    if (initialResult) return initialResult;
  }

  try {
    const ensured = await ensureDesktopRunning({ stateDir, fetchImpl, timeoutMs: 20_000 });
    const ensuredResult = await inspectConnection(ensured);
    if (ensuredResult) return ensuredResult;
  } catch (error) {
    attempts.push({ baseUrl: baseUrls[0] || null, reason: 'desktop_start_failed', error: error?.message || String(error) });
  }

  const last = attempts.at(-1) || { reason: 'health_request_failed', error: 'no_base_urls' };
  return {
    ok: false,
    reason: last.reason,
    stateDir,
    conn: initialConn,
    attempts,
    error: last.error || null,
    status: last.status || null,
    health: last.health || null
  };
}

export async function probeMcpServerStartup({
  command,
  args = [],
  env = process.env,
  cwd = promptBridgeRepoRoot(),
  spawnImpl = spawn,
  timeoutMs = 120_000
} = {}) {
  if (!command) throw new Error('missing_command');
  const serverEntrypoint = args[0] ? path.resolve(cwd, args[0]) : null;
  const clientResolution = await resolveProbeClientModulePaths({ serverEntrypoint, cwd });
  const runtimeRoot = clientResolution.runtimeRoot;
  const clientIndexPath = clientResolution.clientIndexPath;
  const clientStdioPath = clientResolution.clientStdioPath;

  if (!clientResolution.ok) {
    return {
      ok: false,
      reason: clientResolution.reason || 'missing_runtime_modules',
      phase: 'startup',
      runtimeRoot,
      resolutionBase: clientResolution.resolutionBase,
      error: clientResolution.error || null,
      clientIndexPath,
      clientStdioPath
    };
  }

  const probeDir = await fs.mkdtemp(path.join(os.tmpdir(), 'promptbridge-mcp-probe-'));
  const probeScript = path.join(probeDir, 'handshake.mjs');
  const resultFile = path.join(probeDir, 'result.json');
  const script = `import { Client } from ${JSON.stringify(pathToFileURL(clientIndexPath).href)};
import { StdioClientTransport } from ${JSON.stringify(pathToFileURL(clientStdioPath).href)};
import fs from 'node:fs/promises';

const startedAt = Date.now();
const transport = new StdioClientTransport({
  command: ${JSON.stringify(command)},
  args: ${JSON.stringify(args)},
  env: ${JSON.stringify(env)},
  cwd: ${JSON.stringify(cwd)},
  stderr: 'pipe'
});
let stderr = '';
transport.stderr?.on('data', (buf) => { stderr += String(buf || ''); });
transport.onerror = (error) => { stderr += '[transport-error] ' + (error?.stack || error?.message || String(error)) + '\\n'; };

const client = new Client({ name: 'promptbridge-probe', version: '0.0.0' });
client.onerror = (error) => { stderr += '[client-error] ' + (error?.stack || error?.message || String(error)) + '\\n'; };

try {
  await client.connect(transport);
  const connectedAt = Date.now();
  const tools = await client.listTools();
  const listedAt = Date.now();
  await client.close().catch(() => {});
  await fs.writeFile(${JSON.stringify(resultFile)}, JSON.stringify({
    ok: true,
    phase: 'handshake',
    connectMs: connectedAt - startedAt,
    listMs: listedAt - connectedAt,
    totalMs: listedAt - startedAt,
    toolNames: (tools.tools || []).map((tool) => tool.name),
    stderr
  }, null, 2));
} catch (error) {
  try { await client.close(); } catch {}
  await fs.writeFile(${JSON.stringify(resultFile)}, JSON.stringify({
    ok: false,
    phase: 'handshake',
    reason: 'handshake_failed',
    error: error?.stack || error?.message || String(error),
    stderr
  }, null, 2));
  process.exit(1);
}`;

  await fs.writeFile(probeScript, script, 'utf8');

  const result = await new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    let settled = false;
    const child = spawnImpl(command, [probeScript], {
      cwd: runtimeRoot,
      env,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    const finish = async (payload) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      const filePayload = await readJsonIfPresent(resultFile);
      resolve({ stdout, stderr, ...payload, filePayload });
    };

    const timer = setTimeout(() => {
      try {
        child.kill('SIGTERM');
      } catch {}
      void finish({ ok: false, reason: 'startup_timeout', phase: 'startup' });
    }, timeoutMs);

    child.stdout.on('data', (buf) => {
      stdout += String(buf || '');
    });
    child.stderr.on('data', (buf) => {
      stderr += String(buf || '');
    });
    child.on('error', (error) => {
      void finish({ ok: false, reason: 'spawn_error', phase: 'startup', error: error?.message || String(error) });
    });
    child.on('exit', (code, signal) => {
      void finish({ ok: code === 0, code, signal, phase: 'handshake' });
    });
  });

  await fs.rm(probeDir, { recursive: true, force: true }).catch(() => {});

  const payload = result.filePayload || {};
  if (result.ok && payload.ok) {
    return {
      ok: true,
      phase: 'handshake',
      runtimeRoot,
      toolNames: payload.toolNames || [],
      connectMs: payload.connectMs ?? null,
      listMs: payload.listMs ?? null,
      totalMs: payload.totalMs ?? null,
      stdout: result.stdout,
      stderr: payload.stderr || result.stderr
    };
  }

  return {
    ok: false,
    phase: payload.phase || result.phase || 'handshake',
    reason: payload.reason || result.reason || 'process_exit',
    error: payload.error || result.error || null,
    runtimeRoot,
    toolNames: payload.toolNames || [],
    stdout: result.stdout,
    stderr: payload.stderr || result.stderr,
    code: result.code ?? null,
    signal: result.signal ?? null
  };
}

function extractStructuredToolPayload(callResult) {
  const structuredContent =
    callResult?.structuredContent && typeof callResult.structuredContent === 'object' ? callResult.structuredContent : null;
  let parsedTextJson = null;
  const textEntry = Array.isArray(callResult?.content)
    ? callResult.content.find((entry) => entry?.type === 'text' && typeof entry.text === 'string')
    : null;
  if (textEntry?.text) {
    try {
      parsedTextJson = JSON.parse(textEntry.text);
    } catch {}
  }
  return { structuredContent, parsedTextJson };
}

export async function callMcpServerTool({
  command,
  args = [],
  env = process.env,
  cwd = promptBridgeRepoRoot(),
  spawnImpl = spawn,
  timeoutMs = 120_000,
  toolName,
  toolArguments = {}
} = {}) {
  if (!command) throw new Error('missing_command');
  if (!toolName) throw new Error('missing_tool_name');
  const serverEntrypoint = args[0] ? path.resolve(cwd, args[0]) : null;
  const clientResolution = await resolveProbeClientModulePaths({ serverEntrypoint, cwd });
  const runtimeRoot = clientResolution.runtimeRoot;
  const clientIndexPath = clientResolution.clientIndexPath;
  const clientStdioPath = clientResolution.clientStdioPath;

  if (!clientResolution.ok) {
    return {
      ok: false,
      reason: clientResolution.reason || 'missing_runtime_modules',
      phase: 'startup',
      runtimeRoot,
      resolutionBase: clientResolution.resolutionBase,
      error: clientResolution.error || null,
      clientIndexPath,
      clientStdioPath,
      toolName
    };
  }

  const probeDir = await fs.mkdtemp(path.join(os.tmpdir(), 'promptbridge-mcp-tool-'));
  const probeScript = path.join(probeDir, 'call-tool.mjs');
  const resultFile = path.join(probeDir, 'result.json');
  const script = `import { Client } from ${JSON.stringify(pathToFileURL(clientIndexPath).href)};
import { StdioClientTransport } from ${JSON.stringify(pathToFileURL(clientStdioPath).href)};
import fs from 'node:fs/promises';

const startedAt = Date.now();
const transport = new StdioClientTransport({
  command: ${JSON.stringify(command)},
  args: ${JSON.stringify(args)},
  env: ${JSON.stringify(env)},
  cwd: ${JSON.stringify(cwd)},
  stderr: 'pipe'
});
let stderr = '';
transport.stderr?.on('data', (buf) => { stderr += String(buf || ''); });
transport.onerror = (error) => { stderr += '[transport-error] ' + (error?.stack || error?.message || String(error)) + '\\n'; };

const client = new Client({ name: 'promptbridge-tool-call', version: '0.0.0' });
client.onerror = (error) => { stderr += '[client-error] ' + (error?.stack || error?.message || String(error)) + '\\n'; };

try {
  await client.connect(transport);
  const connectedAt = Date.now();
  const tools = await client.listTools();
  const listedAt = Date.now();
  const result = await client.callTool({ name: ${JSON.stringify(toolName)}, arguments: ${JSON.stringify(toolArguments)} });
  const calledAt = Date.now();
  await client.close().catch(() => {});
  await fs.writeFile(${JSON.stringify(resultFile)}, JSON.stringify({
    ok: true,
    phase: 'call',
    connectMs: connectedAt - startedAt,
    listMs: listedAt - connectedAt,
    callMs: calledAt - listedAt,
    totalMs: calledAt - startedAt,
    toolNames: (tools.tools || []).map((tool) => tool.name),
    result,
    stderr
  }, null, 2));
} catch (error) {
  try { await client.close(); } catch {}
  await fs.writeFile(${JSON.stringify(resultFile)}, JSON.stringify({
    ok: false,
    phase: 'call',
    reason: 'tool_call_failed',
    error: error?.stack || error?.message || String(error),
    stderr
  }, null, 2));
  process.exit(1);
}`;

  await fs.writeFile(probeScript, script, 'utf8');

  const result = await new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    let settled = false;
    const child = spawnImpl(command, [probeScript], {
      cwd: runtimeRoot,
      env,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    const finish = async (payload) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      const filePayload = await readJsonIfPresent(resultFile);
      resolve({ stdout, stderr, ...payload, filePayload });
    };

    const timer = setTimeout(() => {
      try {
        child.kill('SIGTERM');
      } catch {}
      void finish({ ok: false, reason: 'tool_call_timeout', phase: 'call', toolName });
    }, timeoutMs);

    child.stdout.on('data', (buf) => {
      stdout += String(buf || '');
    });
    child.stderr.on('data', (buf) => {
      stderr += String(buf || '');
    });
    child.on('error', (error) => {
      void finish({ ok: false, reason: 'spawn_error', phase: 'startup', error: error?.message || String(error), toolName });
    });
    child.on('exit', (code, signal) => {
      void finish({ ok: code === 0, code, signal, phase: code === 0 ? 'call' : 'startup', toolName });
    });
  });

  await fs.rm(probeDir, { recursive: true, force: true }).catch(() => {});

  const payload = result.filePayload || {};
  const extracted = extractStructuredToolPayload(payload.result || null);
  return {
    ok: result.ok && payload.ok === true,
    phase: payload.phase || result.phase || 'call',
    reason: payload.reason || result.reason || null,
    runtimeRoot,
    toolName,
    toolNames: payload.toolNames || [],
    result: payload.result || null,
    structuredContent: extracted.structuredContent,
    parsedTextJson: extracted.parsedTextJson,
    stdout: result.stdout,
    stderr: payload.stderr || result.stderr,
    error: payload.error || result.error || null,
    code: result.code ?? null,
    signal: result.signal ?? null
  };
}


function synthesizeDirectVisibility({ consultation, talkLane } = {}) {
  const codexToolName =
    consultation?.parsed?.tool_visible === true
      ? 'codex_consult'
      : Array.isArray(consultation?.raw?.toolNames) && consultation.raw.toolNames.includes('codex_consult')
        ? 'codex_consult'
        : null;
  const promptbridgeToolName =
    talkLane?.parsed?.tool_visible === true
      ? talkLane.parsed.tool_name || null
      : Array.isArray(talkLane?.status?.toolNames) && talkLane.status.toolNames.includes('promptbridge_status')
        ? 'promptbridge_status'
        : Array.isArray(talkLane?.status?.toolNames) && talkLane.status.toolNames.includes('agentify_status')
          ? 'agentify_status'
          : null;

  return {
    ok: !!codexToolName && !!promptbridgeToolName,
    reason: codexToolName && promptbridgeToolName ? null : 'direct_lane_proof_incomplete',
    parsed: {
      codex_tool_visible: !!codexToolName,
      codex_tool_name: codexToolName,
      promptbridge_tool_visible: !!promptbridgeToolName,
      promptbridge_tool_name: promptbridgeToolName,
      status_ok:
        consultation?.parsed?.consultation_ok === true &&
        talkLane?.parsed?.status_ok === true,
      url: talkLane?.parsed?.url ?? null,
      blocked: talkLane?.parsed?.blocked ?? null,
      fallback_to_lane_a:
        !(
          consultation?.parsed?.consultation_ok === true &&
          talkLane?.parsed?.status_ok === true
        )
    }
  };
}

export async function runPromptbridgeStatusCheck({
  codexHome,
  workspaceDir = promptBridgeRepoRoot(),
  platform = process.platform,
  isWsl = false,
  windowsHome = null,
  homeDir = os.homedir(),
  getBootstrapStatusImpl = getBootstrapStatus,
  callMcpServerToolImpl = callMcpServerTool
} = {}) {
  const bootstrap = await getBootstrapStatusImpl({
    codexHome,
    mirrorCodexHome: defaultMirrorCodexHome({ homeDir }),
    platform,
    isWsl,
    windowsHome,
    homeDir,
    nodeExecutable: process.execPath
  });
  const promptbridgeServerSpec = bootstrap.managedServers?.codexConsult || bootstrap.managedServer || null;
  if (!promptbridgeServerSpec) {
    return {
      ok: false,
      reason: 'managed_server_spec_missing',
      parsed: {
        tool_visible: false,
        tool_name: null,
        status_ok: false,
        url: null,
        blocked: null,
        fallback_to_lane_a: true
      }
    };
  }

  const serverEnv = { ...process.env, ...promptbridgeServerSpec.env };
  const ready = await callMcpServerToolImpl({
    command: promptbridgeServerSpec.command,
    args: promptbridgeServerSpec.args,
    env: serverEnv,
    cwd: workspaceDir,
    toolName: 'promptbridge_ensure_ready',
    toolArguments: { key: 'promptbridge-probe' },
    timeoutMs: 90_000
  });
  const status = ready.ok
    ? await callMcpServerToolImpl({
        command: promptbridgeServerSpec.command,
        args: promptbridgeServerSpec.args,
        env: serverEnv,
        cwd: workspaceDir,
        toolName: 'promptbridge_status',
        toolArguments: { key: 'promptbridge-probe' },
        timeoutMs: 90_000
      })
    : null;

  const payload = status?.structuredContent || status?.parsedTextJson || null;
  const toolNames = [...new Set([...(ready?.toolNames || []), ...(status?.toolNames || [])])];
  const visibleName = toolNames.includes('promptbridge_status')
    ? 'promptbridge_status'
    : toolNames.includes('agentify_status')
      ? 'agentify_status'
      : null;
  const ok = ready?.ok === true && status?.ok === true && payload?.ok === true;

  return {
    ok,
    reason: ok ? null : ready?.reason || status?.reason || 'status_call_failed',
    parsed: {
      tool_visible: !!visibleName,
      tool_name: visibleName,
      status_ok: ok,
      url: payload?.url ?? null,
      blocked: payload?.blocked ?? null,
      fallback_to_lane_a: !ok
    },
    ready,
    status
  };
}

export async function runToolVisibilityCheck({
  codexHome,
  workspaceDir = promptBridgeRepoRoot(),
  runCodexExecImpl = runCodexExec
} = {}) {
  const prompt =
    'Reply with exactly one JSON object containing keys codex_tool_visible, codex_tool_name, promptbridge_tool_visible, promptbridge_tool_name, status_ok, url, blocked, fallback_to_lane_a. ' +
    'Set codex_tool_visible=true and codex_tool_name="codex_consult" only if you can see codex_consult in this session. ' +
    'Set promptbridge_tool_visible=true and promptbridge_tool_name to "promptbridge_status" if you can see that tool, otherwise "agentify_status" if you can see that tool; otherwise set promptbridge_tool_visible=false and promptbridge_tool_name=null. ' +
    'Do not call any tools. Set status_ok=true only if both codex_consult and one PromptBridge status tool are visible. Set url=null and blocked=null. Set fallback_to_lane_a=false only if both are visible; otherwise true. ' +
    'No markdown, no prose.';

  const out = await runCodexExecImpl({
    workspaceDir,
    prompt,
    ephemeral: true,
    skipGitRepoCheck: true,
    timeoutMs: 60_000,
    configOverrides: ['model_reasoning_effort="low"', 'model_verbosity="low"'],
    abortOnStderrPatterns: [{ pattern: /database is locked/i, reason: 'codex_state_db_locked' }],
    env: { ...process.env, CODEX_HOME: codexHome }
  });
  const parsed = parseAgentJsonResult(out.stdout);
  const ok = parsed?.codex_tool_visible === true && parsed?.promptbridge_tool_visible === true;
  return {
    ok,
    reason: parsed ? null : out.abortedReason || 'no_structured_agent_json',
    parsed,
    raw: out
  };
}

export async function runSchemaConsultationCheck({
  codexHome,
  workspaceDir = promptBridgeRepoRoot(),
  platform = process.platform,
  isWsl = false,
  windowsHome = null,
  homeDir = os.homedir(),
  getBootstrapStatusImpl = getBootstrapStatus,
  callMcpServerToolImpl = callMcpServerTool
} = {}) {
  const bootstrap = await getBootstrapStatusImpl({
    codexHome,
    mirrorCodexHome: defaultMirrorCodexHome({ homeDir }),
    platform,
    isWsl,
    windowsHome,
    homeDir,
    nodeExecutable: process.execPath
  });
  const codexServerSpec = bootstrap.managedServers?.codexConsult || bootstrap.managedServer || null;
  const required = ['problem', 'assumptions', 'options', 'recommended_option', 'risks', 'verification_plan', 'confidence'];
  if (!codexServerSpec) {
    return {
      ok: false,
      reason: 'managed_server_spec_missing',
      parsed: {
        tool_visible: false,
        consultation_ok: false,
        schema_keys_present: [],
        fallback_to_lane_a: true
      }
    };
  }

  const fixedSchemaPrompt =
    'Reply with exactly this JSON and nothing else: ' +
    '{"problem":"validate lane b","assumptions":["clean profile"],"options":["probe","smoke"],"recommended_option":"probe","risks":["tool visibility"],"verification_plan":["status","query"],"confidence":"medium"}';
  const direct = await callMcpServerToolImpl({
    command: codexServerSpec.command,
    args: codexServerSpec.args,
    env: {
      ...process.env,
      ...codexServerSpec.env,
      PROMPTBRIDGE_CODEX_HOME: bootstrap.canonicalCodexHome || codexHome,
      PROMPTBRIDGE_ORCHESTRATION_CONFIG:
        bootstrap.orchestration?.file || codexServerSpec.env?.PROMPTBRIDGE_ORCHESTRATION_CONFIG || null
    },
    cwd: workspaceDir,
    toolName: 'codex_consult',
    toolArguments: {
      prompt: fixedSchemaPrompt,
      workspaceDir,
      profile: 'consult',
      model: 'gpt-5.4',
      reasoningEffort: 'low',
      peerCount: 1,
      useCurator: false
    },
    timeoutMs: 4 * 60_000
  });

  const payload = direct.structuredContent || direct.parsedTextJson || null;
  const keys = payload ? required.filter((key) => Object.prototype.hasOwnProperty.call(payload, key)) : [];
  const toolVisible = Array.isArray(direct.toolNames) ? direct.toolNames.includes('codex_consult') : false;
  const consultationOk = direct.ok === true && required.every((key) => keys.includes(key));
  return {
    ok: consultationOk,
    reason: consultationOk ? null : direct.reason || direct.error || 'tool_call_failed',
    parsed: {
      tool_visible: toolVisible,
      consultation_ok: consultationOk,
      schema_keys_present: keys,
      fallback_to_lane_a: !consultationOk
    },
    raw: direct
  };
}

export async function probeVsCodeExtensionPreflight({
  bootstrapStatus,
  desktop,
  platform = process.platform,
  isWsl = false,
  windowsHome = null,
  homeDir = os.homedir(),
  settingsPath = null,
  extensionsRoot = null,
  detectVsCodeOriginatorCodexHomeImpl = detectVsCodeOriginatorCodexHome,
  listLiveVsCodeAppServersImpl = listLiveVsCodeAppServers
} = {}) {
  const detectedPaths = detectVsCodePaths({ platform, isWsl, windowsHome, homeDir });
  const resolvedSettingsPath = settingsPath || detectedPaths.settingsPath;
  const resolvedExtensionsRoot = extensionsRoot || detectedPaths.extensionsRoot;
  const settings = await readJsonIfPresent(resolvedSettingsPath);
  const extensionPath = await findOpenAiExtension({ extensionsRoot: resolvedExtensionsRoot });
  const canonicalCodexHome = bootstrapStatus?.canonicalCodexHome || defaultCodexHome({ homeDir });
  const legacyCodexHome =
    bootstrapStatus?.legacyCodexHome ||
    bootstrapStatus?.mirrorCodexHome ||
    defaultMirrorCodexHome({ homeDir });
  const canonicalConfigPath = path.join(canonicalCodexHome, 'config.toml');
  const canonicalConfig = await fs.readFile(canonicalConfigPath, 'utf8').catch(() => '');

  const extensionInstalled = !!extensionPath;
  const canonicalProfilePresent = !!bootstrapStatus?.canonicalProfile?.installed || !!canonicalConfig;
  const canonicalHasCodexConsult = /\[mcp_servers\.codex_consult\]/.test(canonicalConfig);
  const canonicalHasPromptbridgeTalk = canonicalHasCodexConsult;
  const legacyMigrationInputPresent = await pathExists(legacyCodexHome);
  const wslModeSetting = settings?.['chatgpt.runCodexInWindowsSubsystemForLinux'];
  const genericMcpServerConfigured = !!settings?.mcpServers?.codex_consult || !!settings?.mcpServers?.promptbridge_talk;
  const desktopReady = desktop?.ok === true;
  const originatorHome = await detectVsCodeOriginatorCodexHomeImpl();
  const liveAppServers = (await listLiveVsCodeAppServersImpl()).filter(
    (entry) => entry?.originatorOverride === 'codex_vscode'
  );
  const liveAppServerHomes = [...new Set(liveAppServers.map((entry) => entry?.codexHome).filter(Boolean))];
  const liveAppServerUsingCanonical = liveAppServerHomes.includes(canonicalCodexHome);
  const reloadRequired = liveAppServers.length > 0 && !liveAppServerUsingCanonical;
  const originatorMatchesKnownHome =
    !originatorHome?.codexHome ||
    originatorHome.codexHome === canonicalCodexHome;
  const ok =
    extensionInstalled &&
    canonicalProfilePresent &&
    canonicalHasCodexConsult &&
    canonicalHasPromptbridgeTalk &&
    desktopReady &&
    (!isWsl || wslModeSetting === true) &&
    originatorMatchesKnownHome &&
    !reloadRequired;

  return {
    ok,
    extensionInstalled,
    extensionPath,
    settingsPath: resolvedSettingsPath,
    settingsPresent: !!settings,
    wslModeSetting: typeof wslModeSetting === 'boolean' ? wslModeSetting : null,
    genericMcpServerConfigured,
    canonicalCodexHome,
    canonicalProfilePresent,
    canonicalHasCodexConsult,
    canonicalHasPromptbridgeTalk,
    legacyCodexHome,
    legacyMigrationInputPresent,
    desktopReady,
    originatorHome,
    liveAppServers,
    liveAppServerHomes,
    liveAppServerUsingCanonical,
    reloadRequired
  };
}

export async function probeVsCodeAppServerMirror({
  codexHome = defaultCodexHome(),
  workspaceDir = promptBridgeRepoRoot(),
  spawnImpl = spawn,
  timeoutMs = 30_000,
  requestTimeoutMs = 10_000
} = {}) {
  const childEnv = { ...process.env, CODEX_HOME: codexHome };
  const codexInvocation = await resolveCodexInvocation({ env: childEnv, platform: process.platform, nodeExecutable: process.execPath });
  const child = spawnImpl(codexInvocation.command, [...codexInvocation.args, 'app-server'], {
    cwd: workspaceDir,
    env: childEnv,
    shell: codexInvocation.shell || false,
    stdio: ['pipe', 'pipe', 'pipe']
  });

  let stdout = '';
  let stderr = '';
  let settled = false;
  const pending = new Map();
  const rl = readline.createInterface({ input: child.stdout });

  const clearPending = (error) => {
    for (const [id, state] of pending.entries()) {
      clearTimeout(state.timer);
      state.reject(error);
      pending.delete(id);
    }
  };

  const finish = async () => {
    if (settled) return;
    settled = true;
    try {
      child.kill('SIGTERM');
    } catch {}
    if (child.exitCode === null && child.signalCode === null) {
      await new Promise((resolve) => child.once('exit', () => resolve())).catch(() => {});
    }
    try {
      rl.close();
    } catch {}
  };

  const send = (message) => {
    child.stdin.write(`${JSON.stringify(message)}\n`);
  };

  const request = (id, method, params, ms = requestTimeoutMs) =>
    new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`${method}_timeout`));
      }, ms);
      pending.set(id, {
        resolve: (value) => {
          clearTimeout(timer);
          pending.delete(id);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timer);
          pending.delete(id);
          reject(error);
        },
        timer
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
    stdout += `${line}
`;
    let message;
    try {
      message = JSON.parse(line);
    } catch {
      return;
    }
    if (Object.prototype.hasOwnProperty.call(message, 'id') && pending.has(message.id)) {
      const state = pending.get(message.id);
      if (message.error) state.reject(new Error(message.error?.message || `${message.id}_error`));
      else state.resolve(message.result);
    }
  });

  const timer = setTimeout(() => {
    clearPending(new Error('app_server_timeout'));
    void finish();
  }, timeoutMs);

  try {
    const initialize = await request(1, 'initialize', {
      clientInfo: { name: 'promptbridge-vscode-probe', version: '0.0.0' },
      capabilities: null
    });
    send({ jsonrpc: '2.0', method: 'initialized', params: {} });

    const reload = await request(2, 'config/mcpServer/reload', undefined, requestTimeoutMs);
    const configRead = await request(
      3,
      'config/read',
      { includeLayers: true, cwd: workspaceDir },
      requestTimeoutMs
    );

    let statusList = null;
    let statusError = null;
    try {
      statusList = await request(4, 'mcpServerStatus/list', { limit: 100 }, requestTimeoutMs * 2);
    } catch (error) {
      statusError = error?.message || String(error);
    }

    const configCodexConsult = configRead?.config?.mcp_servers?.codex_consult || null;
    const configPromptbridgeTalk = !!configCodexConsult ? configCodexConsult : null;
    const statusServers = Array.isArray(statusList?.data) ? statusList.data : [];
    const statusCodexConsult = statusServers.find((entry) => entry?.name === 'codex_consult') || null;
    const codexToolNames = statusCodexConsult?.tools ? Object.keys(statusCodexConsult.tools) : [];
    const promptbridgeToolNames = codexToolNames.filter((name) => /^promptbridge_|^agentify_/.test(name));
    const statusServerNames = statusServers.map((entry) => entry?.name).filter(Boolean);
    const hasRequiredCodexTool = codexToolNames.includes('codex_consult');
    const hasRequiredPromptbridgeTool =
      promptbridgeToolNames.includes('promptbridge_status') || promptbridgeToolNames.includes('agentify_status');

    clearTimeout(timer);
    await finish();

    return {
      ok:
        !!configCodexConsult &&
        !!initialize &&
        !!reload &&
        !!statusList &&
        hasRequiredCodexTool &&
        hasRequiredPromptbridgeTool,
      codexHome,
      initialize,
      reloadOk: !!reload,
      configReadOk: !!configRead,
      configHasCodexConsult: !!configCodexConsult,
      configHasPromptbridgeTalk: !!configPromptbridgeTalk,
      statusListOk: !!statusList,
      statusListError: statusError,
      statusServerNames,
      codexToolNames,
      promptbridgeToolNames,
      stdout,
      stderr
    };
  } catch (error) {
    clearTimeout(timer);
    await finish();
    return {
      ok: false,
      codexHome,
      reason: error?.message || String(error),
      stdout,
      stderr
    };
  }
}

export async function probeConsultationStack({
  codexHome = defaultCodexHome(),
  mirrorCodexHome = defaultMirrorCodexHome(),
  workspaceDir = promptBridgeRepoRoot(),
  platform = process.platform,
  isWsl = false,
  windowsHome = null,
  homeDir = os.homedir(),
  includeVsCodePreflight = true,
  getBootstrapStatusImpl = getBootstrapStatus,
  probeDesktopConnectionImpl = probeDesktopConnection,
  probeMcpServerStartupImpl = probeMcpServerStartup,
  runToolVisibilityCheckImpl = runToolVisibilityCheck,
  runSchemaConsultationCheckImpl = runSchemaConsultationCheck,
  runPromptbridgeStatusCheckImpl = runPromptbridgeStatusCheck,
  probeVsCodeExtensionPreflightImpl = probeVsCodeExtensionPreflight,
  probeVsCodeAppServerMirrorImpl = probeVsCodeAppServerMirror
} = {}) {
  const bootstrap = await getBootstrapStatusImpl({
    codexHome,
    mirrorCodexHome,
    platform,
    isWsl,
    windowsHome,
    homeDir,
    nodeExecutable: process.execPath
  });

  if (!bootstrap.targetProfile?.installed) {
    return {
      ok: false,
      failureLayer: 'bootstrap',
      codexHome,
      workspaceDir,
      bootstrap
    };
  }

  const codexServerSpec = bootstrap.managedServers?.codexConsult || bootstrap.managedServer || null;
  if (!codexServerSpec) {
    return {
      ok: false,
      failureLayer: 'bootstrap',
      codexHome,
      workspaceDir,
      bootstrap,
      reason: 'managed_server_spec_missing'
    };
  }

  const stateDir =
    codexServerSpec.env?.PROMPTBRIDGE_DESKTOP_STATE_DIR ||
    codexServerSpec.env?.AGENTIFY_DESKTOP_STATE_DIR ||
    stateDirForBootstrap({ platform, isWsl, windowsHome, homeDir });
  const desktop = await probeDesktopConnectionImpl({ stateDir });
  if (!desktop.ok) {
    return {
      ok: false,
      failureLayer: 'desktop_state',
      codexHome,
      workspaceDir,
      bootstrap,
      desktop
    };
  }

  const codexServer = await probeMcpServerStartupImpl({
    command: codexServerSpec.command,
    args: codexServerSpec.args,
    env: { ...process.env, ...codexServerSpec.env, PROMPTBRIDGE_CODEX_HOME: bootstrap.canonicalCodexHome }
  });
  if (!codexServer.ok) {
    return {
      ok: false,
      failureLayer: codexServer.phase === 'startup' ? 'mcp_startup' : 'mcp_handshake',
      codexHome,
      workspaceDir,
      bootstrap,
      desktop,
      serverKind: 'codex_consult',
      server: codexServer
    };
  }
  const missingCodexHandshakeTools = expectedCodexToolNames().filter((name) => !codexServer.toolNames?.includes(name));
  if (missingCodexHandshakeTools.length > 0) {
    return {
      ok: false,
      failureLayer: 'mcp_handshake',
      codexHome,
      workspaceDir,
      bootstrap,
      desktop,
      serverKind: 'codex_consult',
      server: { ...codexServer, missingExpectedTools: missingCodexHandshakeTools }
    };
  }

  const missingPromptbridgeHandshakeTools = expectedPromptbridgeToolNames().filter(
    (name) => !codexServer.toolNames?.includes(name)
  );
  if (missingPromptbridgeHandshakeTools.length > 0) {
    return {
      ok: false,
      failureLayer: 'mcp_handshake',
      codexHome,
      workspaceDir,
      bootstrap,
      desktop,
      serverKind: 'codex_consult',
      server: { ...codexServer, missingExpectedTools: missingPromptbridgeHandshakeTools }
    };
  }

  const consultation = await runSchemaConsultationCheckImpl({
    codexHome,
    workspaceDir,
    platform,
    isWsl,
    windowsHome,
    homeDir,
    getBootstrapStatusImpl
  });
  const talkLane = await runPromptbridgeStatusCheckImpl({
    codexHome,
    workspaceDir,
    platform,
    isWsl,
    windowsHome,
    homeDir,
    getBootstrapStatusImpl
  });
  const visibility = synthesizeDirectVisibility({ consultation, talkLane });
  if (!visibility.ok) {
    return {
      ok: false,
      failureLayer: 'tool_visibility_cli',
      codexHome,
      workspaceDir,
      bootstrap,
      desktop,
      servers: {
        codexConsult: codexServer,
        promptbridgeTalk: codexServer
      },
      visibility,
      consultation,
      talkLane
    };
  }

  let vscodePreflight = null;
  let vscodeAppServer = null;
  if (includeVsCodePreflight) {
    vscodePreflight = await probeVsCodeExtensionPreflightImpl({
      bootstrapStatus: bootstrap,
      desktop,
      platform,
      isWsl,
      windowsHome,
      homeDir
    });
    if (!vscodePreflight.ok) {
      return {
        ok: false,
        failureLayer: 'vscode_extension_preflight',
        codexHome,
        workspaceDir,
        bootstrap,
        desktop,
        servers: {
          codexConsult: codexServer,
          promptbridgeTalk: codexServer
        },
        visibility,
        consultation,
        talkLane,
        vscodePreflight
      };
    }
    vscodeAppServer = await probeVsCodeAppServerMirrorImpl({
      codexHome: bootstrap.canonicalCodexHome || codexHome,
      workspaceDir
    });
    if (!vscodeAppServer.ok) {
      return {
        ok: false,
        failureLayer: 'vscode_extension_surface',
        codexHome,
        workspaceDir,
        bootstrap,
        desktop,
        servers: {
          codexConsult: codexServer,
          promptbridgeTalk: codexServer
        },
        visibility,
        consultation,
        talkLane,
        vscodePreflight,
        vscodeAppServer
      };
    }
  }

  return {
    ok: true,
    failureLayer: null,
    codexHome,
    workspaceDir,
    bootstrap,
    desktop,
    servers: {
      codexConsult: codexServer,
      promptbridgeTalk: codexServer
    },
    visibility,
    consultation,
    talkLane,
    vscodePreflight,
    vscodeAppServer,
    exportedToolNames: [...new Set([...(codexServer.toolNames || [])])]
  };
}
export async function runConsultationSelfTest({
  primaryCodexHome = defaultCodexHome(),
  alternateCodexHome = null,
  workspaceDir = promptBridgeRepoRoot(),
  platform = process.platform,
  isWsl = false,
  windowsHome = null,
  homeDir = os.homedir(),
  runToolVisibilityCheckImpl = runToolVisibilityCheck,
  runSchemaConsultationCheckImpl = runSchemaConsultationCheck,
  runPromptbridgeStatusCheckImpl = runPromptbridgeStatusCheck,
  getBootstrapStatusImpl = getBootstrapStatus,
  probeVsCodeExtensionPreflightImpl = probeVsCodeExtensionPreflight,
  probeVsCodeAppServerMirrorImpl = probeVsCodeAppServerMirror
} = {}) {
  const activeProfile = {
    visibility: await runToolVisibilityCheckImpl({ codexHome: primaryCodexHome, workspaceDir }),
    talkLane: await runPromptbridgeStatusCheckImpl({ codexHome: primaryCodexHome, workspaceDir, platform, isWsl, windowsHome, homeDir }),
    consultation: await runSchemaConsultationCheckImpl({ codexHome: primaryCodexHome, workspaceDir, platform, isWsl, windowsHome, homeDir })
  };

  const customProfile = alternateCodexHome
    ? {
        visibility: await runToolVisibilityCheckImpl({ codexHome: alternateCodexHome, workspaceDir }),
        talkLane: await runPromptbridgeStatusCheckImpl({ codexHome: alternateCodexHome, workspaceDir, platform, isWsl, windowsHome, homeDir }),
        consultation: await runSchemaConsultationCheckImpl({ codexHome: alternateCodexHome, workspaceDir, platform, isWsl, windowsHome, homeDir })
      }
    : null;

  const bootstrap = await getBootstrapStatusImpl({
    codexHome: primaryCodexHome,
    mirrorCodexHome: defaultMirrorCodexHome({ homeDir }),
    platform,
    isWsl,
    windowsHome,
    homeDir,
    nodeExecutable: process.execPath
  });
  const vscode = {
    preflight: await probeVsCodeExtensionPreflightImpl({
      bootstrapStatus: bootstrap,
      desktop: { ok: activeProfile.talkLane.ok },
      platform,
      isWsl,
      windowsHome,
      homeDir
    }),
    appServer: await probeVsCodeAppServerMirrorImpl({
      codexHome: bootstrap.canonicalCodexHome || primaryCodexHome,
      workspaceDir
    }),
    guidedSmoke: {
      required: true,
      prompt:
        'If codex_consult and promptbridge_ensure_ready or agentify_ensure_ready and promptbridge_status or agentify_status are available in this session, call ensure_ready with key="promptbridge-probe" and then call the matching status tool with key="promptbridge-probe". If not, say exactly which codex_* and promptbridge_* or agentify_* tools you can see.',
      expectedTools: ['codex_consult', 'promptbridge_ensure_ready', 'agentify_ensure_ready', 'promptbridge_status', 'agentify_status'],
      successCriteria: 'A fresh OpenAI Codex VS Code chat can see codex_consult, prepare a dedicated PromptBridge session, and call one of the PromptBridge status tools.'
    }
  };

  const activeProfileOk = activeProfile.visibility.ok && activeProfile.talkLane.ok && activeProfile.consultation.ok;
  const customProfileOk = !customProfile || (customProfile.visibility.ok && customProfile.talkLane.ok && customProfile.consultation.ok);
  const provenSurfaces = [];
  const configuredSurfaces = [];
  if (activeProfileOk) provenSurfaces.push('codex_cli_active_windows_profile');
  if (customProfile && customProfileOk) provenSurfaces.push('codex_cli_custom_windows_profile');
  if (vscode.preflight.ok && vscode.appServer.ok) configuredSurfaces.push('openai_vscode_extension_shared_profile_fresh_chat_required');

  return {
    ok: activeProfileOk && customProfileOk && vscode.preflight.ok && vscode.appServer.ok,
    activeProfile,
    customProfile,
    vscode,
    summary: {
      provenSurfaces,
      configuredSurfaces,
      manualSmokeRequired: true,
      fallbackExpected: !activeProfileOk || !customProfileOk || !vscode.preflight.ok || !vscode.appServer.ok
    }
  };
}
