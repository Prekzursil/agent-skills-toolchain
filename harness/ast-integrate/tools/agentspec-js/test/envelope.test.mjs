/** The shared observation envelope, including the banned error-only shape. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  ENVELOPE_FIELDS,
  STATUSES,
  asWire,
  error,
  errorDetail,
  observation,
  success,
  validateObservation,
  warning,
} from "../src/envelope.mjs";

const DETAIL = errorDetail({
  code: "receipt-missing",
  rootCause: "the rail exited 0 with no receipt",
  retryInstruction: "re-dispatch once in the foreground",
  stopCondition: "stop after 1 retry",
});

test("the four mandated fields are declared in wire order", () => {
  assert.deepEqual([...ENVELOPE_FIELDS], ["status", "summary", "next_actions", "artifacts"]);
  assert.deepEqual([...STATUSES], ["success", "warning", "error"]);
});

test("success and warning build valid envelopes", () => {
  const ok = success("done", { nextActions: ["consume"], artifacts: ["a.log"] });
  assert.equal(ok.status, "success");
  assert.deepEqual(validateObservation(ok), []);
  const warn = warning("partial");
  assert.equal(warn.status, "warning");
  assert.deepEqual(validateObservation(warn), []);
  assert.deepEqual([...warn.nextActions], []);
});

test("an error envelope carries all three recovery affordances", () => {
  const bad = error("wu-1: receipt-missing", DETAIL, { nextActions: ["resolve it"] });
  assert.equal(bad.status, "error");
  assert.equal(bad.error.code, "receipt-missing");
  assert.deepEqual(validateObservation(bad), []);
});

test("an error with NO next_actions is refused at construction", () => {
  // "error-only output without next steps" is a named anti-pattern, so it cannot be built.
  assert.throws(() => error("boom", DETAIL, { nextActions: [] }), /error-only output is banned/u);
});

test("the wire form is exactly the four fields, plus error only when present", () => {
  assert.deepEqual(asWire(success("done")), {
    status: "success",
    summary: "done",
    next_actions: [],
    artifacts: [],
  });
  const wire = asWire(error("boom", DETAIL, { nextActions: ["fix"], artifacts: ["x"] }));
  assert.deepEqual(Object.keys(wire), [...ENVELOPE_FIELDS, "error"]);
  assert.deepEqual(wire.error, {
    code: "receipt-missing",
    root_cause: "the rail exited 0 with no receipt",
    retry_instruction: "re-dispatch once in the foreground",
    stop_condition: "stop after 1 retry",
  });
});

test("the wire form serialises canonically and byte-identically to the Python shape", async () => {
  const { dumps } = await import("../src/canonical.mjs");
  assert.equal(
    dumps(asWire(success("wu-1: completed (1200 ms)", { nextActions: ["consume the receipt payload"] }))),
    '{"artifacts":[],"next_actions":["consume the receipt payload"],' +
      '"status":"success","summary":"wu-1: completed (1200 ms)"}',
  );
});

test("validateObservation reports every violation, sorted", () => {
  const broken = observation({ status: "nope", summary: "   " });
  assert.deepEqual(validateObservation(broken), [
    "envelope-status-invalid",
    "envelope-summary-empty",
  ]);
});

test("an error status with no error detail is a violation", () => {
  const broken = observation({ status: "error", summary: "boom", nextActions: ["fix"] });
  assert.deepEqual(validateObservation(broken), ["envelope-error-missing"]);
});

test("a non-error status carrying an error detail is a violation", () => {
  const broken = observation({ status: "success", summary: "ok", error: DETAIL });
  assert.deepEqual(validateObservation(broken), ["envelope-error-unexpected"]);
});

test("every field of the error detail is checked", () => {
  const blank = errorDetail({
    code: "not-a-taxonomy-member",
    rootCause: " ",
    retryInstruction: "",
    stopCondition: "\t",
  });
  const broken = observation({ status: "error", summary: "boom", nextActions: [], error: blank });
  assert.deepEqual(validateObservation(broken), [
    "envelope-error-code-unknown",
    "envelope-error-retry-instruction-empty",
    "envelope-error-root-cause-empty",
    "envelope-error-stop-condition-empty",
    "envelope-next-actions-empty",
  ]);
});

test("a parametrised taxonomy code is accepted in the error detail", () => {
  const detail = errorDetail({
    code: "rate-limited-429",
    rootCause: "429 from the rail",
    retryInstruction: "back off",
    stopCondition: "stop after 6 attempts",
  });
  const obs = error("wu: rate-limited-429", detail, { nextActions: ["back off"] });
  assert.deepEqual(validateObservation(obs), []);
});

test("observations are frozen records, not mutable accumulators", () => {
  const obs = success("done", { nextActions: ["a"] });
  assert.ok(Object.isFrozen(obs));
  assert.ok(Object.isFrozen(obs.nextActions));
  assert.ok(Object.isFrozen(obs.artifacts));
});
