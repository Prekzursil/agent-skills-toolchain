// ORIGIN: tools/mcp/codex-orchestrator/src/orchestrator/codex.mjs:32-64 (resolveCodexInvocation)
//
// SURVIVED THE RETIREMENT because locating the Codex binary on Windows is hard-won and entirely
// independent of the ChatGPT-web architecture that was retired. Any future `codex exec` shell-out
// needs it: CODEX_CLI_BIN override -> %APPDATA%\npm\node_modules\@openai\codex\bin\codex.js driven
// by the npm-bundled node.exe -> codex.exe on PATH, plus the branch where a .cmd shim requires
// shell:true. The surrounding runCodexExec streaming/abort machinery was NOT carried: it had no
// surviving consumer and porting untested spawn plumbing would be a larger claim than this salvage
// can back.
//
// ============================================================================================
// TWO DEFECTS FROM THE ORIGIN ARE FIXED HERE. Neither is carried forward.
//
//  (a) PROMPT PASSED AS ARGV. Origin codex.mjs:91-92 read
//        // Prompt is an argument to avoid stdin edge cases.
//        args.push(String(prompt || ''));
//      On Windows CreateProcess caps the whole command line at 32,767 chars. This is
//      ledger-proven to have failed in production with payload_len=34472 -> os error 206,
//      killing the run. FIX: the prompt is written to a FILE and streamed to the child's stdin;
//      argv carries only the literal '-'. Verified against the installed CLI (codex-cli 0.145.0):
//        `codex exec --help` -> "[PROMPT] Initial instructions for the agent. If not provided as
//         an argument (or if `-` is used), instructions are read from stdin."
//      NOTE for anyone reaching for `--prompt-file`: that flag DOES NOT EXIST on the codex CLI.
//      It is a flag of a different local wrapper (codex-companion.mjs). stdin via '-' is the
//      real mechanism; a file plus a stdin stream is how you get both an unbounded payload and
//      an on-disk artifact you can re-read when a dispatch goes wrong.
//
//  (b) --ignore-user-config MISSING. It appeared NOWHERE in the repo. It is the documented #1
//      execution blocker for non-interactive Codex dispatch: without it the active MCP inventory
//      is loaded into the invocation and is what blows the arg limit in (a), and it also dodges
//      the typed --output-schema x active-MCP landmine. FIX: added, and ON BY DEFAULT.
//      Verified present on the installed CLI: `codex exec --help` ->
//        "--ignore-user-config  Do not load `$CODEX_HOME/config.toml`; auth still uses CODEX_HOME"
// ============================================================================================
//
// ADDITION beyond the two mandated fixes, disclosed rather than slipped in: buildCodexExecArgs
// accepts an optional `outputLastMessage` path (-o). Exit code 0 alone is NOT proof a dispatch
// produced a result; the AND-gate needs a last-message file that exists, is non-empty, and
// parses. The flag is optional and defaults to unset, so this changes nothing unless asked for.

import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';

