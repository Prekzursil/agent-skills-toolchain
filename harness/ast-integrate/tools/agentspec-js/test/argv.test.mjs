/** ARGV transport safety: the prompt never reaches the command line. */

import assert from "node:assert/strict";
import test from "node:test";

import { capture } from "./helpers.mjs";

import {
  ArgvTooLong,
  MIN_SUBSTRING_SCAN_LEN,
  PolicyViolation,
  PROMPT_TRANSPORTS,
  PromptOnArgv,
  WINDOWS_CMDLINE_CAP,
  buildArgv,
  buildForRail,
  missingHardening,
  promptOnArgv,
  railSpec,
  renderCmdline,
} from "../src/argv.mjs";

const LONG_PROMPT = "p".repeat(MIN_SUBSTRING_SCAN_LEN);

test("the constants match the measured Windows limits", () => {
  assert.equal(WINDOWS_CMDLINE_CAP, 32767);
  assert.equal(MIN_SUBSTRING_SCAN_LEN, 64);
  assert.deepEqual([...PROMPT_TRANSPORTS], ["file", "stdin"]);
});

test("the file transport puts a PATH on argv, never the prompt", () => {
  const plan = buildArgv({
    exe: "codex",
    prompt: "a long body ".repeat(50),
    transport: "file",
    flags: ["--ignore-user-config"],
    promptFlag: "--prompt-file",
    promptPath: "/tmp/p.txt",
  });
  assert.deepEqual([...plan.argv], ["codex", "--ignore-user-config", "--prompt-file", "/tmp/p.txt"]);
  assert.equal(plan.stdinPayload, null);
  assert.equal(plan.promptTransport, "file");
  assert.equal(plan.cmdlineLen, renderCmdline(plan.argv).length);
});

test("the stdin transport carries the prompt off argv entirely", () => {
  const plan = buildArgv({ exe: "codex", prompt: LONG_PROMPT, transport: "stdin" });
  assert.deepEqual([...plan.argv], ["codex"]);
  assert.equal(plan.stdinPayload, LONG_PROMPT);
  assert.equal(plan.promptPath, null);
});

test("empty exe / prompt and an unknown transport are refused", () => {
  assert.throws(() => buildArgv({ exe: "", prompt: "p", transport: "stdin" }), /exe must be non-empty/u);
  assert.throws(() => buildArgv({ exe: "x", prompt: "", transport: "stdin" }), /prompt must be non-empty/u);
  // "argv" is deliberately NOT a transport: prompt-on-argv is a hard policy violation.
  assert.throws(() => buildArgv({ exe: "x", prompt: "p", transport: "argv" }), /transport must be one of/u);
});

test("the file transport requires both its flag and its path", () => {
  assert.throws(
    () => buildArgv({ exe: "x", prompt: "p", transport: "file", promptPath: "/tmp/p" }),
    /promptFlag is required/u,
  );
  assert.throws(
    () => buildArgv({ exe: "x", prompt: "p", transport: "file", promptFlag: "--f" }),
    /promptPath is required/u,
  );
});

test("the stdin transport refuses a stray flag or path", () => {
  assert.throws(
    () => buildArgv({ exe: "x", prompt: "p", transport: "stdin", promptPath: "/tmp/p" }),
    /promptPath must be null/u,
  );
  assert.throws(
    () => buildArgv({ exe: "x", prompt: "p", transport: "stdin", promptFlag: "--f" }),
    /promptFlag must be null/u,
  );
});

test("a prompt smuggled onto argv is caught and is unrecoverable by retry", () => {
  const caught = capture(() =>
      buildArgv({
        exe: "codex",
        prompt: "the-body",
        transport: "file",
        flags: ["the-body"],
        promptFlag: "--prompt-file",
        promptPath: "/tmp/p",
      }));
  assert.ok(caught instanceof PromptOnArgv, `expected PromptOnArgv, got ${caught}`);
  assert.equal(caught.reason, "policy-violation");
});

