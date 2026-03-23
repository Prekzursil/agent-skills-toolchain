import test from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

import {
  applyBootstrap,
  removeBootstrap,
  getBootstrapStatus,
  managedMcpServerSpec,
  managedRuntimeRoot,
  managedSqliteHome,
  defaultCodexHome,
  defaultMirrorCodexHome
} from '../integrations/codex/bootstrap.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function tempDir() {
  return await fs.mkdtemp(path.join(os.tmpdir(), 'promptbridge-codex-bootstrap-test-'));
}

const isolatedTestEnv = { CODEX_HOME: '', USERPROFILE: '' };

function syncRuntimeStubFor(canonicalCodexHome) {
  const runtimeRoot = managedRuntimeRoot({ canonicalCodexHome });
  return async () => {
    await fs.mkdir(path.join(runtimeRoot, 'node_modules'), { recursive: true });
    await fs.writeFile(path.join(runtimeRoot, 'mcp-server.mjs'), 'export {};\n', 'utf8');
    await fs.writeFile(path.join(runtimeRoot, 'package.json'), '{}\n', 'utf8');
    await fs.writeFile(path.join(runtimeRoot, 'package-lock.json'), '{}\n', 'utf8');
    return { ok: true, changed: true, runtimeRoot };
  };
}

test('codex bootstrap: install writes managed codex config and docs without deleting existing config', async () => {
  const root = await tempDir();
  const dir = defaultCodexHome({ env: { CODEX_HOME: '' }, homeDir: root });
  const mirrorDir = defaultMirrorCodexHome({ homeDir: root });
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(
    path.join(dir, 'config.toml'),
    'model = "old-model"\n\n[features]\nundo = true\n',
    'utf8'
  );

  const out = await applyBootstrap({
    codexHome: dir,
    mirrorCodexHome: mirrorDir,
    manageMirror: true,
    mode: 'install',
    platform: 'linux',
    isWsl: true,
    windowsHome: '/mnt/c/Users/Prekzursil',
    nodeExecutable: '/custom/node',
    homeDir: root,
    env: isolatedTestEnv,
    syncManagedRuntimeImpl: syncRuntimeStubFor(dir)
  });

  assert.equal(out.changed, true);

  const config = await fs.readFile(path.join(dir, 'config.toml'), 'utf8');
  assert.match(config, /model = "gpt-5\.4"/);
  assert.match(config, /review_model = "gpt-5\.4"/);
  assert.match(config, new RegExp(`sqlite_home = ${JSON.stringify(managedSqliteHome({ canonicalCodexHome: dir, codexHome: dir })).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`));
  assert.match(config, /\[mcp_servers\.codex_consult\]/);
  assert.match(config, /\[mcp_servers\.promptbridge_talk\]/);
  assert.match(config, /command = "\/custom\/node"/);
  assert.match(
    config,
    new RegExp(`args = ${JSON.stringify([path.join(managedRuntimeRoot({ canonicalCodexHome: dir }), 'mcp-server.mjs')]).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`)
  );
  assert.match(config, /PROMPTBRIDGE_DESKTOP_STATE_DIR = "\/mnt\/c\/Users\/Prekzursil\/\.promptbridge-desktop"/);
  assert.match(config, /\[features\][\s\S]*memories = true/);
  assert.match(config, /undo = true/);
  assert.match(config, /suppress_unstable_features_warning = true/);

  const agents = await fs.readFile(path.join(dir, 'AGENTS.md'), 'utf8');
  assert.match(agents, /codex_consult/);
  assert.match(agents, /fallback_to_lane_a = true/);

  const workflow = await fs.readFile(path.join(dir, 'CONSULTATION_WORKFLOW.md'), 'utf8');
  assert.match(workflow, /PromptBridge Desktop/);
  assert.match(workflow, /codex_consult/);
  assert.match(workflow, /Canonical managed profile/);
  assert.match(workflow, /Legacy migration input only/);
  assert.match(workflow, /subagent-driven execution/i);
  assert.match(workflow, /inline execution/i);

  const orchestration = await fs.readFile(path.join(dir, 'promptbridge-orchestration.toml'), 'utf8');
  assert.match(orchestration, /\[profiles\.consult\]/);
  assert.match(orchestration, /tool = "codex_consult"/);
  assert.match(orchestration, /\[skill_mappings\.codex-brainstorm\]/);

  const brainstormSkill = await fs.readFile(path.join(dir, 'skills', 'codex-brainstorm', 'SKILL.md'), 'utf8');
  assert.match(brainstormSkill, /codex_brainstorm/);
  const governanceSkill = await fs.readFile(path.join(dir, 'skills', 'codex-governance', 'SKILL.md'), 'utf8');
  assert.match(governanceSkill, /codex_curate/);
  const quickstartSkill = await fs.readFile(path.join(dir, 'skills', 'multi-agent-quickstart', 'SKILL.md'), 'utf8');
  assert.match(quickstartSkill, /Execution Choice/);
  assert.match(quickstartSkill, /subagent-driven execution/);

  const mirrorConfig = await fs.readFile(path.join(mirrorDir, 'config.toml'), 'utf8');
  assert.match(
    mirrorConfig,
    new RegExp(`sqlite_home = ${JSON.stringify(managedSqliteHome({ canonicalCodexHome: dir, codexHome: mirrorDir })).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`)
  );
  assert.match(mirrorConfig, /\[mcp_servers\.codex_consult\]/);
  assert.match(mirrorConfig, /\[mcp_servers\.promptbridge_talk\]/);
  assert.match(mirrorConfig, /PROMPTBRIDGE_DESKTOP_STATE_DIR = "\/mnt\/c\/Users\/Prekzursil\/\.promptbridge-desktop"/);
});

