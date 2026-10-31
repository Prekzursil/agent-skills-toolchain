/**
 * THE COMPLETION AND-GATE. Exit 0 is not proof of completion.
 *
 * Each clause has a case that fails ONLY that clause, so the gate cannot silently collapse to
 * "exit 0 and non-empty" — the measured shape where a rail returned a progress prefix after
 * 6m59s and the caller forwarded it as a terminal result.
 */

import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import test from "node:test";

import { validateObservation } from "../src/envelope.mjs";
import { CLAUSES, failureReason, judge, observe, railResult } from "../src/oracle.mjs";
import { receiptSpec } from "../src/spec.mjs";
import { terminalLine } from "../src/terminal.mjs";

const JSON_SPEC = receiptSpec({ fmt: "json", requiredFields: ["result"] });
const TEXT_SPEC = receiptSpec({ fmt: "text", forbiddenMarkers: ["in progress", "TODO"] });

const bytes = (text) => Buffer.from(text, "utf8");

test("the six clauses are declared in gate order", () => {
  assert.deepEqual([...CLAUSES], [
    "exit-zero",
    "receipt-present",
    "receipt-non-empty",
    "receipt-parses",
    "receipt-schema",
    "receipt-content",
  ]);
});

test("a real work product passes all six clauses", () => {
  const verdict = judge(
    "wu-1",
    railResult({ exitCode: 0, receiptBytes: bytes('{"result":"done"}'), wallMs: 1200 }),
    JSON_SPEC,
  );
  assert.equal(verdict.ok, true);
  assert.equal(verdict.reason, null);
  assert.equal(verdict.severed, false);
  assert.deepEqual([...verdict.passedClauses], [...CLAUSES]);
  assert.deepEqual(verdict.payload, { result: "done" });
  assert.equal(verdict.wallMs, 1200);
  assert.equal(failureReason(verdict), "");
  assert.equal(terminalLine(verdict), "SUCCESS:wu-1");
});

test("a non-zero exit is a RAIL failure, not a severed stream", () => {
  const verdict = judge("wu-1", railResult({ exitCode: 137, receiptBytes: null }), JSON_SPEC);
  assert.equal(verdict.ok, false);
  assert.equal(verdict.reason, "rail-exit-137");
  assert.equal(verdict.severed, false, "the rail failing is not the same as a severed stream");
  assert.deepEqual([...verdict.passedClauses], []);
  assert.equal(terminalLine(verdict), "FAILED:wu-1 rail-exit-137");
});

/** `[label, railResult, spec, reason, clauses that should have passed first]` */
const SEVERED_CASES = [
  ["missing receipt", railResult({ exitCode: 0, receiptBytes: null }), JSON_SPEC, "receipt-missing", 1],
  ["blank receipt", railResult({ exitCode: 0, receiptBytes: bytes("   \n ") }), JSON_SPEC, "receipt-empty", 2],
  [
    "invalid UTF-8",
    railResult({ exitCode: 0, receiptBytes: Buffer.from([0xff, 0xfe]) }),
    JSON_SPEC,
    "receipt-unparseable",
    2,
  ],
  [
    "not JSON",
    railResult({ exitCode: 0, receiptBytes: bytes("{not json") }),
    JSON_SPEC,
    "receipt-unparseable",
    3,
  ],
  [
    "JSON array, not an object",
    railResult({ exitCode: 0, receiptBytes: bytes("[1,2]") }),
    JSON_SPEC,
    "receipt-unparseable",
    3,
  ],
  [
    "required field blank",
    railResult({ exitCode: 0, receiptBytes: bytes('{"result":"  "}') }),
    JSON_SPEC,
    "schema-invalid",
    4,
  ],
  [
    "forbidden marker present",
    railResult({ exitCode: 0, receiptBytes: bytes("work is In Progress") }),
    TEXT_SPEC,
    "receipt-incomplete",
    5,
  ],
  [
    "body is a progress stream",
    railResult({ exitCode: 0, receiptBytes: bytes("[codex] reading files\n[codex] thinking") }),
    TEXT_SPEC,
    "progress-stream",
    5,
  ],
];

for (const [label, result, spec, reason, passedCount] of SEVERED_CASES) {
  test(`exit 0 with ${label} is SEVERED, never SUCCESS`, () => {
    const verdict = judge("wu-1", result, spec);
    assert.equal(verdict.ok, false);
    assert.equal(verdict.reason, reason);
    assert.equal(verdict.severed, true);
    assert.deepEqual([...verdict.passedClauses], CLAUSES.slice(0, passedCount));
    // A consumer grepping for severed-stream must match, while the operator sees the cause.
    assert.equal(terminalLine(verdict), `FAILED:wu-1 severed-stream (${reason})`);
  });
}

test("a text receipt with no forbidden marker passes", () => {
  const verdict = judge("wu-1", railResult({ exitCode: 0, receiptBytes: bytes("all done") }), TEXT_SPEC);
  assert.equal(verdict.ok, true);
  assert.equal(verdict.payload, null);
  assert.equal(verdict.text, "all done");
});

test("a falsy-but-real required field is a work product", () => {
  const spec = receiptSpec({ fmt: "json", requiredFields: ["count", "ok"] });
  const verdict = judge(
    "wu-1",
    railResult({ exitCode: 0, receiptBytes: bytes('{"count":0,"ok":false}') }),
    spec,
  );
  assert.equal(verdict.ok, true);
});

