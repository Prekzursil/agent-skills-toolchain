/**
 * The shared conformance corpus, driven from the JS side.
 *
 * The corpus file is the CONTRACT — not prose in a README. `parity/emit_py.py` drives the same
 * file from Python and `parity/oracle.mjs` byte-compares the two. This suite covers the JS
 * reader plus every malformed-input path, because a corpus driver that silently skips a case it
 * cannot parse would report a green run over a shrinking contract.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { CorpusError, buildValue, disagreements, runCase, runCorpus } from "../src/corpus.mjs";

const CORPUS_PATH = fileURLToPath(new URL("../fixtures/canonical-corpus.json", import.meta.url));
const CORPUS = JSON.parse(readFileSync(CORPUS_PATH, "utf8"));

test("the real corpus is non-trivial and every case agrees with this runtime", () => {
  assert.ok(CORPUS.cases.length >= 80, `corpus shrank to ${CORPUS.cases.length} cases`);
  const results = runCorpus(CORPUS);
  assert.equal(results.length, CORPUS.cases.length);
  assert.deepEqual(disagreements(results), []);
});

test("the corpus exercises BOTH outcomes, so neither branch is untested", () => {
  const results = runCorpus(CORPUS);
  assert.ok(results.some((row) => row.status === "ok"), "no accepted case");
  assert.ok(results.some((row) => row.status === "reject"), "no rejected case");
});

test("the corpus covers every canonical rejection code that can be reached by VALUE", async () => {
  const { REJECTION_CODES } = await import("../src/canonical.mjs");
  const covered = new Set(
    runCorpus(CORPUS)
      .filter((row) => row.status === "reject")
      .map((row) => row.output),
  );
  // These cannot be expressed as a VALUE in a plain-JSON corpus, so they are pinned by the
  // unit suites on each side instead. Naming them here keeps the gap explicit rather than
  // accidental:
  //   cyclic / nonstring-key / unsupported-type — a JSON file has no cycles, no symbols,
  //     no Date;
  //   key-collision — reachable only through Python's surrogate FOLD, which the JS encoder
  //     cannot perform (its encoding is injective), so no single corpus value rejects on
  //     both runtimes; `test_canonical.py::test_R4b_*` pins the Python side;
  //   utf8 — a DECODER rejection (`loadb`), not an encoder one; this corpus drives `dumps`.
  const unreachableInJson = new Set([
    "schema-invalid-cyclic",
    "schema-invalid-nonstring-key",
    "schema-invalid-unsupported-type",
    "schema-invalid-key-collision",
    "schema-invalid-utf8",
  ]);
  for (const code of REJECTION_CODES) {
    if (!unreachableInJson.has(code)) {
      assert.ok(covered.has(code), `no corpus case rejects with ${code}`);
    }
  }
});

test("every value tag builds the type it claims", () => {
  assert.equal(buildValue({ str: "x" }), "x");
  assert.equal(buildValue({ int: "5" }), 5n);
  assert.equal(buildValue({ num: "1.5" }), 1.5);
  assert.equal(buildValue({ bool: true }), true);
  assert.equal(buildValue({ null: true }), null);
  assert.deepEqual(buildValue({ arr: [{ int: "1" }] }), [1n]);
  assert.ok(Number.isNaN(buildValue({ num: "NaN" })));
  assert.equal(buildValue({ num: "Infinity" }), Number.POSITIVE_INFINITY);
  assert.ok(Object.is(buildValue({ num: "-0" }), -0));
});

test("an obj node preserves the declared insertion order", () => {
  const built = buildValue({ obj: [["b", { int: "1" }], ["a", { int: "2" }]] });
  assert.deepEqual(Object.keys(built), ["b", "a"]);
  assert.equal(Object.getPrototypeOf(built), null);
});

test("a nest node builds the requested depth in both kinds", () => {
  const nestedArray = buildValue({ nest: { depth: 3, kind: "arr" } });
  assert.deepEqual(nestedArray, [[[1n]]]);
  const nestedObject = buildValue({ nest: { depth: 2, kind: "obj" } });
  assert.deepEqual(runCase({ id: "t", value: { nest: { depth: 2, kind: "obj" } } }), {
    id: "t",
    status: "ok",
    output: '{"n":{"n":1}}',
  });
  assert.equal(Object.getPrototypeOf(nestedObject), null);
});

test("a depth-zero nest is the bare inner value", () => {
  assert.equal(buildValue({ nest: { depth: 0, kind: "arr" } }), 1n);
});

test("runCase reports a rejection as a terminal status, not as a throw", () => {
  assert.deepEqual(runCase({ id: "r", value: { num: "NaN" } }), {
    id: "r",
    status: "reject",
    output: "schema-invalid-nonfinite",
  });
});

test("a malformed value node THROWS, so a bad case can never be skipped silently", () => {
  assert.throws(() => buildValue(null), CorpusError);
  assert.throws(() => buildValue("bare"), /must be a tagged object/u);
  assert.throws(() => buildValue([1]), /must be a tagged object/u);
  assert.throws(() => buildValue({}), /exactly one tag/u);
  assert.throws(() => buildValue({ str: "a", int: "1" }), /exactly one tag/u);
  assert.throws(() => buildValue({ nope: 1 }), /unknown value tag/u);
  assert.throws(() => buildValue({ obj: [["only-a-key"]] }), /\[key, node\] pairs/u);
  assert.throws(() => buildValue({ obj: ["not-a-pair"] }), /\[key, node\] pairs/u);
  assert.throws(() => buildValue({ nest: { depth: 1, kind: "map" } }), /nest kind must be/u);
});

test("runCase wraps a build failure with the case id", () => {
  assert.throws(() => runCase({ id: "bad-case", value: { nope: 1 } }), /case bad-case/u);
});

test("a non-canonical throw from the encoder is NOT swallowed as a tidy rejection", () => {
  // Only a CanonicalJsonError is a REJECTION. A crash recorded as `status: "reject"` would let
  // a defect masquerade as conformance, so it must propagate.
  const exploding = () => {
    throw new RangeError("kaboom");
  };
  assert.throws(() => runCase({ id: "x", value: { int: "1" } }, exploding), RangeError);
  assert.throws(
    () => runCorpus({ cases: [{ id: "x", value: { int: "1" }, expect: { ok: "1" } }] }, exploding),
    RangeError,
  );
});

test("a case with no expectation is REFUSED rather than counted as agreeing", () => {
  assert.throws(
    () => runCorpus({ cases: [{ id: "x", value: { int: "1" }, expect: {} }] }),
    /must carry "ok" or "reject"/u,
  );
});

test("an empty or duplicated corpus is REFUSED, never passed vacuously", () => {
  assert.throws(() => runCorpus({ cases: [] }), /passes vacuously/u);
  assert.throws(() => runCorpus({ cases: "nope" }), /passes vacuously/u);
  assert.throws(
    () =>
      runCorpus({
        cases: [
          { id: "dup", value: { int: "1" }, expect: { ok: "1" } },
          { id: "dup", value: { int: "2" }, expect: { ok: "2" } },
        ],
      }),
    /duplicate case ids/u,
  );
});

test("a wrong expectation is reported as a disagreement, not hidden", () => {
  const results = runCorpus({
    cases: [
      { id: "right", value: { int: "1" }, expect: { ok: "1" } },
      { id: "wrong-output", value: { int: "1" }, expect: { ok: "2" } },
      { id: "wrong-status", value: { int: "1" }, expect: { reject: "schema-invalid-int-range" } },
    ],
  });
  assert.deepEqual(
    disagreements(results).map((row) => row.id),
    ["wrong-output", "wrong-status"],
  );
  assert.equal(results[0].agrees, true);
});

test("the CorpusError type is exported so a caller can match on it", () => {
  const failure = new CorpusError("boom");
  assert.equal(failure.name, "CorpusError");
  assert.ok(failure instanceof Error);
});
