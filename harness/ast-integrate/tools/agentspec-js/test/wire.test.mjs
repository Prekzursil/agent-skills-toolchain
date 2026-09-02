/**
 * The SHARED WIRE RULES, and a regression row for every measured Python<->JS divergence.
 *
 * This file is the JS half of `tools/agentspec/tests/test_wire.py`; the two assert the SAME
 * outcomes so a reader can diff them, and the executable cross-check is
 * `fixtures/behaviour-corpus.json`, which the parity oracle drives through BOTH runtimes and
 * byte-compares in CI. Unit tests alone cannot catch a divergence — the pre-existing suites were
 * at 100% line+branch on both sides while 78 behavioural cases disagreed — so these rows exist
 * to explain and localise a failure the corpus is what actually detects.
 */

import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import test from "node:test";

import { buildArgv, promptOnArgv, renderCmdline } from "../src/argv.mjs";
import { costPerSuccess, debit, ledger } from "../src/budget.mjs";
import { CanonicalJsonError, E_INVALID_UTF8, loadb } from "../src/canonical.mjs";
import { checkDispatch } from "../src/dispatchpolicy.mjs";
import { judge, railResult } from "../src/oracle.mjs";
import { missingFields, parseJsonObject } from "../src/receipt.mjs";
import { RATE_LIMIT_MAX_ATTEMPTS, rateLimitBackoffMs } from "../src/retry.mjs";
import { receiptSpec } from "../src/spec.mjs";
import { successLine } from "../src/terminal.mjs";
import * as wire from "../src/wire.mjs";

const JSON_SPEC = receiptSpec({ fmt: "json", requiredFields: ["summary"] });

/** Blank to Python `str.strip()` and NOT to JS `trim()` — measured by code-point sweep. */
const PY_ONLY_BLANK = ["\u001c", "\u001d", "\u001e", "\u001f", "\u0085"];

const ASTRAL = "\u{1f600}";

test("the blank set is closed and excludes the BOM", () => {
  assert.equal(wire.BLANK_CHARS.length, 29);
  assert.equal(new Set(wire.BLANK_CHARS).size, wire.BLANK_CHARS.length);
  assert.ok(!wire.BLANK_CHARS.includes("\ufeff"));
  assert.equal(wire.isBlank("\ufeff"), false);
  assert.equal(wire.containsBlank("\ufeff"), false);
  // The detector control: `trim()` DOES call it blank, which is the whole defect.
  assert.equal("\ufeff".trim(), "");
});

for (const char of PY_ONLY_BLANK) {
  const label = `U+${char.codePointAt(0).toString(16).padStart(4, "0")}`;
  test(`${label} is blank on BOTH runtimes now`, () => {
    assert.equal(wire.isBlank(char), true);
    assert.equal(wire.containsBlank(`a${char}b`), true);
    // The detector control: `trim()` does NOT strip it, which is the whole defect.
    assert.notEqual(char.trim(), "");
  });
}

test("isBlank treats the empty string as blank and real text as not", () => {
  assert.equal(wire.isBlank(""), true);
  assert.equal(wire.isBlank(" \t\n"), true);
  assert.equal(wire.isBlank(" x "), false);
  assert.equal(wire.containsBlank("abc"), false);
});

test("utf16Len counts code units, which is what CreateProcess counts", () => {
  assert.equal(wire.utf16Len("abc"), 3);
  assert.equal(wire.utf16Len(ASTRAL), 2);
  assert.equal(wire.utf16Len(ASTRAL.repeat(32)), 64);
  assert.equal([...ASTRAL.repeat(32)].length, 32);
});

test("sortedWire orders by UTF-16 code unit, the order Python must adopt", () => {
  assert.deepEqual([...wire.sortedWire([ASTRAL, "�"])], [ASTRAL, "�"]);
  assert.deepEqual([...wire.sortedWire(["b", "a"])], ["a", "b"]);
  assert.deepEqual([...wire.sortedWire(new Set(["b", "a", "b"]))], ["a", "b"]);
});

