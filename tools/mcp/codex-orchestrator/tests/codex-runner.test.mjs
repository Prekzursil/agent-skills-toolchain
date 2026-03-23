import test from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';

import { resolveCodexInvocation } from '../src/orchestrator/codex.mjs';

test('codex runner: resolveCodexInvocation prefers global npm codex.js on Windows', async () => {
  const home = await fs.mkdtemp(path.join(os.tmpdir(), 'codex-runner-win-'));
  try {
    const appData = path.join(home, 'AppData', 'Roaming');
    const npmDir = path.join(appData, 'npm');
    const scriptPath = path.join(npmDir, 'node_modules', '@openai', 'codex', 'bin', 'codex.js');
    await fs.mkdir(path.dirname(scriptPath), { recursive: true });
    await fs.writeFile(scriptPath, 'console.log("codex");\n');

    const resolved = await resolveCodexInvocation({
      platform: 'win32',
      nodeExecutable: 'C:/Program Files/nodejs/node.exe',
      env: { APPDATA: appData, USERPROFILE: home }
    });

    assert.equal(resolved.command, 'C:/Program Files/nodejs/node.exe');
    assert.deepEqual(resolved.args, [scriptPath]);
    assert.equal(resolved.shell, false);
  } finally {
    await fs.rm(home, { recursive: true, force: true });
  }
});

test('codex runner: resolveCodexInvocation honors CODEX_CLI_BIN override', async () => {
  const resolved = await resolveCodexInvocation({
    platform: 'win32',
    env: { CODEX_CLI_BIN: 'C:/Tools/codex.cmd' }
  });

  assert.equal(resolved.command, 'C:/Tools/codex.cmd');
  assert.deepEqual(resolved.args, []);
  assert.equal(resolved.shell, true);
});
