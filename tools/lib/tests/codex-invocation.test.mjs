// Tests for tools/lib/codex-invocation.mjs (K7).
//
// The origin (tools/mcp/codex-orchestrator/src/orchestrator/codex.mjs) had NO test file covering
// resolveCodexInvocation or the argv build - which is how both salvaged-away defects shipped.
// The two DEFECT tests below each carry a CONTROL that reproduces the ORIGINAL builder and
// requires it to fail, so a green here is a measurement and not silence (rule 3b).

import test from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';

import {
  resolveCodexInvocation,
  buildCodexExecArgs,
  writePromptFile,
  createCodexExecPlan,
  PROMPT_FROM_STDIN
} from '../codex-invocation.mjs';

const WINDOWS_CMDLINE_LIMIT = 32767; // CreateProcess hard cap

async function tmp() {
  return await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), 'toolslib-codex-')));
}

// Reproduction of the ORIGINAL argv build (codex.mjs:80-92) - used only as a control.
function originalArgs({ cwd, prompt, ephemeral = false, sessionId = null }) {
  const args = ['exec'];
  if (ephemeral) args.push('--ephemeral');
  args.push('--json', '-C', cwd);
  if (!ephemeral && sessionId) args.push('resume', sessionId);
  args.push(String(prompt || '')); // the defect
  return args;
}

// ============================ DEFECT (a): prompt must never be argv ============================

test('codex: DEFECT (a) - the prompt is NEVER placed in argv', () => {
  const secret = 'THE-PROMPT-PAYLOAD-MARKER';
  const args = buildCodexExecArgs({ cwd: '/w' });
  assert.ok(!args.includes(secret));
  assert.equal(args.at(-1), PROMPT_FROM_STDIN, 'argv must end with the stdin token');
  assert.equal(PROMPT_FROM_STDIN, '-');
  // buildCodexExecArgs has no prompt parameter at all - passing one changes nothing.
  assert.deepEqual(buildCodexExecArgs({ cwd: '/w', prompt: secret }), args);
});

test('codex: DEFECT (a) - a 40,000-char prompt stays far under the CreateProcess limit', async () => {
  const dir = await tmp();
  const huge = 'A'.repeat(40_000);
  const plan = await createCodexExecPlan({ prompt: huge, workspaceDir: dir, promptDir: dir, platform: 'linux' });

  const cmdlineLen = [plan.command, ...plan.args].join(' ').length;
  assert.ok(cmdlineLen < 1000, `argv should be tiny, was ${cmdlineLen}`);
  assert.ok(cmdlineLen < WINDOWS_CMDLINE_LIMIT);
  assert.ok(!plan.args.some((a) => a.includes('AAAA')), 'prompt payload leaked into argv');

  // The payload is on disk, byte-exact, and reachable.
  assert.equal(await fs.readFile(plan.promptFile, 'utf8'), huge);
  assert.equal(plan.stdin, 'file');

  // CONTROL: the ORIGINAL builder really does blow the limit with this same payload.
  const origLen = ['codex', ...originalArgs({ cwd: dir, prompt: huge })].join(' ').length;
  assert.ok(
    origLen > WINDOWS_CMDLINE_LIMIT,
    `control broken: original cmdline was only ${origLen}, expected > ${WINDOWS_CMDLINE_LIMIT}`
  );
});

test('codex: prompt file round-trips unicode and newlines byte-exactly', async () => {
  const dir = await tmp();
  const prompt = 'line1\nline2\r\ntabs\tand "quotes" and \'apostrophes\'\nunicode: \u00e9\u4e2d\u6587\n';
  const file = await writePromptFile(prompt, { dir });
  assert.equal(await fs.readFile(file, 'utf8'), prompt);
  assert.equal(path.dirname(file), dir);
});

test('codex: writePromptFile handles empty/nullish prompts and never collides', async () => {
  const dir = await tmp();
  assert.equal(await fs.readFile(await writePromptFile('', { dir }), 'utf8'), '');
  assert.equal(await fs.readFile(await writePromptFile(null, { dir }), 'utf8'), '');
  const files = await Promise.all(Array.from({ length: 20 }, () => writePromptFile('x', { dir })));
  assert.equal(new Set(files).size, 20, 'prompt file names collided');
});

// ======================== DEFECT (b): --ignore-user-config must be present =====================

