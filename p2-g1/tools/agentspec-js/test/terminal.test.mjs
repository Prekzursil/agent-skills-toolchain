/** Terminal-marker rendering, and the id sanitisation that keeps the marker parseable. */

import assert from "node:assert/strict";
import test from "node:test";

import { TERMINAL_RE, failureLine, successLine, terminalLine } from "../src/terminal.mjs";

test("the two marker shapes render and match the anchored pattern", () => {
  assert.equal(successLine("wu-1"), "SUCCESS:wu-1");
  assert.equal(failureLine("wu-1", "receipt-missing"), "FAILED:wu-1 receipt-missing");
  assert.ok(TERMINAL_RE.test(successLine("wu-1")));
  assert.ok(TERMINAL_RE.test(failureLine("wu-1", "rail-exit-137")));
  assert.ok(!TERMINAL_RE.test("mostly done, I think"));
  assert.ok(!TERMINAL_RE.test("FAILED:wu-1 "));
});

test("a reason outside the closed taxonomy is refused", () => {
  assert.throws(() => failureLine("wu-1", "made-up"), /not in the closed taxonomy/u);
  assert.throws(() => failureLine("wu-1", ""), /not in the closed taxonomy/u);
  // A parametrised member is fine.
  assert.equal(failureLine("wu-1", "timeout-1800s"), "FAILED:wu-1 timeout-1800s");
});

test("an id that would corrupt the marker line is refused", () => {
  for (const bad of ["", "wu 1", "wu\t1", "wu\n1", "wu\u001b[31m", "wu\u0000", "wu\u007f", "wu\u00a0"]) {
    assert.throws(
      () => successLine(bad),
      /must be non-empty, whitespace-free and printable/u,
      `accepted a hazardous id: ${JSON.stringify(bad)}`,
    );
  }
});

test("a non-ASCII but PRINTABLE id is valid", () => {
  // `isprintable` is deliberately not an ASCII check on the Python side; the JS predicate has
  // to agree or the two runtimes disagree on which ids are legal.
  assert.equal(successLine("wu-é"), "SUCCESS:wu-é");
  assert.equal(successLine("wu-日本"), "SUCCESS:wu-日本");
});

test("a successful verdict renders SUCCESS", () => {
  assert.equal(terminalLine({ unitId: "wu-1", ok: true }), "SUCCESS:wu-1");
});

test("a SEVERED verdict puts severed-stream FIRST, with the fine cause in parentheses", () => {
  // A consumer that greps for `severed-stream` must match, while the operator still sees the
  // fine cause.
  assert.equal(
    terminalLine({ unitId: "wu-1", ok: false, severed: true, reason: "receipt-empty" }),
    "FAILED:wu-1 severed-stream (receipt-empty)",
  );
});

test("a genuine rail failure renders its own reason, not severed-stream", () => {
  assert.equal(
    terminalLine({ unitId: "wu-1", ok: false, severed: false, reason: "rail-exit-137" }),
    "FAILED:wu-1 rail-exit-137",
  );
});

test("terminalLine is duck-typed and tolerates missing fields", () => {
  // Typed loosely on purpose: importing the verdict type would make oracle and terminal
  // mutually dependent, and a runtime carrying its own verdict record must still render.
  assert.throws(() => terminalLine({}), /must be non-empty/u);
  assert.equal(
    terminalLine({ unitId: "wu-1", ok: false, reason: "timeout-60s" }),
    "FAILED:wu-1 timeout-60s",
  );
});
