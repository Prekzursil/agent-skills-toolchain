#!/usr/bin/env node
import os from 'node:os';

import {
  applyBootstrap,
  removeBootstrap,
  getBootstrapStatus,
  defaultCodexHome,
  defaultMirrorCodexHome,
  detectBootstrapEnvironment,
  detectWindowsHomeForWsl
} from './bootstrap.mjs';
import { probeConsultationStack, runConsultationSelfTest } from './probe.mjs';

function argValue(name) {
  const idx = process.argv.indexOf(name);
  if (idx === -1) return null;
  return process.argv[idx + 1] || null;
}

function argFlag(name) {
  return process.argv.includes(name);
}

function usage() {
  console.log(`Usage: node integrations/codex/cli.mjs <install|update|status|probe|self-test|uninstall|dry-run> [options]

Options:
  --codex-home <path>      Override the target CODEX_HOME path.
  --workspace-dir <path>   Override the workspace directory used for self-tests.
  --alternate-codex-home <path>
                            Override the derived mirror CODEX_HOME path used by self-test.
  --mirror-codex-home <path>
                            Override the derived ~/.codex compatibility mirror.
  --platform <id>          Override platform (win32, darwin, linux).
  --windows-home <path>    Override the Windows home directory for WSL bridging.
  --wsl                    Force WSL bridging mode.
  --json                   Print machine-readable JSON.
  --help                   Show this help text.
`);
}

async function resolveOptions() {
  const detected = detectBootstrapEnvironment();
  const forcedPlatform = String(argValue('--platform') || '').trim() || detected.platform;
  const forcedCodexHome = String(argValue('--codex-home') || '').trim();
  const isWsl = argFlag('--wsl') || detected.isWsl;
  let windowsHome = String(argValue('--windows-home') || '').trim() || detected.windowsHome || null;
  if (isWsl && !windowsHome) windowsHome = await detectWindowsHomeForWsl();

  return {
    platform: forcedPlatform,
    isWsl,
    windowsHome,
    codexHome: forcedCodexHome || defaultCodexHome({ homeDir: os.homedir() }),
    mirrorCodexHome: String(argValue('--mirror-codex-home') || '').trim() || defaultMirrorCodexHome({ homeDir: os.homedir() }),
    workspaceDir: String(argValue('--workspace-dir') || '').trim() || process.cwd(),
    alternateCodexHome: String(argValue('--alternate-codex-home') || '').trim() || null
  };
}

async function main() {
  const cmd = String(process.argv[2] || '').trim().toLowerCase();
  if (!cmd || cmd === '--help' || cmd === '-h') {
    usage();
    return;
  }

  if (!['install', 'update', 'status', 'probe', 'self-test', 'uninstall', 'dry-run'].includes(cmd)) {
    usage();
    throw new Error(`invalid_command:${cmd}`);
  }

  const opts = await resolveOptions();
  const asJson = argFlag('--json');
  let out;

  if (cmd === 'status') {
    out = {
      command: cmd,
      options: opts,
      ...(await getBootstrapStatus({
        codexHome: opts.codexHome,
        mirrorCodexHome: opts.mirrorCodexHome,
        platform: opts.platform,
        isWsl: opts.isWsl,
        windowsHome: opts.windowsHome,
        nodeExecutable: process.execPath
      }))
    };
  } else if (cmd === 'probe') {
    out = {
      command: cmd,
      options: opts,
      ...(await probeConsultationStack({
        codexHome: opts.codexHome,
        mirrorCodexHome: opts.mirrorCodexHome,
        workspaceDir: opts.workspaceDir,
        platform: opts.platform,
        isWsl: opts.isWsl,
        windowsHome: opts.windowsHome
      }))
    };
  } else if (cmd === 'self-test') {
    out = {
      command: cmd,
      options: opts,
      ...(await runConsultationSelfTest({
        primaryCodexHome: opts.codexHome,
        alternateCodexHome: opts.alternateCodexHome,
        workspaceDir: opts.workspaceDir,
        platform: opts.platform,
        isWsl: opts.isWsl,
        windowsHome: opts.windowsHome
      }))
    };
  } else if (cmd === 'uninstall') {
    out = {
      command: cmd,
      options: opts,
      ...(await removeBootstrap({ codexHome: opts.codexHome, mirrorCodexHome: opts.mirrorCodexHome }))
    };
  } else {
    out = {
      command: cmd,
      options: opts,
      ...(await applyBootstrap({
        codexHome: opts.codexHome,
        mirrorCodexHome: opts.mirrorCodexHome,
        mode: cmd === 'dry-run' ? 'dry-run' : 'install',
        platform: opts.platform,
        isWsl: opts.isWsl,
        windowsHome: opts.windowsHome,
        nodeExecutable: process.execPath
      }))
    };
  }

  if (asJson) {
    console.log(JSON.stringify(out, null, 2));
    return;
  }

  console.log(JSON.stringify(out, null, 2));
}

main().catch((err) => {
  const message = err?.message || String(err);
  console.error(message);
  process.exit(1);
});