test('codex bootstrap: dry-run reports changes without mutating files', async () => {
  const root = await tempDir();
  const dir = defaultCodexHome({ env: { CODEX_HOME: '' }, homeDir: root });
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(path.join(dir, 'config.toml'), '', 'utf8');

  const out = await applyBootstrap({
    codexHome: dir,
    mode: 'dry-run',
    platform: 'linux',
    isWsl: false,
    homeDir: root,
    env: isolatedTestEnv,
    syncManagedRuntimeImpl: async () => ({ ok: true, changed: true, runtimeRoot: managedRuntimeRoot({ canonicalCodexHome: dir }) })
  });

  assert.equal(out.changed, true);
  const config = await fs.readFile(path.join(dir, 'config.toml'), 'utf8');
  assert.equal(config, '');
});

test('codex bootstrap: uninstall removes managed files and blocks', async () => {
  const root = await tempDir();
  const dir = defaultCodexHome({ env: { CODEX_HOME: '' }, homeDir: root });
  const mirrorDir = defaultMirrorCodexHome({ homeDir: root });
  await applyBootstrap({
    codexHome: dir,
    mirrorCodexHome: mirrorDir,
    manageMirror: true,
    mode: 'install',
    platform: 'linux',
    isWsl: false,
    homeDir: root,
    env: isolatedTestEnv,
    syncManagedRuntimeImpl: syncRuntimeStubFor(dir)
  });

  const removed = await removeBootstrap({ codexHome: dir, mirrorCodexHome: mirrorDir, removeMirror: true, env: isolatedTestEnv, homeDir: root });
  assert.equal(removed.changed, true);

  const config = await fs.readFile(path.join(dir, 'config.toml'), 'utf8');
  assert.doesNotMatch(config, /\[mcp_servers\.codex_consult\]/);

  const mirrorConfig = await fs.readFile(path.join(mirrorDir, 'config.toml'), 'utf8');
  assert.doesNotMatch(mirrorConfig, /\[mcp_servers\.codex_consult\]/);

  const status = await getBootstrapStatus({ codexHome: dir, mirrorCodexHome: mirrorDir, homeDir: root, env: isolatedTestEnv });
  assert.equal(status.installed, false);
});

test('codex bootstrap: managedMcpServerSpec renders absolute repo entrypoint and explicit state dir env', () => {
  const repoRoot = path.resolve(__dirname, '..');
  const runtimeRoot = '/tmp/codex/promptbridge-runtime';
  const spec = managedMcpServerSpec({
    repoRoot,
    nodeExecutable: '/opt/node/bin/node',
    stateDir: '/tmp/promptbridge-state',
    runtimeRoot,
    canonicalCodexHome: '/tmp/codex'
  });

  assert.equal(spec.command, '/opt/node/bin/node');
  assert.equal(spec.args[0], path.join(runtimeRoot, 'mcp-server.mjs'));
  assert.equal(spec.env.PROMPTBRIDGE_DESKTOP_STATE_DIR, '/tmp/promptbridge-state');
  assert.equal(spec.env.AGENTIFY_DESKTOP_STATE_DIR, '/tmp/promptbridge-state');
  assert.equal(spec.env.PROMPTBRIDGE_CODEX_HOME, '/tmp/codex');
  assert.equal(spec.env.PROMPTBRIDGE_ORCHESTRATION_CONFIG, path.join('/tmp/codex', 'promptbridge-orchestration.toml'));
});