test('codex: DEFECT (b) - --ignore-user-config is emitted BY DEFAULT', () => {
  const args = buildCodexExecArgs({ cwd: '/w' });
  assert.ok(args.includes('--ignore-user-config'), `missing from ${JSON.stringify(args)}`);
  // It must precede the prompt token so it is parsed as an option, not an argument.
  assert.ok(args.indexOf('--ignore-user-config') < args.indexOf(PROMPT_FROM_STDIN));

  // CONTROL: the ORIGINAL builder never emitted it - that is the defect being closed.
  assert.ok(!originalArgs({ cwd: '/w', prompt: 'p' }).includes('--ignore-user-config'));
});

test('codex: --ignore-user-config is opt-out-able but never silently absent', () => {
  assert.ok(!buildCodexExecArgs({ cwd: '/w', ignoreUserConfig: false }).includes('--ignore-user-config'));
  assert.ok(buildCodexExecArgs({ cwd: '/w', ignoreUserConfig: true }).includes('--ignore-user-config'));
});

// ================================== argv composition ==========================================

test('codex: option flags are threaded through', () => {
  const args = buildCodexExecArgs({
    cwd: '/w',
    ephemeral: true,
    skipGitRepoCheck: true,
    model: 'gpt-5.1-codex',
    configOverrides: ['a=1', 'b=2', '', null]
  });
  assert.ok(args.includes('--ephemeral'));
  assert.ok(args.includes('--skip-git-repo-check'));
  assert.deepEqual(args.slice(args.indexOf('-m'), args.indexOf('-m') + 2), ['-m', 'gpt-5.1-codex']);
  assert.equal(args.filter((a) => a === '-c').length, 2, 'empty/null overrides must be skipped');
  assert.ok(args.includes('a=1') && args.includes('b=2'));
  assert.deepEqual(args.slice(args.indexOf('-C'), args.indexOf('-C') + 2), ['-C', '/w']);
  assert.ok(args.includes('--json'));
});

test('codex: --json is suppressible and -o is opt-in only', () => {
  assert.ok(!buildCodexExecArgs({ cwd: '/w', json: false }).includes('--json'));
  assert.ok(!buildCodexExecArgs({ cwd: '/w' }).includes('-o'));
  const args = buildCodexExecArgs({ cwd: '/w', outputLastMessage: '/tmp/last.txt' });
  assert.deepEqual(args.slice(args.indexOf('-o'), args.indexOf('-o') + 2), ['-o', '/tmp/last.txt']);
});

test('codex: resume is placed as a subcommand before the stdin token', () => {
  const id = '11111111-2222-4333-8444-555555555555';
  const args = buildCodexExecArgs({ cwd: '/w', sessionId: id });
  const at = args.indexOf('resume');
  assert.ok(at > 0, 'resume subcommand missing');
  assert.equal(args[at + 1], id);
  assert.equal(args.at(-1), PROMPT_FROM_STDIN);
  assert.ok(at < args.indexOf(PROMPT_FROM_STDIN));
});

test('codex: ephemeral suppresses resume (they are mutually exclusive)', () => {
  const args = buildCodexExecArgs({ cwd: '/w', sessionId: 'abc', ephemeral: true });
  assert.ok(!args.includes('resume'));
  assert.ok(args.includes('--ephemeral'));
});

test('codex: argv always starts with the exec subcommand', () => {
  assert.equal(buildCodexExecArgs({ cwd: '/w' })[0], 'exec');
});

// ============================== resolveCodexInvocation ========================================

test('codex: CODEX_CLI_BIN override wins', async () => {
  const r = await resolveCodexInvocation({ env: { CODEX_CLI_BIN: '/opt/bin/codex' }, platform: 'linux' });
  assert.deepEqual(r, { command: '/opt/bin/codex', args: [], shell: false });
});

test('codex: a .cmd shim on Windows requires shell:true', async () => {
  const r = await resolveCodexInvocation({ env: { CODEX_CLI_BIN: 'C:\\tools\\codex.CMD' }, platform: 'win32' });
  assert.equal(r.command, 'C:\\tools\\codex.CMD');
  assert.equal(r.shell, true, 'a .cmd shim cannot be spawned without a shell');

  const exe = await resolveCodexInvocation({ env: { CODEX_CLI_BIN: 'C:\\tools\\codex.exe' }, platform: 'win32' });
  assert.equal(exe.shell, false);

  // ...and never on POSIX, where shell:true would be a needless injection surface.
  const posix = await resolveCodexInvocation({ env: { CODEX_CLI_BIN: '/x/codex.cmd' }, platform: 'linux' });
  assert.equal(posix.shell, false);
});

test('codex: non-Windows resolves to bare `codex` on PATH', async () => {
  assert.deepEqual(await resolveCodexInvocation({ env: {}, platform: 'linux' }), { command: 'codex', args: [], shell: false });
  assert.deepEqual(await resolveCodexInvocation({ env: {}, platform: 'darwin' }), { command: 'codex', args: [], shell: false });
});

