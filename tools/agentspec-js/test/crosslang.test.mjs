/**
 * THE DRIFT GATE — every shared vocabulary is DERIVED from the Python package, not retyped.
 *
 * Acceptance criterion 7: "the closed taxonomy and PROMPT_TRANSPORTS are IMPORTED/derived from
 * one source, not retyped by hand in JS. Ship a test that fails if the two sets ever diverge."
 *
 * This file reads `tools/agentspec/agentspec/*.py` and asserts that every constant the JS
 * runtime declares still equals the Python declaration — members AND order, because order is
 * part of the contract for these tuples. The Python package stays the single source of truth;
 * `src/*.mjs` is a translation of it, and if either side moves alone, this goes red.
 *
 * The repo already runs this discipline in the other direction: `agentspec/tests/test_argv.py`
 * parses `tools/glob-argv-guard/glob_argv_guard.py` and asserts its own constant matches, so
 * neither file can invent a number. Same idea, opposite direction.
 *
 * The extractor itself is validated against KNOWN-BROKEN inputs in `pysource.test.mjs` — a
 * parser that silently returned `[]` would make every assertion below pass while measuring
 * nothing, which is precisely the failure class this package exists to defeat.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { MIN_SUBSTRING_SCAN_LEN, PROMPT_TRANSPORTS, WINDOWS_CMDLINE_CAP } from "../src/argv.mjs";
import { BLANK_CHARS, MAX_WIRE_INTEGER, MIN_WIRE_INTEGER, NON_PRINTABLE_ID_RANGES } from "../src/wire.mjs";
import { REJECTION_CODES } from "../src/canonical.mjs";
import { DISPATCH_VIOLATIONS } from "../src/dispatchpolicy.mjs";
import { ENVELOPE_FIELDS, STATUSES } from "../src/envelope.mjs";
import { CLAUSES } from "../src/oracle.mjs";
import { BACKGROUND_PHRASES } from "../src/progress.mjs";
import {
  readIntConstant,
  readStringConstant,
  readTupleOfNamedStrings,
  readTupleOfStrings,
} from "../src/pysource.mjs";
import { RATE_LIMIT_BASE_BACKOFF_MS, RATE_LIMIT_MAX_ATTEMPTS, RETRYABLE_ONCE } from "../src/retry.mjs";
import { BARRIER_POLICIES, ISOLATIONS, RECEIPT_FORMATS } from "../src/spec.mjs";
import { REASONS } from "../src/taxonomy.mjs";
import { VIOLATIONS } from "../src/validate.mjs";
import { SPEC_VERSION } from "../src/version.mjs";

const PY_ROOT = new URL("../../agentspec/agentspec/", import.meta.url);

function pySource(moduleName) {
  return readFileSync(fileURLToPath(new URL(`${moduleName}.py`, PY_ROOT)), "utf8");
}

/** Every tuple-of-strings constant, as `[pythonModule, pythonName, jsValue]`. */
const TUPLE_CONTRACTS = [
  ["taxonomy", "REASONS", REASONS],
  ["argv", "PROMPT_TRANSPORTS", PROMPT_TRANSPORTS],
  ["dispatchpolicy", "DISPATCH_VIOLATIONS", DISPATCH_VIOLATIONS],
  ["envelope", "ENVELOPE_FIELDS", ENVELOPE_FIELDS],
  ["envelope", "STATUSES", STATUSES],
  ["oracle", "CLAUSES", CLAUSES],
  ["progress", "BACKGROUND_PHRASES", BACKGROUND_PHRASES],
  ["retry", "RETRYABLE_ONCE", RETRYABLE_ONCE],
  ["spec", "RECEIPT_FORMATS", RECEIPT_FORMATS],
  ["spec", "BARRIER_POLICIES", BARRIER_POLICIES],
  ["spec", "ISOLATIONS", ISOLATIONS],
  ["validate", "VIOLATIONS", VIOLATIONS],
  ["wire", "BLANK_CHARS", BLANK_CHARS],
  ["wire", "NON_PRINTABLE_ID_RANGES", NON_PRINTABLE_ID_RANGES],
];

for (const [moduleName, constantName, jsValue] of TUPLE_CONTRACTS) {
  test(`${moduleName}.${constantName} matches the Python declaration exactly`, () => {
    const fromPython = readTupleOfStrings(pySource(moduleName), constantName);
    assert.deepEqual(
      [...jsValue],
      fromPython,
      `${constantName} drifted: the Python package is the source of truth, update src/`,
    );
  });
}

/** Every integer constant, as `[pythonModule, pythonName, jsValue]`. */
const INT_CONTRACTS = [
  ["argv", "WINDOWS_CMDLINE_CAP", WINDOWS_CMDLINE_CAP],
  ["argv", "MIN_SUBSTRING_SCAN_LEN", MIN_SUBSTRING_SCAN_LEN],
  ["retry", "RATE_LIMIT_MAX_ATTEMPTS", RATE_LIMIT_MAX_ATTEMPTS],
  ["retry", "RATE_LIMIT_BASE_BACKOFF_MS", RATE_LIMIT_BASE_BACKOFF_MS],
];

for (const [moduleName, constantName, jsValue] of INT_CONTRACTS) {
  test(`${moduleName}.${constantName} matches the Python integer exactly`, () => {
    assert.equal(readIntConstant(pySource(moduleName), constantName), jsValue);
  });
}