test("foldAsciiCase folds ASCII only, so no ICU table can move the contract", () => {
  assert.equal(wire.foldAsciiCase("TODO"), "todo");
  assert.equal(wire.foldAsciiCase("İ"), "İ");
  assert.equal(wire.foldAsciiCase("É"), "É");
});

test("isPrintableId is pinned to the range table, not to the engine's Unicode version", () => {
  assert.equal(wire.NON_PRINTABLE_ID_RANGES.length, 42);
  assert.equal(wire.isPrintableId("unit-1"), true);
  // U+088F is Cn on Unicode 16 and Lo on 17: the two runtimes disagreed on 4,803 such points.
  assert.equal(wire.isPrintableId("a࢏"), true);
  assert.equal(wire.isPrintableId("a౜"), true);
  assert.equal(wire.isPrintableId(""), false);
  assert.equal(wire.isPrintableId("a\u001b"), false);
  assert.equal(wire.isPrintableId("a b"), false);
  assert.equal(wire.isPrintableId("a\ufeff"), false);
  assert.equal(wire.isPrintableId("a\u{e0020}"), false);
});

test("the wire integer bound is the JS safe-integer bound", () => {
  assert.equal(wire.MAX_WIRE_INTEGER, Number.MAX_SAFE_INTEGER);
  assert.equal(wire.MIN_WIRE_INTEGER, Number.MIN_SAFE_INTEGER);
});

for (const [value, expected] of [
  [0, true],
  [-1, true],
  [Number.MAX_SAFE_INTEGER, true],
  [Number.MIN_SAFE_INTEGER, true],
  [Number.MAX_SAFE_INTEGER + 2, false],
  [2.5, false],
  [true, false],
  ["1", false],
  [null, false],
]) {
  test(`isWireInteger(${JSON.stringify(value)}) is ${expected}`, () => {
    assert.equal(wire.isWireInteger(value), expected);
  });
}

test("requireWireInteger returns the value, or throws WITHOUT rendering it", () => {
  assert.equal(wire.requireWireInteger(5, "micro"), 5);
  assert.throws(
    () => wire.requireWireInteger(2.5, "micro"),
    (caught) =>
      caught instanceof TypeError &&
      caught.message === "micro must be an integer in [-9007199254740991, 9007199254740991]",
  );
});

for (const [value, expected] of [
  [null, "null"],
  [true, "boolean"],
  [1, "number"],
  ["x", "string"],
  [[1], "array"],
  [{ a: 1 }, "object"],
]) {
  test(`jsonTypeName(${JSON.stringify(value)}) is ${expected}`, () => {
    assert.equal(wire.jsonTypeName(value), expected);
  });
}

// ------------------------------------------------------------------- regression rows

for (const char of PY_ONLY_BLANK) {
  const label = `U+${char.codePointAt(0).toString(16).padStart(4, "0")}`;
  test(`a receipt body of only ${label} is SEVERED, not a six-clause success`, () => {
    const verdict = judge(
      "u",
      railResult({ exitCode: 0, receiptBytes: Buffer.from(char, "utf8"), wallMs: 1 }),
      JSON_SPEC,
    );
    assert.equal(verdict.ok, false);
    assert.equal(verdict.reason, "receipt-empty");
  });

  test(`a unit id of only ${label} is refused, as Python refuses it`, () => {
    assert.throws(
      () =>
        judge(
          char,
          railResult({ exitCode: 0, receiptBytes: Buffer.from('{"summary":"x"}') }),
          JSON_SPEC,
        ),
      /unitId must be non-empty/u,
    );
  });

  test(`a required field of only ${label} is MISSING, as it is in Python`, () => {
    assert.deepEqual([...missingFields({ summary: char }, JSON_SPEC)], ["summary"]);
  });
}