test('codex: Windows finds the npm-installed codex.js and prefers the BUNDLED node.exe', async () => {
  const appData = await tmp();
  const binDir = path.join(appData, 'npm', 'node_modules', '@openai', 'codex', 'bin');
  await fs.mkdir(binDir, { recursive: true });
  const scriptPath = path.join(binDir, 'codex.js');
  await fs.writeFile(scriptPath, '// stub\n', 'utf8');

  // No bundled node.exe yet -> falls back to the running node.
  const withoutBundled = await resolveCodexInvocation({ env: { APPDATA: appData }, platform: 'win32', nodeExecutable: '/run/node' });
  assert.deepEqual(withoutBundled, { command: '/run/node', args: [scriptPath], shell: false });

  // Bundled node.exe present -> it wins.
  const bundled = path.join(appData, 'npm', 'node.exe');
  await fs.writeFile(bundled, 'stub', 'utf8');
  const withBundled = await resolveCodexInvocation({ env: { APPDATA: appData }, platform: 'win32', nodeExecutable: '/run/node' });
  assert.deepEqual(withBundled, { command: bundled, args: [scriptPath], shell: false });
});

test('codex: Windows falls back to USERPROFILE, then to codex.exe', async () => {
  const home = await tmp();
  const binDir = path.join(home, 'AppData', 'Roaming', 'npm', 'node_modules', '@openai', 'codex', 'bin');
  await fs.mkdir(binDir, { recursive: true });
  await fs.writeFile(path.join(binDir, 'codex.js'), '// stub\n', 'utf8');
  const viaProfile = await resolveCodexInvocation({ env: { USERPROFILE: home }, platform: 'win32', nodeExecutable: '/run/node' });
  assert.deepEqual(viaProfile.args, [path.join(binDir, 'codex.js')]);

  const empty = await tmp();
  const none = await resolveCodexInvocation({ env: { APPDATA: empty, USERPROFILE: empty }, platform: 'win32' });
  assert.deepEqual(none, { command: 'codex.exe', args: [], shell: false });
});

// ==================================== the composed plan =======================================

test('codex: createCodexExecPlan emits a complete, spawn-ready plan carrying BOTH fixes', async () => {
  const dir = await tmp();
  const plan = await createCodexExecPlan({
    prompt: 'review this',
    workspaceDir: dir,
    promptDir: dir,
    env: { CODEX_CLI_BIN: '/opt/bin/codex' },
    platform: 'linux',
    model: 'gpt-5.1-codex',
    skipGitRepoCheck: true
  });

  assert.equal(plan.command, '/opt/bin/codex');
  assert.equal(plan.shell, false);
  assert.equal(plan.cwd, path.resolve(dir));
  assert.equal(plan.stdin, 'file');
  assert.ok(plan.args.includes('--ignore-user-config'), 'fix (b) lost in the composed plan');
  assert.equal(plan.args.at(-1), PROMPT_FROM_STDIN, 'fix (a) lost in the composed plan');
  assert.ok(!plan.args.includes('review this'), 'prompt leaked into argv');
  assert.equal(await fs.readFile(plan.promptFile, 'utf8'), 'review this');
  assert.deepEqual(plan.args.slice(plan.args.indexOf('-C'), plan.args.indexOf('-C') + 2), ['-C', path.resolve(dir)]);
});

test('codex: the plan prepends the resolved interpreter args before the exec args', async () => {
  const appData = await tmp();
  const binDir = path.join(appData, 'npm', 'node_modules', '@openai', 'codex', 'bin');
  await fs.mkdir(binDir, { recursive: true });
  const scriptPath = path.join(binDir, 'codex.js');
  await fs.writeFile(scriptPath, '// stub\n', 'utf8');

  const plan = await createCodexExecPlan({
    prompt: 'p',
    workspaceDir: appData,
    promptDir: appData,
    env: { APPDATA: appData },
    platform: 'win32',
    nodeExecutable: '/run/node'
  });
  assert.equal(plan.args[0], scriptPath, 'interpreter script must come first');
  assert.equal(plan.args[1], 'exec');
});

test('codex: createCodexExecPlan mints its own temp dir when none is given', async () => {
  const plan = await createCodexExecPlan({ prompt: 'p', workspaceDir: await tmp(), env: {}, platform: 'linux' });
  assert.equal(await fs.readFile(plan.promptFile, 'utf8'), 'p');
  await fs.rm(path.dirname(plan.promptFile), { recursive: true, force: true });
});

