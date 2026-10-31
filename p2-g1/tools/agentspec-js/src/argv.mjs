/**
 * ARGV construction that REFUSES to place a prompt on the command line.
 *
 * The JS mirror of `agentspec/argv.py`. MEASURED FAILURE THIS EXISTS FOR: an inline prompt
 * produced `payload_len=34472` and killed a run with Windows `os error 206`. The Windows
 * `CreateProcess` command-line cap is 32,767 chars, measured via a libuv spawn sweep at
 * 32,745 OK -> 32,774 ENAMETOOLONG.
 *
 * `PROMPT_TRANSPORTS` deliberately has NO "argv" member — prompt-on-argv is a hard
 * `policy-violation`, not a configurable option. `test/crosslang.test.mjs` asserts every
 * constant here still equals the Python one, so widening it on one side alone fails the gate.
 *
 * `promptOnArgv` uses three rules in order of precision. A first draft used bare substring
 * containment at every length and FALSE-POSITIVED on a one-char prompt hiding inside
 * `--output-last-message`, i.e. a guard that blocked valid work. A detector that fires in the
 * good state is as broken as one that stays silent in the bad state.
 */

import { dumps as canonicalDumps } from "./canonical.mjs";
import { containsBlank, utf16Len } from "./wire.mjs";

/** Mirrors tools/glob-argv-guard/glob_argv_guard.py; the drift is gated by a test. */
export const WINDOWS_CMDLINE_CAP = 32767;

export const PROMPT_TRANSPORTS = Object.freeze(["file", "stdin"]);

/** Below this, only equality and the `=`/`:` shapes are checked (see the module docstring). */
export const MIN_SUBSTRING_SCAN_LEN = 64;

const VALUE_DELIMITERS = Object.freeze(["=", ":"]);

/** The prompt reached argv. Unrecoverable by retry — the caller must be fixed. */
export class PromptOnArgv extends Error {
  constructor(message) {
    super(message);
    this.name = "PromptOnArgv";
    this.reason = "policy-violation";
  }
}

/** The rendered command line exceeds the platform cap. */
export class ArgvTooLong extends Error {
  constructor(cmdlineLen, cap) {
    super(`win-arg-limit: command line is ${cmdlineLen} chars, cap is ${cap}`);
    this.name = "ArgvTooLong";
    this.reason = "win-arg-limit";
    this.cmdlineLen = cmdlineLen;
    this.cap = cap;
  }
}

/** A required hardening flag is absent from a non-interactive invocation. */
export class PolicyViolation extends Error {
  constructor(missing) {
    super(`policy-violation: missing hardening flags ${canonicalDumps(missing)}`);
    this.name = "PolicyViolation";
    this.reason = "policy-violation";
    this.missing = missing;
  }
}

/**
 * The declarative shape of a rail, so adding a rail is a config row, not new code.
 *
 * `hardening` is the load-bearing field: for a non-interactive codex call it holds
 * `--ignore-user-config`, whose absence blew the argv limit by pulling the whole active MCP
 * inventory onto the command line.
 */
export function railSpec({
  name,
  exe,
  hardening = [],
  promptTransport = "file",
  promptFlag = null,
  cap = WINDOWS_CMDLINE_CAP,
}) {
  return Object.freeze({
    name,
    exe,
    hardening: Object.freeze([...hardening]),
    promptTransport,
    promptFlag,
    cap,
  });
}

/** Render `argv` the way Windows would, so the length check measures the real thing. */
export function renderCmdline(argv) {
  return argv.map(quote).join(" ");
}