test("a double-BOM receipt is not blank on either runtime", () => {
  const verdict = judge(
    "u",
    railResult({ exitCode: 0, receiptBytes: Buffer.from("\ufeff\ufeff", "utf8"), wallMs: 1 }),
    JSON_SPEC,
  );
  assert.equal(verdict.reason, "receipt-unparseable");
});

test("a BOM-only required field is PRESENT, as it is in Python", () => {
  assert.deepEqual([...missingFields({ summary: "\ufeff" }, JSON_SPEC)], []);
});

test("missingFields orders by UTF-16 code unit on both runtimes", () => {
  const spec = receiptSpec({ fmt: "json", requiredFields: [ASTRAL, "�"] });
  assert.deepEqual([...missingFields({}, spec)], [ASTRAL, "�"]);
});

test("the cmdline cap is measured in the unit Windows counts", () => {
  const flag = ASTRAL.repeat(16400);
  assert.equal(wire.utf16Len(renderCmdline(["x", flag])), 32802);
  assert.throws(
    () =>
      buildArgv({
        exe: "x",
        prompt: "p",
        transport: "file",
        flags: [flag],
        promptFlag: "-f",
        promptPath: "/t",
      }),
    (caught) => caught.reason === "win-arg-limit",
  );
});

test("the substring scan threshold is measured in UTF-16 code units", () => {
  const prompt = ASTRAL.repeat(32);
  assert.equal(promptOnArgv(`z${prompt}`, prompt), true);
  assert.equal(promptOnArgv(`z${ASTRAL.repeat(31)}`, ASTRAL.repeat(31)), false);
});

test("argv quoting uses the shared blank set, not the two disagreeing builtins", () => {
  assert.equal(renderCmdline(["a\u001cb"]), '"a\u001cb"');
  assert.equal(renderCmdline(["a\ufeffb"]), "a\ufeffb");
});

for (const timeoutS of [2.5, true, Number.MAX_SAFE_INTEGER + 2]) {
  test(`checkDispatch refuses timeout ${JSON.stringify(timeoutS)}, as Python does`, () => {
    assert.throws(
      () => checkDispatch({ background: false, timeoutS, awaited: false }),
      /timeout_s must be an integer/u,
    );
  });
}

test("checkDispatch still accepts a plain integer timeout", () => {
  assert.deepEqual([...checkDispatch({ background: false, timeoutS: 30, awaited: false })], []);
});

for (const micro of [2.5, Number.MAX_SAFE_INTEGER + 2]) {
  test(`debit refuses ${micro}, as Python does`, () => {
    assert.throws(
      () => debit(ledger({ limitMicro: 10 ** 15 }), "u", { attempt: 1, micro }),
      /micro must be an integer/u,
    );
  });
}

test("a ledger limit beyond the wire range is refused at construction", () => {
  assert.throws(
    () => ledger({ limitMicro: Number.MAX_SAFE_INTEGER + 2 }),
    /limit_micro must be an integer/u,
  );
  assert.throws(() => ledger({ limitMicro: -1 }), /limitMicro must be >= 0/u);
});

test("costPerSuccess refuses a non-integer success count", () => {
  assert.throws(
    () => costPerSuccess(ledger({ limitMicro: 10 }), { successes: 1.5 }),
    /successes must be an integer/u,
  );
});

test("costPerSuccess is EXACT at the top of the wire range", () => {
  // `Math.floor(9007199254740991 / 3)` is a double division; Python's `//` is exact. Bounding
  // the ledger and dividing with BigInt makes the two provably equal instead of probably equal.
  const book = debit(ledger({ limitMicro: Number.MAX_SAFE_INTEGER }), "u", {
    attempt: 1,
    micro: Number.MAX_SAFE_INTEGER,
  });
  assert.equal(costPerSuccess(book, { successes: 3 }), 3002399751580330);
  assert.equal(costPerSuccess(book, { successes: 0 }), 0);
});

