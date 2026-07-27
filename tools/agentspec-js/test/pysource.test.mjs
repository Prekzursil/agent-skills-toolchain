/**
 * The drift gate's PARSER, validated against known-broken inputs before its silence is trusted.
 *
 * `crosslang.test.mjs` would pass vacuously if this extractor quietly returned an empty result
 * for a renamed or reshaped constant. Every failure mode therefore has an explicit test that
 * proves the parser THROWS rather than degrading — the same "validate the detector against a
 * known-broken state" discipline the Python package applies to its own determinism scanner.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  PythonSourceError,
  readIntConstant,
  readStringConstant,
  readTupleOfNamedStrings,
  readTupleOfStrings,
} from "../src/pysource.mjs";

const SAMPLE = [
  '"""A docstring that MENTIONS REASONS = ("decoy",) without declaring it."""',
  "",
  "REASONS: tuple[str, ...] = (",
  '    "budget-exhausted",',
  '    "env-missing",',
  ")",
  "",
  'BARE = ("a", "b")',
  "",
  "CAP = 32767",
  "CAP_WITH_SEPARATOR = 32_767",
  "NEGATIVE = -5",
  "CAP_COMMENTED = 32767  # trailing comment",
  'VERSION = "1"',
  'ESCAPED = "line\\nbreak\\ttab \\u00e9 \\\\ \\" done"',
  "NOT_AN_INT = 1 + 1",
  'NOT_A_STRING = f"x"',
  "",
  "E_ONE = \"code-one\"",
  'E_TWO = "code-two"',
  "GROUPED = (",
  "    E_ONE,",
  "    E_TWO,",
  ")",
  "",
  "EMPTY_TUPLE: tuple[str, ...] = ()",
  "UNTERMINATED = (",
  '    "x",',
  "NO_PAREN = 5",
].join("\n");

test("a tuple of string literals is read in declaration ORDER", () => {
  assert.deepEqual(readTupleOfStrings(SAMPLE, "REASONS"), ["budget-exhausted", "env-missing"]);
  assert.deepEqual(readTupleOfStrings(SAMPLE, "BARE"), ["a", "b"]);
});

test("a docstring MENTION is not mistaken for the declaration", () => {
  // The use-vs-mention trap: the sample's first line contains `REASONS = ("decoy",)` inside a
  // docstring. Anchoring to the start of a line is what keeps the real declaration authoritative.
  assert.ok(!readTupleOfStrings(SAMPLE, "REASONS").includes("decoy"));
});

test("an integer constant is read, with separators and comments tolerated", () => {
  assert.equal(readIntConstant(SAMPLE, "CAP"), 32767);
  assert.equal(readIntConstant(SAMPLE, "CAP_WITH_SEPARATOR"), 32767);
  assert.equal(readIntConstant(SAMPLE, "CAP_COMMENTED"), 32767);
  assert.equal(readIntConstant(SAMPLE, "NEGATIVE"), -5);
});

test("a string constant is read, with the escape forms these constants use", () => {
  assert.equal(readStringConstant(SAMPLE, "VERSION"), "1");
  assert.equal(readStringConstant(SAMPLE, "ESCAPED"), 'line\nbreak\ttab é \\ " done');
});

test("a tuple of NAME references is followed to each named constant", () => {
  assert.deepEqual(readTupleOfNamedStrings(SAMPLE, "GROUPED"), ["code-one", "code-two"]);
});

test("a missing constant THROWS instead of returning nothing", () => {
  assert.throws(() => readTupleOfStrings(SAMPLE, "NO_SUCH"), PythonSourceError);
  assert.throws(() => readIntConstant(SAMPLE, "NO_SUCH"), /no top-level assignment/u);
  assert.throws(() => readStringConstant(SAMPLE, "NO_SUCH"), /no top-level assignment/u);
  assert.throws(() => readTupleOfNamedStrings(SAMPLE, "NO_SUCH"), PythonSourceError);
});

test("an EMPTY tuple THROWS rather than reporting a vacuous match", () => {
  assert.throws(() => readTupleOfStrings(SAMPLE, "EMPTY_TUPLE"), /parsed to zero members/u);
  assert.throws(() => readTupleOfNamedStrings(SAMPLE, "EMPTY_TUPLE"), /names zero constants/u);
});

test("a tuple of names is refused by the literal reader, and vice versa", () => {
  assert.throws(() => readTupleOfStrings(SAMPLE, "GROUPED"), /parsed to zero members/u);
  assert.throws(() => readTupleOfNamedStrings(SAMPLE, "REASONS"), /names zero constants/u);
});

test("a non-tuple assignment THROWS when read as a tuple", () => {
  assert.throws(() => readTupleOfStrings(SAMPLE, "NO_PAREN"), /no tuple parenthesis follows/u);
});

test("an unterminated tuple THROWS", () => {
  assert.throws(() => readTupleOfStrings(SAMPLE, "UNTERMINATED"), /unterminated tuple literal/u);
});

test("a non-literal expression THROWS rather than being guessed at", () => {
  assert.throws(() => readIntConstant(SAMPLE, "NOT_AN_INT"), /not a plain integer literal/u);
  assert.throws(() => readStringConstant(SAMPLE, "NOT_A_STRING"), /not a plain string literal/u);
  assert.throws(() => readIntConstant(SAMPLE, "VERSION"), /not a plain integer literal/u);
});

test("an unsupported escape THROWS rather than being passed through", () => {
  assert.throws(
    () => readStringConstant('X = "a\\qb"', "X"),
    /unsupported escape/u,
    "an unknown escape must be a hard error, not a silent passthrough",
  );
});

test("a quote inside a tuple member does not end the group early", () => {
  const source = ['T = (', '    "a\\"b",', '    "c",', ")"].join("\n");
  assert.deepEqual(readTupleOfStrings(source, "T"), ['a"b', "c"]);
});

test("a single-quoted string inside the group is skipped without breaking the scan", () => {
  const source = ["T = (", "    'skipped',", '    "kept",', ")"].join("\n");
  assert.deepEqual(readTupleOfStrings(source, "T"), ["kept"]);
});

test("a nested parenthesis inside the group is balanced correctly", () => {
  const source = ['T = (', '    "a",', "    # (a comment with parens)", '    "b",', ")", 'AFTER = "x"'].join("\n");
  assert.deepEqual(readTupleOfStrings(source, "T"), ["a", "b"]);
});

test("a constant on the final line with no trailing newline still reads", () => {
  assert.equal(readIntConstant("LAST = 7", "LAST"), 7);
});

test("the error type is exported so a caller can match on it", () => {
  const failure = new PythonSourceError("boom");
  assert.equal(failure.name, "PythonSourceError");
  assert.ok(failure instanceof Error);
});