test("the three prompt-detection rules, in order of precision", () => {
  // 1. bare equality, at any length
  assert.ok(promptOnArgv("x", "x"));
  // 2. the --flag=<body> / --flag:<body> shape, at any length
  assert.ok(promptOnArgv("--message=body", "body"));
  assert.ok(promptOnArgv("--message:body", "body"));
  // 3. bare containment ONLY at or above the threshold
  assert.ok(promptOnArgv(`prefix${LONG_PROMPT}suffix`, LONG_PROMPT));
  assert.ok(!promptOnArgv("prefix-p-suffix", "p"));
  // The measured false positive this threshold exists for: a one-char prompt hiding inside a
  // legitimate flag token. A guard that fires in the good state is as broken as one that stays
  // silent in the bad state.
  assert.ok(!promptOnArgv("--output-last-message", "a"));
});

test("the threshold boundary is exact", () => {
  const atThreshold = "q".repeat(MIN_SUBSTRING_SCAN_LEN);
  const belowThreshold = "q".repeat(MIN_SUBSTRING_SCAN_LEN - 1);
  assert.ok(promptOnArgv(`--x=${atThreshold}!`, atThreshold));
  assert.ok(!promptOnArgv(`--x${belowThreshold}!`, belowThreshold));
});

test("an over-long command line is refused with the win-arg-limit reason", () => {
  const caught = capture(() =>
      buildArgv({
        exe: "codex",
        prompt: "body",
        transport: "stdin",
        flags: ["--flag", "z".repeat(100)],
        cap: 50,
      }));
  assert.ok(caught instanceof ArgvTooLong, `expected ArgvTooLong, got ${caught}`);
  assert.equal(caught.reason, "win-arg-limit");
  assert.equal(caught.cap, 50);
  assert.ok(caught.cmdlineLen > 50);
});

test("renderCmdline quotes what Windows would quote", () => {
  assert.equal(renderCmdline(["a", "b c", ""]), 'a "b c" ""');
  assert.equal(renderCmdline(["plain"]), "plain");
});

test("missingHardening matches WHOLE elements, never substrings", () => {
  assert.deepEqual(missingHardening(["codex", "--ignore-user-config"], ["--ignore-user-config"]), []);
  // The measured near-miss class: a longer flag must NOT satisfy a shorter required one.
  assert.deepEqual(
    missingHardening(["codex", "--ignore-user-configuration"], ["--ignore-user-config"]),
    ["--ignore-user-config"],
  );
});

test("buildForRail injects the hardening flags and then VERIFIES them", () => {
  const rail = railSpec({
    name: "codex",
    exe: "codex",
    hardening: ["--ignore-user-config"],
    promptTransport: "file",
    promptFlag: "--prompt-file",
  });
  const plan = buildForRail(rail, { prompt: "body", promptPath: "/tmp/p" });
  assert.ok(plan.argv.includes("--ignore-user-config"));
  assert.equal(plan.promptPath, "/tmp/p");
});

test("buildForRail handles a stdin rail", () => {
  const rail = railSpec({ name: "stdin-rail", exe: "agent", promptTransport: "stdin" });
  const plan = buildForRail(rail, { prompt: "body" });
  assert.deepEqual([...plan.argv], ["agent"]);
  assert.equal(plan.stdinPayload, "body");
});

test("the hardening VERIFICATION fires when injection is switched off", () => {
  // `injectHardening: false` exists so a test can prove the check works; production callers
  // never pass it. This is the RED condition for the missing-flag guard.
  const rail = railSpec({ name: "codex", exe: "codex", hardening: ["--ignore-user-config"] });
  const caught = capture(() => buildForRail(rail, { prompt: "body", promptPath: "/tmp/p", injectHardening: false }));
  assert.ok(caught instanceof PolicyViolation, `expected PolicyViolation, got ${caught}`);
  assert.deepEqual(caught.missing, ["--ignore-user-config"]);
  assert.equal(caught.reason, "policy-violation");
});

test("a rail declaring an unknown transport is refused", () => {
  const rail = railSpec({ name: "bad", exe: "x", promptTransport: "argv" });
  assert.throws(() => buildForRail(rail, { prompt: "body" }), /declares an unknown transport/u);
});

test("railSpec defaults are the safe ones", () => {
  const rail = railSpec({ name: "r", exe: "e" });
  assert.deepEqual([...rail.hardening], []);
  assert.equal(rail.promptTransport, "file");
  assert.equal(rail.promptFlag, null);
  assert.equal(rail.cap, WINDOWS_CMDLINE_CAP);
  assert.ok(Object.isFrozen(rail));
});
