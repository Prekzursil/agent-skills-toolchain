// tokens.test.mjs — unit tests for the pipeline (no network, no Figma).
// Run: node --test tests/  (from the skill dir)
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { readFileSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import {
  inferType, flatten, unflatten, aliasTarget, nameToPath, cssRefToAlias,
} from "../lib.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILL = join(HERE, "..");
const FIX = join(SKILL, "fixtures");
const run = (script, args) =>
  execFileSync("node", [join(SKILL, script), ...args], { encoding: "utf8" });
// run a script, capturing stdout (the terminal-state marker) AND stderr (the
// JSON findings report) regardless of exit code. `ok` is false when the CLI
// exited non-zero. Used to assert each validator's rule id by name.
const runFull = (script, args) => {
  try {
    const stdout = execFileSync("node", [join(SKILL, script), ...args],
      { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    return { ok: true, stdout, stderr: "" };
  } catch (e) {
    return { ok: false, stdout: String(e.stdout ?? ""), stderr: String(e.stderr ?? "") };
  }
};

// ---- lib --------------------------------------------------------------
test("inferType maps raw values to DTCG types", () => {
  assert.equal(inferType("#2563eb"), "color");
  assert.equal(inferType("rgba(0,0,0,0.1)"), "color");
  assert.equal(inferType("16px"), "dimension");
  assert.equal(inferType("200ms"), "duration");
  assert.equal(inferType('"Inter", sans-serif'), "fontFamily");
  assert.equal(inferType("1.5"), "number");
  assert.equal(inferType("{color.primary.500}"), null); // alias -> referent type
});

test("flatten resolves inherited group $type", () => {
  const flat = flatten(JSON.parse(readFileSync(join(FIX, "before.tokens.json"), "utf8")));
  assert.equal(flat.get("color.primary.500").type, "color"); // inherited from group
  assert.equal(flat.get("spacing.1").type, "dimension");
  assert.equal(flat.get("color.action.default").value, "{color.primary.500}");
});

test("unflatten is the inverse of flatten", () => {
  const tree = JSON.parse(readFileSync(join(FIX, "before.tokens.json"), "utf8"));
  const round = unflatten([...flatten(tree).entries()]);
  assert.deepEqual(flatten(round), flatten(tree));
});

test("css var() ref becomes a DTCG alias", () => {
  assert.equal(cssRefToAlias("var(--color-primary-500)"), "{color.primary.500}");
  assert.equal(nameToPath("--color-primary-500"), "color.primary.500");
  assert.equal(aliasTarget("{a.b}"), "a.b");
  assert.equal(aliasTarget("#fff"), null);
});

// ---- extract ----------------------------------------------------------
test("extract_tokens lifts CSS custom properties to DTCG", () => {
  const out = run("extract_tokens.mjs", ["--css", join(FIX, "sample.css")]);
  assert.match(out, /SUCCESS:design-tokens-extract \d+/);
  const json = JSON.parse(out.slice(0, out.lastIndexOf("\n", out.lastIndexOf("SUCCESS"))));
  assert.equal(json.color.primary["500"].$value, "#2563eb");
  assert.equal(json.color.primary["500"].$type, "color");
  assert.equal(json.color.action.default.$value, "{color.primary.500}"); // var() -> alias
  assert.equal(json.duration.fast.$type, "duration");
});

// ---- validate (all FIVE DTCG round-trip rules the SKILL.md claims) -----
// Every validator gets an explicit assertion that its rule id appears in the
// JSON findings report (stderr). The five: missing-type, bad-alias,
// alias-cycle, raw-hex-in-code, reserved-misuse.
const writeTmp = (name, obj) => {
  const f = join(mkdtempSync(join(tmpdir(), "dtp-")), name);
  writeFileSync(f, JSON.stringify(obj));
  return f;
};

test("validate passes a clean DTCG file", () => {
  const out = run("validate_tokens.mjs", ["--file", join(FIX, "before.tokens.json")]);
  assert.match(out, /SUCCESS:design-tokens-validate/);
});

test("validate flags bad-alias (a dangling {group.token} reference)", () => {
  const bad = writeTmp("bad-alias.json", {
    color: { $type: "color", a: { $value: "{color.missing}" } },
  });
  const r = runFull("validate_tokens.mjs", ["--file", bad]);
  assert.equal(r.ok, false);
  assert.match(r.stdout, /FAILED:design-tokens-validate/);
  assert.match(r.stderr, /"rule": "bad-alias"/);
});

test("validate flags missing-type (a leaf with no resolvable $type)", () => {
  const bad = writeTmp("missing-type.json", { weird: { x: { $value: "??" } } });
  const r = runFull("validate_tokens.mjs", ["--file", bad]);
  assert.equal(r.ok, false);
  assert.match(r.stdout, /FAILED:design-tokens-validate/);
  assert.match(r.stderr, /"rule": "missing-type"/);
});

test("validate flags alias-cycle (a -> b -> a)", () => {
  const bad = writeTmp("alias-cycle.json", {
    color: { $type: "color", a: { $value: "{color.b}" }, b: { $value: "{color.a}" } },
  });
  const r = runFull("validate_tokens.mjs", ["--file", bad]);
  assert.equal(r.ok, false);
  assert.match(r.stdout, /FAILED:design-tokens-validate/);
  assert.match(r.stderr, /"rule": "alias-cycle"/);
});

test("validate flags reserved-misuse (an unknown $-prefixed key)", () => {
  const bad = writeTmp("reserved-misuse.json", {
    color: { $type: "color", a: { $value: "#ffffff", $foo: "nope" } },
  });
  const r = runFull("validate_tokens.mjs", ["--file", bad]);
  assert.equal(r.ok, false);
  assert.match(r.stdout, /FAILED:design-tokens-validate/);
  assert.match(r.stderr, /"rule": "reserved-misuse"/);
});

test("validate warns on raw-hex-in-code, and --strict promotes it to a failure", () => {
  const bad = writeTmp("raw-hex.json", {
    color: { $type: "color", brand: { $value: "#2563eb" }, accent: { $value: "#2563eb" } },
  });
  // default: a warning only -> the clean gate still passes.
  assert.match(run("validate_tokens.mjs", ["--file", bad]), /SUCCESS:design-tokens-validate/);
  // --strict: the same raw-hex warning now fails the gate.
  const r = runFull("validate_tokens.mjs", ["--file", bad, "--strict"]);
  assert.equal(r.ok, false);
  assert.match(r.stdout, /FAILED:design-tokens-validate/);
  assert.match(r.stderr, /"rule": "raw-hex-in-code"/);
});

// ---- diff (the revert surface) ----------------------------------------
test("token_diff reports add/remove/change and writes a revert overlay", () => {
  const dir = mkdtempSync(join(tmpdir(), "dtp-"));
  const diffFile = join(dir, "diff.json");
  const revertFile = join(dir, "revert.json");
  const out = run("token_diff.mjs", [
    "--before", join(FIX, "before.tokens.json"),
    "--after", join(FIX, "after.tokens.json"),
    "--out", diffFile, "--revert", revertFile,
  ]);
  assert.match(out, /SUCCESS:design-tokens-diff 1\+0\+1/); // 1 added (spacing.3), 1 changed (primary.500)
  const diff = JSON.parse(readFileSync(diffFile, "utf8"));
  assert.equal(diff.summary.added, 1);
  assert.equal(diff.summary.changed, 1);
  assert.equal(diff.changed[0].path, "color.primary.500");
  // the revert overlay restores the OLD primary.500 value
  const revert = JSON.parse(readFileSync(revertFile, "utf8"));
  assert.equal(revert.color.primary["500"].$value, "#2563eb");
  assert.deepEqual(diff.revertDeletes, ["spacing.3"]); // added token a revert must delete
});