test("judge REFUSES a vacuous spec, fail-closed", () => {
  // Without this a consumer that hand-built a spec and called judge directly silently ran a
  // two-clause gate, and a receipt reading "work is still in progress" reported SUCCESS.
  const result = railResult({ exitCode: 0, receiptBytes: bytes("{}") });
  assert.throws(() => judge("wu-1", result, receiptSpec({ fmt: "json" })), /vacuous/u);
  assert.throws(() => judge("wu-1", result, receiptSpec({ fmt: "text" })), /vacuous/u);
});

test("judge refuses an unknown format and an empty unit id", () => {
  const result = railResult({ exitCode: 0, receiptBytes: bytes("{}") });
  assert.throws(() => judge("wu-1", result, receiptSpec({ fmt: "yaml" })), /fmt must be one of/u);
  assert.throws(() => judge("  ", result, JSON_SPEC), /unitId must be non-empty/u);
});

test("railResult refuses a non-integer or negative wallMs", () => {
  // An integral float renders `1.0` in Python and `1` in JS, so the wire type is pinned here.
  assert.throws(() => railResult({ exitCode: 0, receiptBytes: null, wallMs: 1.5 }), TypeError);
  assert.throws(() => railResult({ exitCode: 0, receiptBytes: null, wallMs: true }), TypeError);
  assert.throws(() => railResult({ exitCode: 0, receiptBytes: null, wallMs: -1 }), /wallMs must be >= 0/u);
  assert.equal(railResult({ exitCode: 0, receiptBytes: null }).wallMs, 0);
});

test("the progress field is DIAGNOSTICS and is never read as a result", () => {
  const verdict = judge(
    "wu-1",
    railResult({
      exitCode: 0,
      receiptBytes: bytes('{"result":"done"}'),
      progress: "[codex] started in the background",
    }),
    JSON_SPEC,
  );
  assert.equal(verdict.ok, true, "a progress diagnostic must not change the verdict");
});

test("observe projects a success onto a valid envelope", () => {
  const verdict = judge(
    "wu-1",
    railResult({ exitCode: 0, receiptBytes: bytes('{"result":"done"}'), wallMs: 900 }),
    JSON_SPEC,
  );
  const obs = observe(verdict, { artifacts: ["out.json"] });
  assert.equal(obs.status, "success");
  assert.equal(obs.summary, "wu-1: completed (900 ms)");
  assert.deepEqual([...obs.artifacts], ["out.json"]);
  assert.deepEqual(validateObservation(obs), []);
});

test("EVERY error projection carries all three recovery affordances", () => {
  for (const [, result, spec] of SEVERED_CASES) {
    const obs = observe(judge("wu-1", result, spec));
    assert.equal(obs.status, "error");
    assert.deepEqual(validateObservation(obs), [], `invalid envelope for ${obs.summary}`);
    assert.ok(obs.error.rootCause.includes("severed-stream"));
    assert.ok(obs.error.retryInstruction.length > 0);
    assert.ok(obs.error.stopCondition.length > 0);
    assert.equal(obs.nextActions.length, 1);
  }
});

test("the retry instruction and stop condition are tailored per reason family", () => {
  const railFailure = observe(
    judge("wu-1", railResult({ exitCode: 137, receiptBytes: null }), JSON_SPEC),
  );
  assert.ok(railFailure.error.rootCause.startsWith("the rail itself failed"));
  assert.match(railFailure.error.retryInstruction, /inspect the diagnostic tail/u);
  assert.match(railFailure.error.stopCondition, /no automatic retry/u);

  const missing = observe(judge("wu-1", railResult({ exitCode: 0, receiptBytes: null }), JSON_SPEC));
  assert.match(missing.error.retryInstruction, /FOREGROUND/u);
  assert.match(missing.error.stopCondition, /stop after 1 retry/u);

  const empty = observe(
    judge("wu-1", railResult({ exitCode: 0, receiptBytes: bytes("  ") }), JSON_SPEC),
  );
  assert.match(empty.error.retryInstruction, /do not parse the progress stream/u);

  const unusable = observe(
    judge("wu-1", railResult({ exitCode: 0, receiptBytes: bytes('{"result":null}') }), JSON_SPEC),
  );
  assert.match(unusable.error.retryInstruction, /do NOT retry blindly/u);
});

test("a rate-limited reason gets the bounded backoff instruction", () => {
  // Reached through the projection rather than the gate: `judge` never mints rate-limited, but
  // a transport that did must still get a bounded, non-looping instruction.
  const obs = observe({
    unitId: "wu-1",
    ok: false,
    reason: "rate-limited-429",
    severed: false,
    detail: "429 from the rail",
    wallMs: 0,
  });
  assert.match(obs.error.retryInstruction, /bounded doubling schedule/u);
  assert.match(obs.error.stopCondition, /stop after 6 attempts/u);
  assert.deepEqual(validateObservation(obs), []);
});

test("verdicts are frozen records", () => {
  const verdict = judge("wu-1", railResult({ exitCode: 0, receiptBytes: null }), JSON_SPEC);
  assert.ok(Object.isFrozen(verdict));
  assert.ok(Object.isFrozen(verdict.passedClauses));
});
