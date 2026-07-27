/** Pre-dispatch policy: no fire-and-forget on an awaited unit, and no implicit timeout. */

import assert from "node:assert/strict";
import test from "node:test";

import { DISPATCH_VIOLATIONS, checkDispatch } from "../src/dispatchpolicy.mjs";

test("the violation set is sorted and closed", () => {
  assert.deepEqual([...DISPATCH_VIOLATIONS], [...DISPATCH_VIOLATIONS].sort());
  assert.equal(DISPATCH_VIOLATIONS.length, 3);
});

test("a well-formed foreground dispatch is clean", () => {
  assert.deepEqual([...checkDispatch({ background: false, timeoutS: 600, awaited: true })], []);
});

test("backgrounding an AWAITED unit is the measured fire-and-forget failure", () => {
  // Three Codex subagents produced zero artifacts: each returned "started in the background as
  // task-…", the barrier read that as the answer, and the real work was discarded unread.
  assert.deepEqual(
    [...checkDispatch({ background: true, timeoutS: 600, awaited: true })],
    ["background-on-awaited-dispatch"],
  );
});

test("the rule is SCOPED: backgrounding something nothing awaits is legitimate", () => {
  // The detector control. A guard that fires in the good state is as broken as one that stays
  // silent in the bad state.
  assert.deepEqual([...checkDispatch({ background: true, timeoutS: 600, awaited: false })], []);
});

test("a missing or non-positive timeout is a violation", () => {
  assert.deepEqual(
    [...checkDispatch({ background: false, timeoutS: null, awaited: false })],
    ["missing-timeout"],
  );
  assert.deepEqual(
    [...checkDispatch({ background: false, timeoutS: 0, awaited: false })],
    ["nonpositive-timeout"],
  );
  assert.deepEqual(
    [...checkDispatch({ background: false, timeoutS: -5, awaited: false })],
    ["nonpositive-timeout"],
  );
});

test("multiple violations are reported together, sorted", () => {
  assert.deepEqual(
    [...checkDispatch({ background: true, timeoutS: null, awaited: true })],
    ["background-on-awaited-dispatch", "missing-timeout"],
  );
});

test("a non-integer timeout is a TYPE error, not a silent coercion", () => {
  for (const bad of [1.5, "600", true, Number.NaN]) {
    assert.throws(
      () => checkDispatch({ background: false, timeoutS: bad, awaited: false }),
      TypeError,
      `accepted ${JSON.stringify(bad)}`,
    );
  }
});

test("every declared violation id is reachable", () => {
  const emitted = new Set([
    ...checkDispatch({ background: true, timeoutS: null, awaited: true }),
    ...checkDispatch({ background: false, timeoutS: 0, awaited: false }),
  ]);
  assert.deepEqual([...emitted].sort(), [...DISPATCH_VIOLATIONS]);
});
