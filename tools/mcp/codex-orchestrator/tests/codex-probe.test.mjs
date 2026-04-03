import test from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';

import {
  expectedToolNames,
  parseAgentJsonResult,
  probeConsultationStack,
  resolveProbeClientModulePaths,
  probeVsCodeExtensionPreflight,
  runConsultationSelfTest,
  runToolVisibilityCheck
} from '../integrations/codex/probe.mjs';

function bootstrapFixture() {
  return {
    role: 'active',
    canonicalCodexHome: 'C:/Users/Test/.codex',
    legacyCodexHome: 'C:/Users/Test/.codex-vscode',
    targetProfile: { installed: true, files: {} },
    canonicalProfile: { installed: true, files: {} },
    mirrorProfile: { installed: false, files: {} },
    managedServer: {
      command: 'node',
      args: ['C:/repo/mcp-server.mjs'],
      env: { PROMPTBRIDGE_DESKTOP_STATE_DIR: 'C:/Users/Test/.promptbridge-desktop' }
    },
    managedServers: {
      codexConsult: {
        command: 'node',
        args: ['C:/repo/mcp-server.mjs'],
        env: { PROMPTBRIDGE_DESKTOP_STATE_DIR: 'C:/Users/Test/.promptbridge-desktop' }
      },
      promptbridgeTalk: {
        command: 'node',
        args: ['C:/repo/mcp-server.mjs'],
        env: { PROMPTBRIDGE_DESKTOP_STATE_DIR: 'C:/Users/Test/.promptbridge-desktop' }
      }
    }
  };
}

function healthyTalkToolNames() {
  return [
    'promptbridge_query',
    'agentify_query',
    'promptbridge_read_page',
    'agentify_read_page',
    'promptbridge_navigate',
    'agentify_navigate',
    'promptbridge_ensure_ready',
    'agentify_ensure_ready',
    'promptbridge_show',
    'agentify_show',
    'promptbridge_hide',
    'agentify_hide',
    'promptbridge_status',
    'agentify_status',
    'promptbridge_session_state',
    'agentify_session_state',
    'promptbridge_session_configure',
    'agentify_session_configure',
    'promptbridge_image_gen',
    'agentify_image_gen',
    'promptbridge_download_images',
    'agentify_download_images',
    'promptbridge_tabs',
    'agentify_tabs',
    'promptbridge_tab_create',
    'agentify_tab_create',
    'promptbridge_tab_close',
    'agentify_tab_close',
    'promptbridge_shutdown',
    'agentify_shutdown',
    'promptbridge_rotate_token',
    'agentify_rotate_token',
    'promptbridge_discuss',
    'agentify_discuss',
    'promptbridge_curate',
    'agentify_curate'
  ];
}

function healthyCodexToolNames() {
  return ['codex_consult', 'codex_brainstorm', 'codex_review', 'codex_discuss', 'codex_coordinate', 'codex_curate'];
}

function healthyUnifiedToolNames() {
  return [...healthyCodexToolNames(), ...healthyTalkToolNames()];
}

test('codex probe: resolveProbeClientModulePaths walks up to shared runtime node_modules for nested talk-lane entrypoints', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'codex-probe-runtime-'));
  try {
    const nestedSrc = path.join(root, 'tools', 'web', 'promptbridge-talk-lane', 'src');
    const sdkClientDir = path.join(root, 'node_modules', '@modelcontextprotocol', 'sdk', 'dist', 'esm', 'client');
    await fs.mkdir(nestedSrc, { recursive: true });
    await fs.mkdir(sdkClientDir, { recursive: true });
    await fs.writeFile(path.join(nestedSrc, 'mcp-server.mjs'), 'export {};\n');
    await fs.writeFile(path.join(sdkClientDir, 'index.js'), 'export {};\n');
    await fs.writeFile(path.join(sdkClientDir, 'stdio.js'), 'export {};\n');

    const resolved = await resolveProbeClientModulePaths({
      serverEntrypoint: path.join(nestedSrc, 'mcp-server.mjs'),
      cwd: root
    });

    assert.equal(resolved.ok, true);
    assert.equal(resolved.runtimeRoot, nestedSrc);
    assert.equal(resolved.clientIndexPath, path.join(sdkClientDir, 'index.js'));
    assert.equal(resolved.clientStdioPath, path.join(sdkClientDir, 'stdio.js'));
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});