test("canonical.REJECTION_CODES matches the Python declaration exactly", () => {
  // Python declares this tuple by NAME reference, so each identifier is followed to its own
  // `E_* = "..."` declaration rather than scraped as a literal.
  const fromPython = readTupleOfNamedStrings(pySource("canonical"), "REJECTION_CODES");
  assert.deepEqual([...REJECTION_CODES], fromPython);
  assert.equal(fromPython.length, 8);
});

test("the shared wire rules are DERIVED from wire.py, not retyped", () => {
  // The two tables above are compared member-by-member by TUPLE_CONTRACTS. These are the
  // SEMANTIC invariants a member-equality check cannot state, and each one is a measured
  // divergence: a runtime whose blank set gains U+FEFF calls a two-BOM receipt EMPTY, and
  // one that loses U+001C calls a severed stream a six-clause SUCCESS.
  const fromPython = readTupleOfStrings(pySource("wire"), "BLANK_CHARS");
  assert.equal(fromPython.length, 29);
  assert.ok(!fromPython.includes("\ufeff"), "Python BLANK_CHARS gained the BOM");
  assert.ok(!BLANK_CHARS.includes("\ufeff"), "JS BLANK_CHARS gained the BOM");
  for (const char of ["\u001c", "\u001d", "\u001e", "\u001f", "\u0085"]) {
    assert.ok(fromPython.includes(char), `Python BLANK_CHARS lost U+${char.codePointAt(0).toString(16)}`);
    assert.ok(BLANK_CHARS.includes(char), `JS BLANK_CHARS lost U+${char.codePointAt(0).toString(16)}`);
  }
  // Python writes the bound as an EXPRESSION (`2**53 - 1`), so the value is asserted here
  // and the expression text is pinned by the regex — the same split canonical.py uses.
  assert.equal(MAX_WIRE_INTEGER, Number.MAX_SAFE_INTEGER);
  assert.equal(MIN_WIRE_INTEGER, -Number.MAX_SAFE_INTEGER);
  assert.match(pySource("wire"), /^MAX_WIRE_INTEGER = 2\*\*53 - 1$/mu);
  assert.match(pySource("wire"), /^MIN_WIRE_INTEGER = -\(2\*\*53 - 1\)$/mu);
  assert.equal(NON_PRINTABLE_ID_RANGES.length, 42);
});

test("SPEC_VERSION matches the Python package", () => {
  assert.equal(readStringConstant(pySource("__init__"), "SPEC_VERSION"), SPEC_VERSION);
});

test("MAX_DEPTH and the safe-integer bounds match the Python canonical module", async () => {
  const source = pySource("canonical");
  const { MAX_DEPTH, MAX_SAFE_INTEGER, MIN_SAFE_INTEGER } = await import("../src/canonical.mjs");
  assert.equal(readIntConstant(source, "MAX_DEPTH"), MAX_DEPTH);
  // Python writes these as expressions (`2**53 - 1`), so assert the VALUE the expression names
  // rather than re-parsing arithmetic — the expression text is checked separately below.
  assert.equal(MAX_SAFE_INTEGER, 2n ** 53n - 1n);
  assert.equal(MIN_SAFE_INTEGER, -(2n ** 53n - 1n));
  assert.match(source, /^MAX_SAFE_INTEGER = 2\*\*53 - 1$/mu);
  assert.match(source, /^MIN_SAFE_INTEGER = -\(2\*\*53 - 1\)$/mu);
});

test("PROMPT_TRANSPORTS has NO argv member on either side", () => {
  // Not a restatement of the tuple check: this pins the SEMANTIC invariant. Prompt-on-argv is a
  // hard policy-violation because it caused a measured `os error 206` at payload_len=34472, so
  // a future edit that adds "argv" to BOTH sides would pass the equality check and still be
  // wrong. This assertion is the one that catches that.
  const fromPython = readTupleOfStrings(pySource("argv"), "PROMPT_TRANSPORTS");
  assert.ok(!fromPython.includes("argv"), "Python PROMPT_TRANSPORTS gained an argv member");
  assert.ok(!PROMPT_TRANSPORTS.includes("argv"), "JS PROMPT_TRANSPORTS gained an argv member");
  assert.deepEqual([...PROMPT_TRANSPORTS], ["file", "stdin"]);
});

test("the closed taxonomy is sorted and free of duplicates on both sides", () => {
  const fromPython = readTupleOfStrings(pySource("taxonomy"), "REASONS");
  assert.deepEqual(fromPython, [...fromPython].sort());
  assert.equal(new Set(fromPython).size, fromPython.length);
  assert.equal(REASONS.length, 15);
});

test("every canonical rejection code resolves to the schema-invalid taxonomy member", async () => {
  const { family } = await import("../src/taxonomy.mjs");
  for (const code of REJECTION_CODES) {
    assert.equal(family(code), "schema-invalid", `${code} escaped the closed taxonomy`);
  }
  assert.equal(family("schema-invalidate"), "");
});

test("the drift gate is reading REAL files, not silently missing them", () => {
  // The whole file above would pass vacuously if `pySource` returned "" for everything, so the
  // preconditions are asserted rather than assumed.
  for (const moduleName of ["taxonomy", "argv", "canonical", "validate", "wire", "__init__"]) {
    assert.ok(pySource(moduleName).length > 100, `${moduleName}.py looks empty`);
  }
  assert.throws(() => pySource("no_such_module"), /ENOENT/u);
});
