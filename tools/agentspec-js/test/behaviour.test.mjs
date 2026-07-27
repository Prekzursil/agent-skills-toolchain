/**
 * The BEHAVIOURAL corpus driver, and the guards that stop it reporting a vacuous pass.
 *
 * The corpus itself is executed here as well as by `npm run parity`, so a malformed fixture
 * fails the unit gate too rather than only the (slower, python-dependent) parity gate.
 */

import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  BehaviourCorpusError,
  OPERATIONS,
  decodeArg,
  errorKind,
  runCase,
  runCorpus,
} from "../src/behaviour.mjs";

const CORPUS = JSON.parse(
  readFileSync(fileURLToPath(new URL("../fixtures/behaviour-corpus.json", import.meta.url)), "utf8"),
);

test("every corpus case runs and produces a canonical outcome", () => {
  const results = runCorpus(CORPUS);
  assert.ok(results.length >= 100, `expected a real corpus, got ${results.length} cases`);
  for (const result of results) {
    assert.match(
      result.output,
      /^\{"(?:err|ok)":/u,
      `case ${result.id} produced a non-outcome: ${result.output}`,
    );
  }
});

test("the corpus exercises the AND-gate on the blankness boundary that flipped it", () => {
  // A named spot-check, not a restatement: these are the rows whose Python and JS outcomes
  // DISAGREED before the shared wire rules, so a corpus that lost them would go green while
  // measuring nothing.
  const byId = new Map(runCorpus(CORPUS).map((result) => [result.id, result.output]));
  assert.equal(byId.get("judge-blank-fs"), byId.get("judge-empty-receipt"));
  assert.match(byId.get("judge-blank-nel"), /receipt-empty/u);
  assert.match(byId.get("judge-bom-double"), /receipt-unparseable/u);
  assert.match(byId.get("judge-blank-unit-id"), /"err":"invalid-value"/u);
  assert.equal(byId.get("loadb-bad-start"), '{"err":"schema-invalid-utf8"}');
  assert.equal(byId.get("missing-bom"), '{"ok":[]}');
  assert.equal(byId.get("missing-fs"), '{"ok":["summary"]}');
});

test("every declared operation is exercised by at least one case", () => {
  assert.ok(OPERATIONS.length >= 20, `expected the full op table, got ${OPERATIONS.length}`);
  const exercised = new Set(CORPUS.cases.map((entry) => entry.op));
  assert.deepEqual([...exercised].sort(), [...OPERATIONS]);
});

test("an empty or duplicated corpus is REFUSED rather than passing vacuously", () => {
  assert.throws(() => runCorpus({ cases: [] }), BehaviourCorpusError);
  assert.throws(() => runCorpus({ cases: "nope" }), BehaviourCorpusError);
  const one = CORPUS.cases[0];
  assert.throws(() => runCorpus({ cases: [one, one] }), /duplicate case ids/u);
  assert.throws(
    () => runCorpus({ cases: [one] }),
    /no corpus case exercises op/u,
    "a corpus that drops an op must FAIL, or a deleted op stops being compared",
  );
});

test("an unknown op is a corpus defect, not a tidy err row", () => {
  assert.throws(
    () => runCase({ id: "x", op: "no_such_op", args: {} }),
    /unknown op "no_such_op"/u,
  );
});

for (const [node, expected] of [
  [{ s: "text" }, "text"],
  [{ i: "42" }, 42],
  [{ f: "1.5" }, 1.5],
  [{ b: true }, true],
  [{ n: true }, null],
]) {
  test(`decodeArg ${JSON.stringify(node)} yields ${JSON.stringify(expected)}`, () => {
    assert.equal(decodeArg(node), expected);
  });
}

test("decodeArg builds bytes, string lists and ordered objects", () => {
  assert.ok(decodeArg({ hex: "7b7d" }).equals(Buffer.from("{}", "utf8")));
  assert.deepEqual(decodeArg({ ss: ["a", "b"] }), ["a", "b"]);
  assert.deepEqual(decodeArg({ kv: [["a", { i: "1" }]] }), { a: 1 });
});

for (const bad of [null, "text", ["a"], {}, { s: "a", i: "1" }, { zz: 1 }]) {
  test(`decodeArg refuses ${JSON.stringify(bad)}`, () => {
    assert.throws(() => decodeArg(bad), BehaviourCorpusError);
  });
}

test("errorKind prefers the taxonomy code, then the reason, then the structural class", () => {
  assert.equal(errorKind({ code: "schema-invalid-utf8", reason: "schema-invalid" }), "schema-invalid-utf8");
  assert.equal(errorKind({ reason: "receipt-unparseable" }), "receipt-unparseable");
  assert.equal(errorKind(new TypeError("x")), "invalid-type");
  assert.equal(errorKind(new RangeError("x")), "invalid-value");
});

test("errorKind RE-THROWS anything it cannot name, so a crash cannot look like conformance", () => {
  const crash = new Error("segfault-equivalent");
  assert.throws(() => errorKind(crash), /segfault-equivalent/u);
});