test('codex probe: expected tool names include codex orchestration plus promptbridge and legacy agentify aliases', () => {
  const names = expectedToolNames();

  assert.ok(names.includes('codex_consult'));
  assert.ok(names.includes('codex_brainstorm'));
  assert.ok(names.includes('promptbridge_status'));
  assert.ok(names.includes('promptbridge_query'));
  assert.ok(names.includes('agentify_status'));
  assert.ok(names.includes('agentify_query'));
});

test('codex probe: parseAgentJsonResult extracts strict JSON from agent message events', () => {
  const stdout = [
    JSON.stringify({ type: 'thread.started', thread_id: 'abc' }),
    JSON.stringify({
      type: 'item.completed',
      item: {
        id: 'item_5',
        type: 'agent_message',
        text: JSON.stringify({
          tool_visible: true,
          tool_name: 'agentify_status',
          status_ok: true,
          url: 'https://chatgpt.com/',
          blocked: false,
          fallback_to_lane_a: false
        })
      }
    })
  ].join('\n');

  assert.deepEqual(parseAgentJsonResult(stdout), {
    tool_visible: true,
    tool_name: 'agentify_status',
    status_ok: true,
    url: 'https://chatgpt.com/',
    blocked: false,
    fallback_to_lane_a: false
  });
});

test('codex probe: runToolVisibilityCheck passes skipGitRepoCheck to codex exec', async () => {
  let capturedCall = null;
  const result = await runToolVisibilityCheck({
    codexHome: 'C:/Users/Test/.codex',
    workspaceDir: 'C:/Users/Test',
    runCodexExecImpl: async (args) => {
      capturedCall = args;
      return {
        ok: true,
        stdout: JSON.stringify({
          item: {
            type: 'agent_message',
            text: JSON.stringify({
              codex_tool_visible: true,
              codex_tool_name: 'codex_consult',
              promptbridge_tool_visible: true,
              promptbridge_tool_name: 'promptbridge_status',
              status_ok: true,
              url: null,
              blocked: null,
              fallback_to_lane_a: false
            })
          }
        }),
        stderr: '',
        exit: { code: 0, signal: null },
        sessionId: null,
        abortedReason: null
      };
    }
  });

  assert.equal(capturedCall?.skipGitRepoCheck, true);
  assert.equal(result.ok, true);
});

test('codex probe: probeConsultationStack classifies missing desktop state before later checks', async () => {
  const result = await probeConsultationStack({
    codexHome: 'C:/Users/Test/.codex',
    mirrorCodexHome: 'C:/Users/Test/.codex-vscode',
    workspaceDir: 'C:/repo',
    getBootstrapStatusImpl: async () => bootstrapFixture(),
    probeDesktopConnectionImpl: async () => ({ ok: false, reason: 'missing_state_or_token' }),
    probeMcpServerStartupImpl: async () => {
      throw new Error('should_not_be_called');
    },
    runToolVisibilityCheckImpl: async () => {
      throw new Error('should_not_be_called');
    }
  });

  assert.equal(result.ok, false);
  assert.equal(result.failureLayer, 'desktop_state');
  assert.equal(result.desktop.reason, 'missing_state_or_token');
});