async function pathExists(file) {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

/**
 * Locate the Codex CLI. Carried over verbatim from the origin - it was already correct.
 * Returns { command, args, shell } ready to prepend to the exec argv.
 */
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

/**
 * The literal argv token that tells `codex exec` to read the prompt from stdin.
 * The prompt payload itself must NEVER appear in argv - see defect (a).
 */
export const PROMPT_FROM_STDIN = '-';

/**
 * Build the `codex exec` argv. PURE - no filesystem, no spawn - so the two fixes are directly
 * unit-testable. The prompt is never an argument; argv ends with '-' (stdin).
 */
export function buildCodexExecArgs({
  cwd,
  sessionId = null,
  ephemeral = false,
  skipGitRepoCheck = false,
  model = null,
  configOverrides = [],
  ignoreUserConfig = true,
  json = true,
  outputLastMessage = null
} = {}) {
  const args = ['exec'];
  if (ignoreUserConfig) args.push('--ignore-user-config'); // DEFECT FIX (b)
  if (ephemeral) args.push('--ephemeral');
  if (skipGitRepoCheck) args.push('--skip-git-repo-check');
  if (model) args.push('-m', String(model));
  for (const entry of Array.isArray(configOverrides) ? configOverrides : []) {
    if (!entry) continue;
    args.push('-c', String(entry));
  }
  if (json) args.push('--json');
  if (outputLastMessage) args.push('-o', String(outputLastMessage));
  if (cwd) args.push('-C', String(cwd));
  if (!ephemeral && sessionId) args.push('resume', String(sessionId));

  // DEFECT FIX (a): the prompt is read from stdin. It is NEVER pushed into argv, so the payload
  // cannot contribute to the Windows 32,767-char CreateProcess limit.
  args.push(PROMPT_FROM_STDIN);
  return args;
}

/**
 * Persist a prompt to a file. Returns the absolute path. The file is the transport for the
 * stdin stream and doubles as the on-disk artifact for diagnosing a failed dispatch.
 */
export async function writePromptFile(prompt, { dir = null, prefix = 'codex-prompt' } = {}) {
  const targetDir = dir ? path.resolve(dir) : await fs.mkdtemp(path.join(os.tmpdir(), 'codex-prompt-'));
  await fs.mkdir(targetDir, { recursive: true });
  const file = path.join(targetDir, `${prefix}-${crypto.randomBytes(6).toString('hex')}.txt`);
  await fs.writeFile(file, String(prompt ?? ''), 'utf8');
  return file;
}

/**
 * Compose a complete, spawn-ready plan without running anything.
 *
 * The caller spawns { command, args, shell, cwd } with stdio[0] = 'pipe' and streams
 * promptFile into the child's stdin, e.g.:
 *
 *   const child = spawn(plan.command, plan.args, { cwd: plan.cwd, shell: plan.shell,
 *                                                  stdio: ['pipe', 'pipe', 'pipe'] });
 *   createReadStream(plan.promptFile).pipe(child.stdin);
 */
export async function createCodexExecPlan({
  prompt,
  workspaceDir,
  promptDir = null,
  env = process.env,
  platform = process.platform,
  nodeExecutable = process.execPath,
  ...execOptions
} = {}) {
  const cwd = path.resolve(workspaceDir || process.cwd());
  const invocation = await resolveCodexInvocation({ env, platform, nodeExecutable });
  const promptFile = await writePromptFile(prompt, { dir: promptDir });
  const execArgs = buildCodexExecArgs({ ...execOptions, cwd });

  return {
    command: invocation.command,
    args: [...invocation.args, ...execArgs],
    shell: invocation.shell,
    cwd,
    promptFile,
    stdin: 'file'
  };
}

// --- TST-0191: byte-exact argv-array invocation ------------------------------
// Spawns the given argv as an ARRAY (never a concatenated shell string) and
// returns the raw child streams. Argument bytes must survive exactly; the
// paired probe asserts that against the python echo child's hex report.
import { spawnSync as _tst0191SpawnSync } from 'node:child_process';

export function invokeArgv(argv, { timeout = 30000 } = {}) {
  if (!Array.isArray(argv) || argv.length === 0) {
    return { error: 'invokeArgv: argv must be a non-empty array' };
  }
  const [command, ...args] = argv.map(String);
  const res = _tst0191SpawnSync(command, args, { timeout, shell: false });
  if (res.error) {
    return { error: String(res.error), status: res.status ?? 1 };
  }
  return { status: res.status, stdout: res.stdout, stderr: res.stderr };
}

// --- TST-0189: file creation through the fs API, never through a shell ---------
// A document that contains PowerShell here-string terminator tokens or heredoc markers
// cannot be inlined into a shell file-creation command without the shell closing the
// literal early and parsing the remainder as commands. The write API takes the bytes as
// a Buffer and lands them verbatim; nothing about the payload ever reaches an argv or a
// shell parser.
import { realpathSync as _tst0189RealpathSync } from 'node:fs';
import { fileURLToPath as _tst0189FileURLToPath } from 'node:url';

export async function writeFileViaApi(dest, data) {
  const target = path.resolve(String(dest));
  const buf = Buffer.isBuffer(data) ? data : Buffer.from(String(data ?? ''), 'utf8');
  await fs.mkdir(path.dirname(target), { recursive: true });
  await fs.writeFile(target, buf);
  return {
    dest: target,
    bytes: buf.length,
    sha256: crypto.createHash('sha256').update(buf).digest('hex'),
    route: 'fs.writeFile',
    shell: false
  };
}

async function readStdinBytes() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks);
}

/** CLI: `node codex-invocation.mjs write <dest>` — payload bytes on stdin, JSON meta on stdout. */
export async function cliMain(argv) {
  const [verb, dest] = argv;
  if (verb !== 'write' || !dest) {
    process.stderr.write('usage: node codex-invocation.mjs write <dest>   (payload bytes on stdin)\n');
    return 2;
  }
  const meta = await writeFileViaApi(dest, await readStdinBytes());
  process.stdout.write(JSON.stringify(meta) + '\n');
  return 0;
}

function isMainModule() {
  try {
    if (!process.argv[1]) return false;
    return _tst0189RealpathSync(path.resolve(process.argv[1])) ===
      _tst0189RealpathSync(_tst0189FileURLToPath(import.meta.url));
  } catch {
    return false;
  }
}

if (isMainModule()) {
  cliMain(process.argv.slice(2)).then(
    (code) => { process.exitCode = code; },
    (err) => {
      process.stderr.write(`${(err && err.stack) || err}\n`);
      process.exitCode = 1;
    }
  );
}