test("the backoff schedule is bounded to the declared attempt ceiling", () => {
  assert.equal(rateLimitBackoffMs(RATE_LIMIT_MAX_ATTEMPTS), 32000);
  assert.throws(() => rateLimitBackoffMs(60), /RATE_LIMIT_MAX_ATTEMPTS/u);
  assert.throws(() => rateLimitBackoffMs(0), /attempt must be >= 1/u);
});

test("a terminal id accepts a newly assigned code point on both runtimes", () => {
  assert.equal(successLine("a࢏"), "SUCCESS:a࢏");
  assert.throws(() => successLine("a\u001b"), /printable/u);
});

test("the wire detail strings render lists canonically", () => {
  const verdict = judge(
    "u",
    railResult({ exitCode: 0, receiptBytes: Buffer.from('{"a":1}') }),
    JSON_SPEC,
  );
  assert.equal(verdict.detail, 'schema-invalid: missing or blank ["summary"]');
  const markerSpec = receiptSpec({ fmt: "text", forbiddenMarkers: ["todo"] });
  const incomplete = judge(
    "u",
    railResult({ exitCode: 0, receiptBytes: Buffer.from("TODO later") }),
    markerSpec,
  );
  assert.equal(incomplete.detail, 'receipt-incomplete: body carries ["todo"]');
});

test("an invalid-UTF-8 receipt names no interpreter-specific cause", () => {
  // The old message hardcoded "(invalid continuation)" for bytes Python called a bad START byte.
  const verdict = judge(
    "u",
    railResult({ exitCode: 0, receiptBytes: Buffer.from([0xff]) }),
    JSON_SPEC,
  );
  assert.equal(verdict.detail, "receipt-unparseable: not valid UTF-8");
});

for (const [label, text] of [
  ["array", "[1]"],
  ["number", "1"],
  ["string", '"s"'],
  ["null", "null"],
  ["boolean", "true"],
]) {
  test(`a ${label} top level is named in the portable vocabulary`, () => {
    assert.throws(
      () => parseJsonObject(text),
      (caught) =>
        caught.message === `receipt-unparseable: top level must be an object, got ${label}`,
    );
  });
}

for (const literal of ["NaN", "Infinity", "-Infinity"]) {
  test(`a ${literal} receipt is unparseable rather than a success`, () => {
    assert.throws(() => parseJsonObject(`{"summary": ${literal}}`), /invalid JSON/u);
  });
}

// ------------------------------------------------- canonical.loadb: the BLOCKING silent coercion

for (const [label, bytes] of [
  ["a bare invalid start byte", [0x22, 0xff, 0x22]],
  ["a truncated 3-byte sequence", [0x22, 0xe2, 0x82, 0x22]],
  ["an overlong encoding", [0x22, 0xc0, 0xaf, 0x22]],
  ["a CESU-8 surrogate", [0x22, 0xed, 0xa0, 0xbd, 0x22]],
  ["corrupt bytes inside an object", [0x7b, 0x22, 0x61, 0x22, 0x3a, 0x22, 0xff, 0x22, 0x7d]],
]) {
  test(`loadb REFUSES ${label} instead of substituting U+FFFD`, () => {
    // MEASURED before the fix: every one of these returned a well-formed value here and raised
    // in Python, so `dumpb(loadb(corrupt))` manufactured a plausible canonical receipt.
    assert.throws(
      () => loadb(Buffer.from(bytes)),
      (caught) => caught instanceof CanonicalJsonError && caught.code === E_INVALID_UTF8,
    );
    // The detector control: the LOSSY decode this replaced is still lossy, and still silent.
    assert.ok(Buffer.from(bytes).toString("utf8").includes("�"));
  });
}

test("loadb still accepts valid canonical bytes, including a BOM as DATA", () => {
  assert.deepEqual(loadb(Buffer.from('{"a":1}', "utf8")), { a: 1 });
  assert.deepEqual(loadb(Buffer.from('{"\ufeff":1}', "utf8")), { "\ufeff": 1 });
});
