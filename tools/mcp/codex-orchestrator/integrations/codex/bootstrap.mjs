import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';
import { spawn, execFile as execFileCb } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import { defaultOrchestrationConfig, renderOrchestrationConfig } from '../../src/codex-orchestration.mjs';

const execFile = promisify(execFileCb);

const MANAGED_BLOCK_START = '# >>> promptbridge-codex managed >>>';
const MANAGED_BLOCK_END = '# <<< promptbridge-codex managed <<<';
const MANAGED_FILE_HEADER = '<!-- promptbridge-managed -->';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export function defaultCodexHome({ env = process.env, homeDir = os.homedir() } = {}) {
  const fromEnv = String(env.CODEX_HOME || '').trim();
  if (fromEnv) return fromEnv;
  const winHome = String(env.USERPROFILE || '').trim();
  return path.join(winHome || homeDir, '.codex');
}

export function defaultMirrorCodexHome({ homeDir = os.homedir() } = {}) {
  return path.join(homeDir, '.codex-vscode');
}

export function resolveManagedCodexHomes({
  codexHome,
  env = process.env,
  homeDir = os.homedir(),
  mirrorCodexHome = null
} = {}) {
  const canonicalCodexHome = path.resolve(defaultCodexHome({ env: { ...env, CODEX_HOME: '' }, homeDir }));
  const derivedLegacyCodexHome = path.resolve(mirrorCodexHome || defaultMirrorCodexHome({ homeDir }));
  const requestedCodexHome = path.resolve(codexHome || canonicalCodexHome);

  let role = 'custom';
  if (requestedCodexHome === canonicalCodexHome) role = 'canonical';
  else if (requestedCodexHome === derivedLegacyCodexHome) role = 'legacy';

  return {
    requestedCodexHome,
    canonicalCodexHome,
    legacyCodexHome: derivedLegacyCodexHome,
    mirrorCodexHome: derivedLegacyCodexHome,
    role,
    managesMirror: false
  };
}

export function detectBootstrapEnvironment({ platform = process.platform, env = process.env, homeDir = os.homedir() } = {}) {
  const isWsl = platform === 'linux' && !!(env.WSL_DISTRO_NAME || env.WSL_INTEROP);
  const codexHome = defaultCodexHome({ env, homeDir });
  const legacyCodexHome = defaultMirrorCodexHome({ homeDir });
  return {
    platform,
    isWsl,
    homeDir,
    codexHome,
    canonicalCodexHome: codexHome,
    legacyCodexHome,
    mirrorCodexHome: legacyCodexHome,
    windowsHome: String(env.USERPROFILE || '').trim() || null
  };
}

async function convertWindowsPathToWsl(raw, { execFileImpl = execFile } = {}) {
  const text = String(raw || '').trim();
  if (!text) return null;
  if (text.startsWith('/')) return text;
  try {
    const converted = await execFileImpl('wslpath', ['-u', text], { timeout: 5000 });
    return String(converted.stdout || '').trim() || text;
  } catch {
    return text;
  }
}

export async function detectWindowsHomeForWsl({ env = process.env, execFileImpl = execFile } = {}) {
  const fromEnv = String(env.USERPROFILE || '').trim();
  if (fromEnv) return await convertWindowsPathToWsl(fromEnv, { execFileImpl });

  try {
    const ps = await execFileImpl('powershell.exe', ['-NoProfile', '-Command', "[Environment]::GetFolderPath('UserProfile')"], {
      timeout: 5000
    });
    return await convertWindowsPathToWsl(String(ps.stdout || '').trim(), { execFileImpl });
  } catch {
    return null;
  }
}

export async function resolveWindowsHome({
  platform = process.platform,
  isWsl = false,
  windowsHome = null,
  env = process.env,
  execFileImpl = execFile
} = {}) {
  const provided = String(windowsHome || '').trim();
  if (!isWsl) return provided || String(env.USERPROFILE || '').trim() || null;
  if (provided) return await convertWindowsPathToWsl(provided, { execFileImpl });
  return await detectWindowsHomeForWsl({ env, execFileImpl });
}

export function promptBridgeRepoRoot() {
  return path.resolve(__dirname, '..', '..', '..', '..', '..');
}

export function managedRuntimeRoot({ canonicalCodexHome } = {}) {
  return path.join(canonicalCodexHome, 'promptbridge-runtime');
}

export function managedSqliteHome({ canonicalCodexHome, codexHome } = {}) {
  const canonical = path.resolve(String(canonicalCodexHome || ''));
  const requested = path.resolve(String(codexHome || canonicalCodexHome || ''));
  const baseName = path.basename(requested);
  const role = requested === canonical ? 'canonical' : (baseName === '.codex-vscode' ? 'legacy' : 'custom');
  return path.join(canonical, 'codex-sqlite', role);
}

function normalizeLineEndings(text) {
  return String(text || '').replace(/\r\n/g, '\n');
}

