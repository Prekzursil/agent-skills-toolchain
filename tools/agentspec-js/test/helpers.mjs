/**
 * Shared test helpers. NOT a `*.test.mjs` file, so the runner does not collect it as a suite.
 *
 * `assert.throws` returns `undefined`, so it cannot be used to inspect the thrown value. Node
 * has no `assertRaises`-with-a-handle equivalent, and `capture` is the missing piece: it asserts
 * that something was thrown AND hands the error back, so a test can pin the taxonomy `reason`
 * and the structured fields rather than only the message text.
 */

import assert from "node:assert/strict";

/** Run `thunk`, assert it threw, and return the thrown error for inspection. */
export function capture(thunk) {
  try {
    thunk();
  } catch (caught) {
    return caught;
  }
  assert.fail("expected the call to throw, but it returned normally");
  return undefined;
}