test('codex probe: probeConsultationStack returns expected tool names when both lanes, CLI visibility, and VS Code preflight are healthy', async () => {
  const result = await probeConsultationStack({
    codexHome: 'C:/Users/Test/.codex',
    mirrorCodexHome: 'C:/Users/Test/.codex-vscode',
    workspaceDir: 'C:/repo',
    getBootstrapStatusImpl: async () => bootstrapFixture(),
    probeDesktopConnectionImpl: async () => ({
      ok: true,
      status: { ok: true, url: 'https://chatgpt.com/', blocked: false }
    }),
    probeMcpServerStartupImpl: async () => ({ ok: true, phase: 'handshake', toolNames: healthyUnifiedToolNames() }),

    runSchemaConsultationCheckImpl: async () => ({
      ok: true,
      parsed: {
        tool_visible: true,
        consultation_ok: true,
        schema_keys_present: ['problem', 'assumptions', 'options', 'recommended_option', 'risks', 'verification_plan', 'confidence'],
        fallback_to_lane_a: false
      },
      raw: { toolNames: ['codex_consult'] }
    }),
    runPromptbridgeStatusCheckImpl: async () => ({
      ok: true,
      parsed: {
        tool_visible: true,
        tool_name: 'promptbridge_status',
        status_ok: true,
        url: 'https://chatgpt.com/',
        blocked: false,
        fallback_to_lane_a: false
      },
      status: { toolNames: ['promptbridge_status', 'agentify_status'] }
    }),
    probeVsCodeExtensionPreflightImpl: async () => ({ ok: true, extensionInstalled: true }),
    probeVsCodeAppServerMirrorImpl: async () => ({
      ok: true,
      configHasCodexConsult: true,
      configHasPromptbridgeTalk: true,
      statusToolNames: ['promptbridge_status']
    })
  });

  assert.equal(result.ok, true);
  assert.equal(result.failureLayer, null);
  assert.ok(result.exportedToolNames.includes('codex_consult'));
  assert.ok(result.exportedToolNames.includes('promptbridge_status'));
  assert.ok(result.exportedToolNames.includes('agentify_status'));
});

test('codex probe: probeConsultationStack classifies handshake success without expected codex tools as mcp_handshake', async () => {
  const result = await probeConsultationStack({
    codexHome: 'C:/Users/Test/.codex',
    mirrorCodexHome: 'C:/Users/Test/.codex-vscode',
    workspaceDir: 'C:/repo',
    getBootstrapStatusImpl: async () => bootstrapFixture(),
    probeDesktopConnectionImpl: async () => ({
      ok: true,
      status: { ok: true, url: 'https://chatgpt.com/', blocked: false }
    }),
    probeMcpServerStartupImpl: async () => ({ ok: true, phase: 'handshake', toolNames: ['other_tool'] }),
    runToolVisibilityCheckImpl: async () => {
      throw new Error('should_not_be_called');
    }
  });

  assert.equal(result.ok, false);
  assert.equal(result.failureLayer, 'mcp_handshake');
  assert.equal(result.serverKind, 'codex_consult');
  assert.ok(result.server.missingExpectedTools.includes('codex_consult'));
});