async function pathExists(file) {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

function timestampForBackup() {
  return new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
}

async function readFileIfPresent(file) {
  try {
    return normalizeLineEndings(await fs.readFile(file, 'utf8'));
  } catch {
    return '';
  }
}

async function backupFileIfPresent(file) {
  if (!(await pathExists(file))) return null;
  const backupPath = `${file}.bak.${timestampForBackup()}`;
  await fs.copyFile(file, backupPath);
  return backupPath;
}

async function backupDirectoryIfPresent(dir) {
  if (!(await pathExists(dir))) return null;
  const backupPath = `${dir}.bak.${timestampForBackup()}`;
  await fs.cp(dir, backupPath, { recursive: true });
  return backupPath;
}

async function readBufferIfPresent(file) {
  try {
    return await fs.readFile(file);
  } catch {
    return null;
  }
}

async function listRelativeFiles(root, current = root) {
  const entries = await fs.readdir(current, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(current, entry.name);
    if (entry.isDirectory()) {
      files.push(...await listRelativeFiles(root, fullPath));
    } else if (entry.isFile()) {
      files.push(path.relative(root, fullPath));
    }
  }
  return files.sort();
}

async function skillDirectoryDiffers(sourceRoot, targetRoot) {
  const sourceFiles = await listRelativeFiles(sourceRoot);
  if (await pathExists(targetRoot)) {
    const targetFiles = await listRelativeFiles(targetRoot);
    if (targetFiles.some((relativePath) => !sourceFiles.includes(relativePath))) {
      return true;
    }
  }
  for (const relativePath of sourceFiles) {
    const sourceBuffer = await fs.readFile(path.join(sourceRoot, relativePath));
    const targetBuffer = await readBufferIfPresent(path.join(targetRoot, relativePath));
    if (!targetBuffer || !sourceBuffer.equals(targetBuffer)) {
      return true;
    }
  }
  return false;
}

async function copyManagedSkillDirectory(sourceRoot, targetRoot) {
  const backup = await backupDirectoryIfPresent(targetRoot);
  await fs.rm(targetRoot, { recursive: true, force: true });
  await fs.mkdir(path.dirname(targetRoot), { recursive: true });
  await fs.cp(sourceRoot, targetRoot, { recursive: true });
  return backup ? [backup] : [];
}

function replaceRootSetting(config, key, value) {
  const line = `${key} = ${JSON.stringify(value)}`;
  const pattern = new RegExp(`^${key}\\s*=.*$`, 'm');  // nosemgrep: javascript.lang.security.audit.detect-non-literal-regexp.detect-non-literal-regexp -- regex built from internal/controlled patterns, not untrusted input
  if (pattern.test(config)) return config.replace(pattern, line);
  const trimmed = config.trim();
  return trimmed ? `${line}\n${trimmed}\n` : `${line}\n`;
}

function ensureFeaturesSetting(config, key, value) {
  const rendered = `${key} = ${value ? 'true' : 'false'}`;
  if (/\[features\]/.test(config)) {
    const sectionPattern = /(\[features\][\s\S]*?)(\n\[|$)/;
    return config.replace(sectionPattern, (match, section, tail) => {
      if (new RegExp(`^${key}\\s*=.*$`, 'm').test(section)) {  // nosemgrep: javascript.lang.security.audit.detect-non-literal-regexp.detect-non-literal-regexp -- regex built from internal/controlled patterns, not untrusted input
        return `${section.replace(new RegExp(`^${key}\\s*=.*$`, 'm'), rendered)}${tail}`;  // nosemgrep: javascript.lang.security.audit.detect-non-literal-regexp.detect-non-literal-regexp -- regex built from internal/controlled patterns, not untrusted input
      }
      const suffix = section.endsWith('\n') ? '' : '\n';
      return `${section}${suffix}${rendered}\n${tail}`;
    });
  }
  const trimmed = config.trimEnd();
  const prefix = trimmed ? `${trimmed}\n\n` : '';
  return `${prefix}[features]\n${rendered}\n`;
}

function stripManagedBlock(config) {
  const pattern = new RegExp(`\\n?${MANAGED_BLOCK_START}[\\s\\S]*?${MANAGED_BLOCK_END}\\n?`, 'g');
  return config.replace(pattern, '\n').replace(/\n{3,}/g, '\n\n').trimEnd() + '\n';
}

function stripMcpConsultSections(config) {
  const patterns = [
    /\n?\[mcp_servers\.codex_consult\][\s\S]*?(?=\n\[|$)/g,
    /\n?\[mcp_servers\.codex_consult\.env\][\s\S]*?(?=\n\[|$)/g,
    /\n?\[mcp_servers\.promptbridge_talk\][\s\S]*?(?=\n\[|$)/g,
    /\n?\[mcp_servers\.promptbridge_talk\.env\][\s\S]*?(?=\n\[|$)/g
  ];
  let out = config;
  for (const pattern of patterns) out = out.replace(pattern, '\n');
  return out.replace(/\n{3,}/g, '\n\n').trimEnd() + '\n';
}

function extractManagedBlock(config) {
  const start = config.indexOf(MANAGED_BLOCK_START);
  const end = config.indexOf(MANAGED_BLOCK_END);
  if (start === -1 || end === -1 || end < start) return '';
  return config.slice(start, end + MANAGED_BLOCK_END.length).trim();
}

export function stateDirForBootstrap({ platform, isWsl = false, windowsHome = null, homeDir = os.homedir() }) {
  if (isWsl && windowsHome) return path.posix.join(windowsHome, '.promptbridge-desktop');
  if (platform === 'win32') {
    const base = windowsHome || process.env.USERPROFILE || homeDir;
    return path.win32.join(base, '.promptbridge-desktop');
  }
  return path.join(homeDir, '.promptbridge-desktop');
}

export function managedMcpServerSpec({
  stateDir,
  nodeExecutable = process.execPath,
  repoRoot = promptBridgeRepoRoot(),
  runtimeRoot = null,
  canonicalCodexHome = null
} = {}) {
  const entryRoot = runtimeRoot || (canonicalCodexHome ? managedRuntimeRoot({ canonicalCodexHome }) : repoRoot);
  return {
    command: nodeExecutable || 'node',
    args: [path.join(entryRoot, 'mcp-server.mjs')],
    startupTimeoutSec: 45.0,
    toolTimeoutSec: 300.0,
    enabled: true,
    env: {
      PROMPTBRIDGE_DESKTOP_STATE_DIR: stateDir,
      AGENTIFY_DESKTOP_STATE_DIR: stateDir,
      PROMPTBRIDGE_CODEX_HOME: canonicalCodexHome,
      PROMPTBRIDGE_ORCHESTRATION_CONFIG: canonicalCodexHome ? path.join(canonicalCodexHome, 'promptbridge-orchestration.toml') : undefined
    }
  };
}

export function managedPromptbridgeTalkServerSpec({
  stateDir,
  nodeExecutable = process.execPath,
  repoRoot = promptBridgeRepoRoot(),
  runtimeRoot = null,
  canonicalCodexHome = null
} = {}) {
  return managedMcpServerSpec({ stateDir, nodeExecutable, repoRoot, runtimeRoot, canonicalCodexHome });
}

function renderManagedConfigBlock({ stateDir, nodeExecutable, repoRoot, runtimeRoot, canonicalCodexHome }) {
  const codexSpec = managedMcpServerSpec({ stateDir, nodeExecutable, repoRoot, runtimeRoot, canonicalCodexHome });
  return [
    MANAGED_BLOCK_START,
    '[mcp_servers.codex_consult]',
    `command = ${JSON.stringify(codexSpec.command)}`,
    `args = ${JSON.stringify(codexSpec.args)}`,
    `startup_timeout_sec = ${codexSpec.startupTimeoutSec.toFixed(1)}`,
    `tool_timeout_sec = ${codexSpec.toolTimeoutSec.toFixed(1)}`,
    `enabled = ${codexSpec.enabled ? 'true' : 'false'}`,
    '',
    '[mcp_servers.codex_consult.env]',
    `PROMPTBRIDGE_DESKTOP_STATE_DIR = ${JSON.stringify(codexSpec.env.PROMPTBRIDGE_DESKTOP_STATE_DIR)}`,
    '# Legacy compatibility for older builds/scripts.',
    `AGENTIFY_DESKTOP_STATE_DIR = ${JSON.stringify(codexSpec.env.AGENTIFY_DESKTOP_STATE_DIR)}`,
    `PROMPTBRIDGE_CODEX_HOME = ${JSON.stringify(codexSpec.env.PROMPTBRIDGE_CODEX_HOME)}`,
    `PROMPTBRIDGE_ORCHESTRATION_CONFIG = ${JSON.stringify(codexSpec.env.PROMPTBRIDGE_ORCHESTRATION_CONFIG)}`,
    MANAGED_BLOCK_END
  ].join('\n');
}

function renderAgentsMd({ canonicalCodexHome, mirrorCodexHome }) {
  return [
    MANAGED_FILE_HEADER,
    '# PromptBridge Codex Consultation Contract',
    '',
    '## Profile ownership',
    `- Canonical managed profile: ${canonicalCodexHome}`,
    `- Legacy migration input only: ${mirrorCodexHome}`,
    `- Treat ${canonicalCodexHome} as the only editable source of truth. ${mirrorCodexHome} is read only for migration or comparison and is not an active second home.`,
    '',
    '## Lane A (default)',
    '- Use native Codex workflow for implementation.',
    '- For complex work, draft the plan first, then choose an execution path: subagent-driven execution (recommended) or inline execution.',
    '- Suggested flow: Draft -> Review (gpt-5.4) -> Reconcile -> Choose execution path -> Execute -> Verify.',
    '',
    '## Lane B (policy-driven sidecar)',
    '- codex_consult is the single managed MCP lane.',
    '- codex_* execution tools and promptbridge_* / agentify_* talk tools are exposed from that same managed server.',
    '- Use codex_consult automatically for:',
    '  - ambiguous requirement',
    '  - security-sensitive change',
    '  - repeated test failure loop',
    '  - architecture tradeoff decision',
    '',
    '## Lane B operating model',
    '- Prefer codex_* tools for orchestration and promptbridge_* / agentify_* tools for talk-only discussion/curation.',
    '- Keep agentify_* aliases for compatibility during 0.1.x.',
    '- Ensure a ready desktop session before submitting consultation context:',
    '  - promptbridge_ensure_ready / agentify_ensure_ready',
    '  - promptbridge_status / agentify_status',
    '  - codex_consult / codex_brainstorm / codex_review / codex_discuss / codex_coordinate / codex_curate',
    '',
    '## Required consultation output schema',
    'Every consultation result must include:',
    '- problem',
    '- assumptions',
    '- options',
    '- recommended_option',
    '- risks',
    '- verification_plan',
    '- confidence',
    '',
    '## Redaction policy',
    '- Never send secrets, tokens, passwords, API keys, customer identifiers, or private credentials to sidecar tools.',
    '- Sanitize context before sidecar submission.',
    '',
    '## Fallback behavior',
    '- If Lane B is unavailable or unauthenticated, continue in Lane A.',
    '- Mark fallback explicitly in output/logs (fallback_to_lane_a = true).',
    '',
    '## Support contract',
    '- Supported: Codex CLI from the active Windows CODEX_HOME and from any explicitly provided custom CODEX_HOME.',
    '- Guided / proof-required: OpenAI Codex VS Code extension through the shared canonical profile.',
    '- Optional / best-effort only: generic VS Code mcpServers chat integrations.',
    ''
  ].join('\n');
}

function renderWorkflowMd({ canonicalCodexHome, mirrorCodexHome }) {
  return [
    MANAGED_FILE_HEADER,
    '# PromptBridge Desktop Codex Workflow',
    '',
    '## Active profiles',
    `- Canonical managed profile: ${canonicalCodexHome}`,
    `- Legacy migration input only: ${mirrorCodexHome}`,
    '',
    '## Supported paths',
    '- Start PromptBridge Desktop and keep it signed in to ChatGPT.',
    '- Codex CLI is supported from the active Windows CODEX_HOME and from explicitly supplied custom CODEX_HOME values.',
    '- The OpenAI Codex VS Code extension is a configured target through the shared canonical profile and still requires a fresh-chat smoke proof.',
    '- Generic VS Code mcpServers integrations are optional / best-effort and are not the primary proof path.',
    '',
    '## Lane B flow',
    '1. Ensure PromptBridge Desktop is ready and authenticated.',
    '2. Reuse or create a stable dedicated tab for the current workspace or task.',
    '3. After the plan is written, choose the execution path: subagent-driven execution (recommended) or inline execution.',
    '4. Execute the plan and normalize the result into:',
    '   - problem',
    '   - assumptions',
    '   - options',
    '   - recommended_option',
    '   - risks',
    '   - verification_plan',
    '   - confidence',
    '',
    '## Verification contract',
    '- CLI proof requires in-session visibility of codex_consult plus one of promptbridge_status / agentify_status.',
    '- VS Code proof requires canonical-profile extension preflight plus a fresh Codex chat that can surface codex_consult and one of the PromptBridge status tools.',
    '- If PromptBridge tools are not visible in-session, continue in Lane A and emit fallback_to_lane_a = true.',
    '',
    '## Required reset after profile-affecting changes',
    'After any of these changes:',
    '- bootstrap install/update',
    '- canonical profile regeneration',
    '- canonical SQLite reset',
    '- codex_consult path/env change',
    '',
    'You must:',
    '1. reload the VS Code window / OpenAI Codex extension host',
    '2. start a fresh Codex chat thread',
    '3. run a sidecar status smoke prompt before claiming Lane B is live in-session',
    ''
  ].join('\n');
}function renderManagedArtifacts({
  canonicalCodexHome,
  mirrorCodexHome,
  stateDir,
  nodeExecutable,
  repoRoot,
  runtimeRoot
} = {}) {
  return {
    configBlock: renderManagedConfigBlock({ stateDir, nodeExecutable, repoRoot, runtimeRoot, canonicalCodexHome }),
    agents: renderAgentsMd({ canonicalCodexHome, mirrorCodexHome }),
    workflow: renderWorkflowMd({ canonicalCodexHome, mirrorCodexHome })
  };
}

function runtimeExclude(relPath) {
  if (!relPath || relPath === '.') return false;
  return relPath.split(path.sep).some((part) => {
    if (!part) return false;
    return (
      part === '.git' ||
      part === 'node_modules' ||
      part === 'dist' ||
      part === 'dist-live' ||
      part === '.serena' ||
      part.startsWith('node_modules.') ||
      part.startsWith('dist.')
    );
  });
}

async function removeIfExists(target) {
  await fs.rm(target, { recursive: true, force: true }).catch(() => {});
}

async function npmInvocationForNode({ nodeExecutable = process.execPath, platform = process.platform } = {}) {
  if (platform === 'win32') {
    const npmCli = path.join(path.dirname(nodeExecutable), 'node_modules', 'npm', 'bin', 'npm-cli.js');
    if (await pathExists(npmCli)) {
      return { command: nodeExecutable, args: [npmCli] };
    }
    const sibling = path.join(path.dirname(nodeExecutable), 'npm.cmd');
    return { command: 'cmd.exe', args: ['/d', '/s', '/c', `"${sibling}"`] };
  }
  const sibling = path.join(path.dirname(nodeExecutable), 'npm');
  return { command: sibling, args: [] };
}

async function runCommand({ command, args = [], cwd, env = process.env, timeoutMs = 10 * 60_000 } = {}) {
  return await new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    let settled = false;
    const child = spawn(command, args, { cwd, env, stdio: ['ignore', 'pipe', 'pipe'] });  // nosemgrep: javascript.lang.security.detect-child-process.detect-child-process -- developer tooling that legitimately spawns child processes
    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ stdout, stderr, ...result });
    };
    const timer = setTimeout(() => {
      try {
        child.kill('SIGTERM');
      } catch {}
      finish({ ok: false, reason: 'timeout' });
    }, timeoutMs);

    child.stdout.on('data', (buf) => {
      stdout += String(buf || '');
    });
    child.stderr.on('data', (buf) => {
      stderr += String(buf || '');
    });
    child.on('error', (error) => {
      finish({ ok: false, reason: 'spawn_error', error: error?.message || String(error) });
    });
    child.on('exit', (code, signal) => {
      finish({ ok: code === 0, code, signal });
    });
  });
}

export async function syncManagedRuntime({
  canonicalCodexHome,
  repoRoot = promptBridgeRepoRoot(),
  nodeExecutable = process.execPath,
  platform = process.platform,
  dryRun = false
} = {}) {
  const runtimeRoot = managedRuntimeRoot({ canonicalCodexHome });
  const runtimeStatus = {
    runtimeRoot,
    entrypoint: path.join(runtimeRoot, 'mcp-server.mjs'),
    packageJson: path.join(runtimeRoot, 'package.json'),
    packageLock: path.join(runtimeRoot, 'package-lock.json'),
    nodeModules: path.join(runtimeRoot, 'node_modules')
  };

  if (dryRun) {
    return {
      changed: true,
      ok: true,
      dryRun: true,
      ...runtimeStatus
    };
  }

  const stagingRoot = `${runtimeRoot}.tmp-${Date.now()}`;
  await removeIfExists(stagingRoot);
  await fs.mkdir(stagingRoot, { recursive: true });
  await fs.cp(repoRoot, stagingRoot, {
    recursive: true,
    filter: (src) => {
      const rel = path.relative(repoRoot, src) || '.';
      return !runtimeExclude(rel);
    }
  });

  const npmInvocation = await npmInvocationForNode({ nodeExecutable, platform });
  const npmArgs = [...npmInvocation.args, 'ci', '--ignore-scripts'];
  const npmResult = await runCommand({
    command: npmInvocation.command,
    args: npmArgs,
    cwd: stagingRoot,
    timeoutMs: 15 * 60_000
  });
  if (!npmResult.ok) {
    await removeIfExists(stagingRoot);
    throw new Error(`runtime_sync_failed:${npmResult.reason || npmResult.code || 'npm_ci_failed'}\n${npmResult.stderr || npmResult.stdout}`);
  }

  await removeIfExists(runtimeRoot);
  await fs.rename(stagingRoot, runtimeRoot);

  return {
    changed: true,
    ok: true,
    ...runtimeStatus,
    install: {
      command: npmInvocation.command,
      args: npmArgs,
      stdout: npmResult.stdout,
      stderr: npmResult.stderr
    }
  };
}

function configMatchesManagedContract(config, { configBlock, sqliteHome }) {
  const normalized = normalizeLineEndings(config);
  return (
    extractManagedBlock(normalized) === configBlock.trim() &&
    new RegExp(`^sqlite_home\\s*=\\s*${JSON.stringify(sqliteHome).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`, 'm').test(normalized) &&  // nosemgrep: javascript.lang.security.audit.detect-non-literal-regexp.detect-non-literal-regexp -- regex built from internal/controlled patterns, not untrusted input
    /^review_model = "gpt-5\.4"$/m.test(normalized) &&
    /^suppress_unstable_features_warning = true$/m.test(normalized) &&
    /\[features\][\s\S]*^memories = true$/m.test(normalized)
  );
}

function renderManagedOrchestrationFile({ codexHome } = {}) {
  const rendered = renderOrchestrationConfig(defaultOrchestrationConfig({ codexHome }));
  return `# promptbridge-managed\n${rendered}`;
}

async function syncManagedSkills({ codexHome, repoRoot = promptBridgeRepoRoot(), dryRun = false } = {}) {
  const sourceSkillsRoot = (await pathExists(path.join(repoRoot, '.agents', 'skills')))
    ? path.join(repoRoot, '.agents', 'skills')
    : path.join(repoRoot, 'skills');
  const skillsRoot = path.join(codexHome, '.agents', 'skills');
  const backups = [];
  let changed = false;
  let installedSkills = [];

  let sourceEntries = [];
  try {
    sourceEntries = await fs.readdir(sourceSkillsRoot, { withFileTypes: true });
  } catch {
    return { changed: false, backups, skillsRoot, installedSkills };
  }

  for (const entry of sourceEntries) {
    if (!entry.isDirectory()) continue;
    const sourceSkillDir = path.join(sourceSkillsRoot, entry.name);
    if (!(await pathExists(path.join(sourceSkillDir, 'SKILL.md')))) continue;
    installedSkills.push(entry.name);
    const skillDir = path.join(skillsRoot, entry.name);
    const skillChanged = await skillDirectoryDiffers(sourceSkillDir, skillDir);
    if (skillChanged) changed = true;
    if (dryRun) continue;
    if (skillChanged) {
      backups.push(...await copyManagedSkillDirectory(sourceSkillDir, skillDir));
    }
  }

  return { changed, backups, skillsRoot, installedSkills };
}
async function writeManagedFile(file, contents, { dryRun = false } = {}) {
  if (dryRun) return { changed: true, backups: [] };
  const backups = [];
  const existing = await readFileIfPresent(file);
  if (existing) {
    const backup = await backupFileIfPresent(file);
    if (backup) backups.push(backup);
  }
  await fs.writeFile(file, contents, 'utf8');
  return { changed: existing !== contents, backups };
}

async function applyBootstrapToHome({
  codexHome,
  mode = 'install',
  canonicalCodexHome,
  mirrorCodexHome,
  platform,
  isWsl,
  windowsHome,
  homeDir,
  nodeExecutable,
  repoRoot,
  runtimeRoot
} = {}) {
  await fs.mkdir(codexHome, { recursive: true });
  const dryRun = mode === 'dry-run';
  const files = {
    configPath: path.join(codexHome, 'config.toml'),
    agentsPath: path.join(codexHome, 'AGENTS.md'),
    workflowPath: path.join(codexHome, 'CONSULTATION_WORKFLOW.md'),
    orchestrationPath: path.join(codexHome, 'promptbridge-orchestration.toml'),
    skillsRoot: path.join(codexHome, '.agents', 'skills')
  };
  const stateDir = stateDirForBootstrap({ platform, isWsl, windowsHome, homeDir });
  const sqliteHome = managedSqliteHome({ canonicalCodexHome, codexHome });
  const rendered = renderManagedArtifacts({ canonicalCodexHome, mirrorCodexHome, stateDir, nodeExecutable, repoRoot, runtimeRoot });
  const orchestrationContents = renderManagedOrchestrationFile({ codexHome });

  let config = await readFileIfPresent(files.configPath);
  config = replaceRootSetting(config, 'model', 'gpt-5.4');
  config = replaceRootSetting(config, 'review_model', 'gpt-5.4');
  config = replaceRootSetting(config, 'sqlite_home', sqliteHome);
  config = replaceRootSetting(config, 'suppress_unstable_features_warning', true);
  config = ensureFeaturesSetting(config, 'memories', true);
  config = stripMcpConsultSections(stripManagedBlock(config)).trimEnd();
  config = `${config}\n\n${rendered.configBlock}\n`.replace(/^\n+/, '');

  const currentConfig = await readFileIfPresent(files.configPath);
  const currentAgents = await readFileIfPresent(files.agentsPath);
  const currentWorkflow = await readFileIfPresent(files.workflowPath);
  const currentOrchestration = await readFileIfPresent(files.orchestrationPath);
  const skillPreview = await syncManagedSkills({ codexHome, repoRoot, dryRun: true });
  const changes = {
    config: currentConfig !== config,
    agents: currentAgents !== rendered.agents,
    workflow: currentWorkflow !== rendered.workflow,
    orchestration: currentOrchestration !== orchestrationContents,
    skills: skillPreview.changed
  };

  if (dryRun) {
    return {
      codexHome,
      changed: Object.values(changes).some(Boolean),
      files,
      changes,
      stateDir,
      sqliteHome,
      orchestrationFile: files.orchestrationPath,
      installedSkills: skillPreview.installedSkills
    };
  }

  await fs.mkdir(sqliteHome, { recursive: true });

  const backups = [];
  if (changes.config) {
    const backup = await backupFileIfPresent(files.configPath);
    if (backup) backups.push(backup);
    await fs.writeFile(files.configPath, config, 'utf8');
  }
  const agentsWrite = await writeManagedFile(files.agentsPath, rendered.agents);
  const workflowWrite = await writeManagedFile(files.workflowPath, rendered.workflow);
  const orchestrationWrite = await writeManagedFile(files.orchestrationPath, orchestrationContents);
  const skillsWrite = await syncManagedSkills({ codexHome, repoRoot, dryRun: false });
  backups.push(...agentsWrite.backups, ...workflowWrite.backups, ...orchestrationWrite.backups, ...skillsWrite.backups);

  return {
    codexHome,
    changed: Object.values(changes).some(Boolean),
    files,
    changes,
    backups,
    stateDir,
    sqliteHome,
    orchestrationFile: files.orchestrationPath,
    installedSkills: skillsWrite.installedSkills
  };
}

async function removeBootstrapFromHome({ codexHome } = {}) {
  const files = {
    configPath: path.join(codexHome, 'config.toml'),
    agentsPath: path.join(codexHome, 'AGENTS.md'),
    workflowPath: path.join(codexHome, 'CONSULTATION_WORKFLOW.md'),
    orchestrationPath: path.join(codexHome, 'promptbridge-orchestration.toml')
  };

  let changed = false;
  if (await pathExists(files.configPath)) {
    const current = await readFileIfPresent(files.configPath);
    const next = stripMcpConsultSections(stripManagedBlock(current)).trim();
    const rendered = next ? `${next}\n` : '';
    if (rendered !== current) {
      await backupFileIfPresent(files.configPath);
      await fs.writeFile(files.configPath, rendered, 'utf8');
      changed = true;
    }
  }

  for (const file of [files.agentsPath, files.workflowPath, path.join(codexHome, 'promptbridge-orchestration.toml')]) {
    if (!(await pathExists(file))) continue;
    const current = await readFileIfPresent(file);
    if (file.endsWith('.toml')) {
      if (!current.startsWith('# promptbridge-managed')) continue;
    } else if (!current.startsWith(MANAGED_FILE_HEADER)) continue;
    await backupFileIfPresent(file);
    await fs.rm(file, { force: true });
    changed = true;
  }

  for (const skillsRoot of [path.join(codexHome, '.agents', 'skills'), path.join(codexHome, 'skills')]) {
    let sourceEntries = [];
    try {
      sourceEntries = await fs.readdir(skillsRoot, { withFileTypes: true });
    } catch {
      sourceEntries = [];
    }
    for (const entry of sourceEntries) {
      if (!entry.isDirectory()) continue;
      const skillPath = path.join(skillsRoot, entry.name, 'SKILL.md');
      const current = await readFileIfPresent(skillPath);
      if (!current.startsWith('---')) continue;
      await backupFileIfPresent(skillPath);
      await fs.rm(path.dirname(skillPath), { recursive: true, force: true });
      changed = true;
    }
  }

  return { codexHome, changed, files };
}


async function getProfileStatus({
  codexHome,
  canonicalCodexHome,
  mirrorCodexHome,
  platform,
  isWsl,
  windowsHome,
  homeDir,
  nodeExecutable,
  repoRoot,
  runtimeRoot
} = {}) {
  const files = {
    configPath: path.join(codexHome, 'config.toml'),
    agentsPath: path.join(codexHome, 'AGENTS.md'),
    workflowPath: path.join(codexHome, 'CONSULTATION_WORKFLOW.md'),
    orchestrationPath: path.join(codexHome, 'promptbridge-orchestration.toml')
  };
  const config = await readFileIfPresent(files.configPath);
  const agents = await readFileIfPresent(files.agentsPath);
  const workflow = await readFileIfPresent(files.workflowPath);
  const orchestration = await readFileIfPresent(files.orchestrationPath);
  const presentFiles = {
    config: await pathExists(files.configPath),
    agents: await pathExists(files.agentsPath),
    workflow: await pathExists(files.workflowPath),
    orchestration: await pathExists(files.orchestrationPath)
  };
  const stateDir = stateDirForBootstrap({ platform, isWsl, windowsHome, homeDir });
  const sqliteHome = managedSqliteHome({ canonicalCodexHome, codexHome });
  const rendered = renderManagedArtifacts({ canonicalCodexHome, mirrorCodexHome, stateDir, nodeExecutable, repoRoot, runtimeRoot });
  const driftReasons = [];
  if (!configMatchesManagedContract(config, { configBlock: rendered.configBlock, sqliteHome })) driftReasons.push('config');
  if (agents !== rendered.agents) driftReasons.push('agents');
  if (workflow !== rendered.workflow) driftReasons.push('workflow');
  if (orchestration !== renderManagedOrchestrationFile({ codexHome })) driftReasons.push('orchestration');
  return {
    path: codexHome,
    files,
    presentFiles,
    installed: driftReasons.length === 0,
    inSync: driftReasons.length === 0,
    driftReasons,
    stateDir,
    sqliteHome,
    orchestrationFile: files.orchestrationPath
  };
}

export async function applyBootstrap({
  codexHome,
  mirrorCodexHome = null,
  manageMirror = null,
  mode = 'install',
  platform = process.platform,
  isWsl = false,
  windowsHome = null,
  env = process.env,
  homeDir = os.homedir(),
  nodeExecutable = process.execPath,
  repoRoot = promptBridgeRepoRoot(),
  syncManagedRuntimeImpl = syncManagedRuntime
} = {}) {
  const resolvedWindowsHome = await resolveWindowsHome({ platform, isWsl, windowsHome, env });
  const resolved = resolveManagedCodexHomes({ codexHome, env, homeDir, mirrorCodexHome });
  const shouldManageMirror = typeof manageMirror === 'boolean' ? manageMirror : resolved.managesMirror;
  const runtime = await syncManagedRuntimeImpl({
    canonicalCodexHome: resolved.canonicalCodexHome,
    repoRoot,
    nodeExecutable,
    platform,
    dryRun: mode === 'dry-run'
  });
  const primary = await applyBootstrapToHome({
    codexHome: resolved.requestedCodexHome,
    mode,
    canonicalCodexHome: resolved.canonicalCodexHome,
    mirrorCodexHome: resolved.mirrorCodexHome,
    platform,
    isWsl,
    windowsHome: resolvedWindowsHome,
    homeDir,
    nodeExecutable,
    repoRoot,
    runtimeRoot: runtime.runtimeRoot
  });

  let mirror = null;
  if (shouldManageMirror) {
    mirror = await applyBootstrapToHome({
      codexHome: resolved.mirrorCodexHome,
      mode,
      canonicalCodexHome: resolved.canonicalCodexHome,
      mirrorCodexHome: resolved.mirrorCodexHome,
      platform,
      isWsl,
      windowsHome: resolvedWindowsHome,
      homeDir,
      nodeExecutable,
      repoRoot,
      runtimeRoot: runtime.runtimeRoot
    });
  }

  return {
    changed: primary.changed || !!mirror?.changed,
    role: resolved.role,
    codexHome: resolved.requestedCodexHome,
    canonicalCodexHome: resolved.canonicalCodexHome,
    mirrorCodexHome: shouldManageMirror ? resolved.mirrorCodexHome : null,
    runtime,
    primary,
    mirror
  };
}

export async function removeBootstrap({
  codexHome,
  mirrorCodexHome = null,
  removeMirror = null,
  env = process.env,
  homeDir = os.homedir()
} = {}) {
  const resolved = resolveManagedCodexHomes({ codexHome, env, homeDir, mirrorCodexHome });
  const shouldRemoveMirror = typeof removeMirror === 'boolean' ? removeMirror : resolved.managesMirror;

  const primary = await removeBootstrapFromHome({ codexHome: resolved.requestedCodexHome });
  let mirror = null;
  if (shouldRemoveMirror) mirror = await removeBootstrapFromHome({ codexHome: resolved.mirrorCodexHome });

  return {
    changed: primary.changed || !!mirror?.changed,
    role: resolved.role,
    codexHome: resolved.requestedCodexHome,
    canonicalCodexHome: resolved.canonicalCodexHome,
    mirrorCodexHome: shouldRemoveMirror ? resolved.mirrorCodexHome : null,
    primary,
    mirror
  };
}

export async function getBootstrapStatus({
  codexHome,
  mirrorCodexHome = null,
  platform = process.platform,
  isWsl = false,
  windowsHome = null,
  env = process.env,
  homeDir = os.homedir(),
  nodeExecutable = process.execPath,
  repoRoot = promptBridgeRepoRoot()
} = {}) {
  const resolvedWindowsHome = await resolveWindowsHome({ platform, isWsl, windowsHome });
  const resolved = resolveManagedCodexHomes({ codexHome, env, homeDir, mirrorCodexHome });
  const runtimeRoot = managedRuntimeRoot({ canonicalCodexHome: resolved.canonicalCodexHome });
  const runtime = {
    root: runtimeRoot,
    entrypoint: path.join(runtimeRoot, 'mcp-server.mjs'),
    packageJson: path.join(runtimeRoot, 'package.json'),
    packageLock: path.join(runtimeRoot, 'package-lock.json'),
    nodeModules: path.join(runtimeRoot, 'node_modules'),
    installed:
      (await pathExists(path.join(runtimeRoot, 'mcp-server.mjs'))) &&
      (await pathExists(path.join(runtimeRoot, 'package.json'))) &&
      (await pathExists(path.join(runtimeRoot, 'package-lock.json'))) &&
      (await pathExists(path.join(runtimeRoot, 'node_modules')))
  };
  const canonicalProfile = await getProfileStatus({
    codexHome: resolved.canonicalCodexHome,
    canonicalCodexHome: resolved.canonicalCodexHome,
    mirrorCodexHome: resolved.mirrorCodexHome,
    platform,
    isWsl,
    windowsHome: resolvedWindowsHome,
    homeDir,
    nodeExecutable,
    repoRoot,
    runtimeRoot
  });
  const mirrorProfile =
    resolved.mirrorCodexHome === resolved.canonicalCodexHome
      ? canonicalProfile
      : await getProfileStatus({
          codexHome: resolved.mirrorCodexHome,
          canonicalCodexHome: resolved.canonicalCodexHome,
          mirrorCodexHome: resolved.mirrorCodexHome,
          platform,
          isWsl,
          windowsHome: resolvedWindowsHome,
          homeDir,
          nodeExecutable,
          repoRoot,
          runtimeRoot
        });
  const targetProfile =
    resolved.role === 'mirror'
      ? mirrorProfile
      : resolved.role === 'canonical'
        ? canonicalProfile
        : await getProfileStatus({
            codexHome: resolved.requestedCodexHome,
            canonicalCodexHome: resolved.canonicalCodexHome,
            mirrorCodexHome: resolved.mirrorCodexHome,
            platform,
            isWsl,
            windowsHome: resolvedWindowsHome,
            homeDir,
            nodeExecutable,
            repoRoot,
            runtimeRoot
          });

  const stateDir = stateDirForBootstrap({ platform, isWsl, windowsHome: resolvedWindowsHome, homeDir });
  const managedServers = {
    codexConsult: managedMcpServerSpec({
      stateDir,
      nodeExecutable,
      repoRoot,
      runtimeRoot,
      canonicalCodexHome: resolved.canonicalCodexHome
    }),
    promptbridgeTalk: managedPromptbridgeTalkServerSpec({
      stateDir,
      nodeExecutable,
      repoRoot,
      runtimeRoot,
      canonicalCodexHome: resolved.canonicalCodexHome
    })
  };

  return {
    installed: targetProfile.installed,
    role: resolved.role,
    codexHome: resolved.requestedCodexHome,
    canonicalCodexHome: resolved.canonicalCodexHome,
    mirrorCodexHome: resolved.mirrorCodexHome,
    windowsHome: resolvedWindowsHome,
    files: targetProfile.files,
    managedServer: managedServers.codexConsult,
    managedServers,
    runtime,
    targetProfile,
    canonicalProfile,
    mirrorProfile,
    orchestration: {
      file: path.join(resolved.canonicalCodexHome, 'promptbridge-orchestration.toml'),
      present: await pathExists(path.join(resolved.canonicalCodexHome, 'promptbridge-orchestration.toml'))
    },
    supportMatrix: {
      supported: ['codex_cli_active_windows_profile', 'codex_cli_custom_windows_profile'],
      guided: ['openai_vscode_extension_shared_profile_fresh_chat_required'],
      optional: ['generic_vscode_mcp_servers']
    }
  };
}