test('codex: resolveCodexInvocation with empty env on win32 falls through to codex.exe', async () => {
  const r = await resolveCodexInvocation({ env: {}, platform: 'win32', nodeExecutable: 'node-x' });
  assert.deepEqual(r, { command: 'codex.exe', args: [], shell: false });
});

test('codex: a script-path base without a bundled node.exe uses the given node executable', async () => {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), 'toolslib-codex-base-'));
  try {
    const script = path.join(base, 'npm', 'node_modules', '@openai', 'codex', 'bin', 'codex.js');
    await fs.mkdir(path.dirname(script), { recursive: true });
    await fs.writeFile(script, '', 'utf8');
    const r = await resolveCodexInvocation({
      env: { APPDATA: base },
      platform: 'win32',
      nodeExecutable: 'given-node',
    });
    assert.equal(r.command, 'given-node', 'no bundled node.exe -> caller-supplied executable');
    assert.deepEqual(r.args, [script]);

    // Once a bundled node.exe appears next to the npm tree, it wins.
    await fs.writeFile(path.join(base, 'npm', 'node.exe'), '', 'utf8');
    const r2 = await resolveCodexInvocation({
      env: { APPDATA: base },
      platform: 'win32',
      nodeExecutable: 'given-node',
    });
    assert.equal(r2.command, path.join(base, 'npm', 'node.exe'));
  } finally {
    await fs.rm(base, { recursive: true, force: true });
  }
});

test('codex: CODEX_CLI_BIN shell flag follows platform AND extension', async () => {
  assert.deepEqual(
    await resolveCodexInvocation({ env: { CODEX_CLI_BIN: 'C:\\tools\\codex.cmd' }, platform: 'win32' }),
    { command: 'C:\\tools\\codex.cmd', args: [], shell: true },
  );
  assert.deepEqual(
    await resolveCodexInvocation({ env: { CODEX_CLI_BIN: '/usr/local/bin/codex' }, platform: 'linux' }),
    { command: '/usr/local/bin/codex', args: [], shell: false },
  );
  assert.deepEqual(
    await resolveCodexInvocation({ env: { CODEX_CLI_BIN: 'C:\\tools\\codex.exe' }, platform: 'win32' }),
    { command: 'C:\\tools\\codex.exe', args: [], shell: false },
  );
  // POSIX never needs the .cmd shim, whatever the extension.
  assert.deepEqual(
    await resolveCodexInvocation({ env: { CODEX_CLI_BIN: '/opt/codex.cmd' }, platform: 'linux' }),
    { command: '/opt/codex.cmd', args: [], shell: false },
  );
});

test('codex: buildCodexExecArgs covers every optional and tolerates bad config entries', () => {
  // All defaults on.
  assert.deepEqual(buildCodexExecArgs({ cwd: '/w' }), [
    'exec', '--ignore-user-config', '--json', '-C', '/w', '-',
  ]);
  // Everything on/off at once; ephemeral suppresses resume even with a sessionId.
  assert.deepEqual(
    buildCodexExecArgs({
      cwd: '/w',
      ephemeral: true,
      skipGitRepoCheck: true,
      model: 'gpt-x',
      configOverrides: [null, '', 'x=1'],
      ignoreUserConfig: false,
      json: false,
      outputLastMessage: '/out.txt',
      sessionId: 's1',
    }),
    ['exec', '--ephemeral', '--skip-git-repo-check', '-m', 'gpt-x', '-c', 'x=1', '-o', '/out.txt', '-C', '/w', '-'],
  );
  // resume appears only when NOT ephemeral and a sessionId is given; non-array overrides are ignored.
  assert.deepEqual(
    buildCodexExecArgs({ sessionId: 's1', configOverrides: 'not-an-array' }),
    ['exec', '--ignore-user-config', '--json', 'resume', 's1', '-'],
  );
});

test('codex: writePromptFile falls back to its own mkdtemp dir when none is given', async () => {
  const file = await writePromptFile('body');
  try {
    assert.match(file, /[\\/]codex-prompt-/);
    assert.equal(await fs.readFile(file, 'utf8'), 'body');
  } finally {
    await fs.rm(path.dirname(file), { recursive: true, force: true });
  }
});

test('codex: createCodexExecPlan defaults the working directory to process.cwd', async () => {
  const plan = await createCodexExecPlan({ prompt: 'p', env: {}, platform: 'linux' });
  try {
    assert.equal(plan.cwd, path.resolve(process.cwd()));
  } finally {
    await fs.rm(path.dirname(plan.promptFile), { recursive: true, force: true });
  }
});