/** Build a dispatch plan, refusing any shape that could put the prompt on argv. */
export function buildArgv({
  exe,
  prompt,
  transport,
  flags = [],
  promptFlag = null,
  promptPath = null,
  cap = WINDOWS_CMDLINE_CAP,
}) {
  if (exe === "") {
    throw new RangeError("exe must be non-empty");
  }
  if (prompt === "") {
    throw new RangeError("prompt must be non-empty");
  }
  if (!PROMPT_TRANSPORTS.includes(transport)) {
    throw new RangeError(
      `transport must be one of ${JSON.stringify(PROMPT_TRANSPORTS)}, got ${JSON.stringify(transport)}`,
    );
  }

  let argv;
  let stdinPayload;
  if (transport === "file") {
    if (promptFlag === null) {
      throw new RangeError("promptFlag is required for the file transport");
    }
    if (promptPath === null) {
      throw new RangeError("promptPath is required for the file transport");
    }
    argv = [exe, ...flags, promptFlag, promptPath];
    stdinPayload = null;
  } else {
    if (promptPath !== null) {
      throw new RangeError("promptPath must be null for the stdin transport");
    }
    if (promptFlag !== null) {
      throw new RangeError("promptFlag must be null for the stdin transport");
    }
    argv = [exe, ...flags];
    stdinPayload = prompt;
  }

  for (const element of argv) {
    if (promptOnArgv(element, prompt)) {
      throw new PromptOnArgv(
        `the prompt (${utf16Len(prompt)} chars) appears in argv element ` +
          `${canonicalDumps([...element].slice(0, 40).join(""))}; ` +
          `route it to a file or stdin`,
      );
    }
  }

  const cmdlineLen = utf16Len(renderCmdline(argv));
  if (cmdlineLen > cap) {
    throw new ArgvTooLong(cmdlineLen, cap);
  }

  return Object.freeze({
    argv: Object.freeze(argv),
    promptTransport: transport,
    promptPath,
    stdinPayload,
    cmdlineLen,
  });
}

/**
 * Build a plan for `rail`, injecting and then VERIFYING its hardening flags.
 *
 * `injectHardening: false` exists so a test can prove the verification fires; production
 * callers never pass it. With it off, a rail declaring hardening raises `PolicyViolation`.
 */
export function buildForRail(rail, { prompt, promptPath = null, flags = [], injectHardening = true }) {
  if (!PROMPT_TRANSPORTS.includes(rail.promptTransport)) {
    throw new RangeError(
      `rail ${JSON.stringify(rail.name)} declares an unknown transport ` +
        `${JSON.stringify(rail.promptTransport)}`,
    );
  }
  const effective = injectHardening ? [...flags, ...rail.hardening] : [...flags];
  const missing = missingHardening([rail.exe, ...effective], rail.hardening);
  if (missing.length > 0) {
    throw new PolicyViolation(missing);
  }
  if (rail.promptTransport === "file") {
    return buildArgv({
      exe: rail.exe,
      prompt,
      transport: "file",
      flags: effective,
      promptFlag: rail.promptFlag,
      promptPath,
      cap: rail.cap,
    });
  }
  return buildArgv({ exe: rail.exe, prompt, transport: "stdin", flags: effective, cap: rail.cap });
}

/**
 * Which `required` flags are absent from `argv`, matched as WHOLE elements.
 *
 * Whole-element matching is deliberate: `--ignore-user-configuration` must not satisfy
 * `--ignore-user-config`. A substring matcher is the measured near-miss class.
 */
export function missingHardening(argv, required) {
  const present = new Set(argv);
  return required.filter((flag) => !present.has(flag));
}

/** True when `element` carries `prompt`. See the module docstring for the three rules. */
export function promptOnArgv(element, prompt) {
  if (element === prompt) {
    return true;
  }
  for (const delimiter of VALUE_DELIMITERS) {
    if (element.endsWith(delimiter + prompt)) {
      return true;
    }
  }
  return utf16Len(prompt) >= MIN_SUBSTRING_SCAN_LEN && element.includes(prompt);
}

function quote(element) {
  // `containsBlank`, not `/\s/u`: the regex class matches U+FEFF (which Python's
  // `str.isspace()` does not) and MISSES U+001C-U+001F and U+0085 (which it does), so the
  // two runtimes quoted DIFFERENT elements and therefore measured different cmdline lengths.
  if (element === "" || containsBlank(element)) {
    return `"${element}"`;
  }
  return element;
}