test('codex probe: runConsultationSelfTest classifies active profile, custom profile, and VS Code proof semantics', async () => {
  const result = await runConsultationSelfTest({
    primaryCodexHome: 'C:/Users/Test/.codex',
    alternateCodexHome: 'D:/CustomCodexHome',
    workspaceDir: 'C:/repo',
    runToolVisibilityCheckImpl: async ({ codexHome }) => ({
      ok: true,
      parsed: {
        codex_tool_visible: true,
        codex_tool_name: 'codex_consult',
        promptbridge_tool_visible: true,
        promptbridge_tool_name: 'promptbridge_status',
        status_ok: true,
        url: 'https://chatgpt.com/',
        blocked: false,
        fallback_to_lane_a: false
      },
      codexHome
    }),
    runPromptbridgeStatusCheckImpl: async ({ codexHome }) => ({
      ok: true,
      parsed: {
        tool_visible: true,
        tool_name: 'promptbridge_status',
        status_ok: true,
        url: 'https://chatgpt.com/',
        blocked: false,
        fallback_to_lane_a: false
      },
      codexHome
    }),
    runSchemaConsultationCheckImpl: async ({ codexHome }) => ({
      ok: true,
      parsed: {
        tool_visible: true,
        consultation_ok: true,
        schema_keys_present: ['problem', 'assumptions', 'options', 'recommended_option', 'risks', 'verification_plan', 'confidence'],
        fallback_to_lane_a: false
      },
      codexHome
    }),
    getBootstrapStatusImpl: async () => ({
      canonicalCodexHome: 'C:/Users/Test/.codex',
      legacyCodexHome: 'C:/Users/Test/.codex-vscode',
      targetProfile: { installed: true },
      canonicalProfile: { installed: true },
      mirrorProfile: { installed: false }
    }),
    probeVsCodeExtensionPreflightImpl: async () => ({
      ok: true,
      extensionInstalled: true,
      canonicalProfilePresent: true,
      canonicalHasCodexConsult: true,
      canonicalHasPromptbridgeTalk: true,
      desktopReady: true
    }),
    probeVsCodeAppServerMirrorImpl: async () => ({
      ok: true,
      configHasCodexConsult: true,
      configHasPromptbridgeTalk: true,
      statusToolNames: ['promptbridge_status']
    })
  });

  assert.equal(result.ok, true);
  assert.equal(result.activeProfile.visibility.parsed.codex_tool_visible, true);
  assert.equal(result.activeProfile.talkLane.parsed.tool_visible, true);
  assert.equal(result.customProfile.consultation.parsed.consultation_ok, true);
  assert.equal(result.vscode.preflight.ok, true);
  assert.equal(result.vscode.appServer.ok, true);
  assert.deepEqual(result.summary.provenSurfaces, [
    'codex_cli_active_windows_profile',
    'codex_cli_custom_windows_profile'
  ]);
  assert.deepEqual(result.summary.configuredSurfaces, ['openai_vscode_extension_shared_profile_fresh_chat_required']);
});
test('codex probe: probeVsCodeExtensionPreflight reports shared-profile extension readiness', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'promptbridge-vscode-preflight-'));
  const settingsDir = path.join(root, 'settings');
  const extensionsDir = path.join(root, 'extensions');
  const canonicalHome = path.join(root, '.codex');
  const settingsPath = path.join(settingsDir, 'settings.json');

  await fs.mkdir(settingsDir, { recursive: true });
  await fs.mkdir(path.join(extensionsDir, 'openai.chatgpt-26.5304.20706-win32-x64'), { recursive: true });
  await fs.mkdir(canonicalHome, { recursive: true });
  await fs.writeFile(
    settingsPath,
    JSON.stringify({
      'chatgpt.runCodexInWindowsSubsystemForLinux': false,
      mcpServers: {
        codex_consult: { command: 'node' }
      }
    }),
    'utf8'
  );
  await fs.writeFile(
    path.join(canonicalHome, 'config.toml'),
    `[mcp_servers.codex_consult]\ncommand = "node"\n`,
    'utf8'
  );

  const result = await probeVsCodeExtensionPreflight({
    bootstrapStatus: {
      canonicalCodexHome: canonicalHome,
      legacyCodexHome: path.join(root, '.codex-vscode'),
      canonicalProfile: { installed: true }
    },
    desktop: { ok: true },
    platform: 'win32',
    isWsl: false,
    settingsPath,
    extensionsRoot: extensionsDir,
    detectVsCodeOriginatorCodexHomeImpl: async () => ({ codexHome: canonicalHome }),
    listLiveVsCodeAppServersImpl: async () => []
  });

  assert.equal(result.ok, true);
  assert.equal(result.extensionInstalled, true);
  assert.equal(result.wslModeSetting, false);
  assert.equal(result.canonicalHasCodexConsult, true);
  assert.equal(result.canonicalHasPromptbridgeTalk, true);
  assert.equal(result.genericMcpServerConfigured, true);
});