test('codex bootstrap: status reports canonical profile, derived mirror, and VS Code support target', async () => {
  const root = await tempDir();
  const dir = path.join(root, 'custom-codex-home');
  const canonicalHome = defaultCodexHome({ env: { CODEX_HOME: '' }, homeDir: root });
  const mirrorDir = defaultMirrorCodexHome({ homeDir: root });
  await applyBootstrap({
    codexHome: dir,
    mirrorCodexHome: mirrorDir,
    mode: 'install',
    platform: 'linux',
    isWsl: false,
    nodeExecutable: '/custom/node',
    homeDir: root,
    env: isolatedTestEnv,
    syncManagedRuntimeImpl: syncRuntimeStubFor(canonicalHome)
  });

  const status = await getBootstrapStatus({
    codexHome: dir,
    mirrorCodexHome: mirrorDir,
    platform: 'linux',
    isWsl: false,
    nodeExecutable: '/custom/node',
    homeDir: root,
    env: isolatedTestEnv
  });

  assert.equal(status.installed, true);
  assert.equal(status.role, 'custom');
  assert.equal(status.managedServer.command, '/custom/node');
  assert.equal(status.managedServers.codexConsult.command, '/custom/node');
  assert.equal(status.managedServers.promptbridgeTalk.command, '/custom/node');
  assert.equal(status.managedServer.args[0], path.join(managedRuntimeRoot({ canonicalCodexHome: canonicalHome }), 'mcp-server.mjs'));
  assert.equal(status.runtime.installed, true);
  assert.equal(status.canonicalProfile.installed, false);
  assert.equal(status.mirrorProfile.installed, false);
  assert.equal(status.targetProfile.installed, true);
  assert.equal(status.orchestration.file, path.join(canonicalHome, 'promptbridge-orchestration.toml'));
  assert.deepEqual(status.supportMatrix.supported, [
    'codex_cli_active_windows_profile',
    'codex_cli_custom_windows_profile'
  ]);
  assert.deepEqual(status.supportMatrix.guided, ['openai_vscode_extension_shared_profile_fresh_chat_required']);
  assert.deepEqual(status.supportMatrix.optional, ['generic_vscode_mcp_servers']);
});

test('codex bootstrap: reinstall over a managed profile stays idempotent and does not duplicate markers', async () => {
  const root = await tempDir();
  const dir = defaultCodexHome({ env: { CODEX_HOME: '' }, homeDir: root });
  const mirrorDir = defaultMirrorCodexHome({ homeDir: root });

  await applyBootstrap({
    codexHome: dir,
    mirrorCodexHome: mirrorDir,
    manageMirror: true,
    mode: 'install',
    platform: 'linux',
    isWsl: true,
    windowsHome: '/mnt/c/Users/Prekzursil',
    nodeExecutable: '/custom/node',
    homeDir: root,
    env: isolatedTestEnv,
    syncManagedRuntimeImpl: syncRuntimeStubFor(dir)
  });

  await applyBootstrap({
    codexHome: dir,
    mirrorCodexHome: mirrorDir,
    manageMirror: true,
    mode: 'install',
    platform: 'linux',
    isWsl: true,
    windowsHome: '/mnt/c/Users/Prekzursil',
    nodeExecutable: '/custom/node',
    homeDir: root,
    env: isolatedTestEnv,
    syncManagedRuntimeImpl: syncRuntimeStubFor(dir)
  });

  const config = await fs.readFile(path.join(dir, 'config.toml'), 'utf8');
  const mirrorConfig = await fs.readFile(path.join(mirrorDir, 'config.toml'), 'utf8');
  const startMarker = /# >>> promptbridge-codex managed >>>/g;

  assert.equal(config.match(startMarker)?.length ?? 0, 1);
  assert.equal(mirrorConfig.match(startMarker)?.length ?? 0, 1);

  const status = await getBootstrapStatus({
    codexHome: dir,
    mirrorCodexHome: mirrorDir,
    platform: 'linux',
    isWsl: true,
    windowsHome: '/mnt/c/Users/Prekzursil',
    nodeExecutable: '/custom/node',
    homeDir: root,
    env: isolatedTestEnv
  });

  assert.equal(status.targetProfile.installed, true);
  assert.equal(status.mirrorProfile.installed, true);
});

test('codex bootstrap: status remains installed when the user changes the active model selection', async () => {
  const root = await tempDir();
  const dir = defaultCodexHome({ env: { CODEX_HOME: '' }, homeDir: root });
  const mirrorDir = defaultMirrorCodexHome({ homeDir: root });

  await applyBootstrap({
    codexHome: dir,
    mirrorCodexHome: mirrorDir,
    manageMirror: true,
    mode: 'install',
    platform: 'linux',
    isWsl: false,
    nodeExecutable: '/custom/node',
    homeDir: root,
    env: isolatedTestEnv,
    syncManagedRuntimeImpl: syncRuntimeStubFor(dir)
  });

  const configPath = path.join(dir, 'config.toml');
  const config = await fs.readFile(configPath, 'utf8');
  await fs.writeFile(configPath, config.replace(/^model = "gpt-5\.4"$/m, 'model = "gpt-5.3-codex"'), 'utf8');

  const status = await getBootstrapStatus({
    codexHome: dir,
    mirrorCodexHome: mirrorDir,
    platform: 'linux',
    isWsl: false,
    nodeExecutable: '/custom/node',
    homeDir: root,
    env: isolatedTestEnv
  });

  assert.equal(status.targetProfile.installed, true);
  assert.deepEqual(status.targetProfile.driftReasons, []);
});
