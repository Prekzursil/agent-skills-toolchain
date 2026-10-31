/**
 * PRE-DISPATCH POLICY — the checks that must pass before a rail is touched at all.
 *
 * The JS mirror of `agentspec/dispatchpolicy.py`. MEASURED FAILURES:
 *
 *  - **Fire-and-forget on an awaited unit.** Three Codex-backed subagents produced zero
 *    artifacts: each returned a "started in the background as task-…" receipt, the barrier
 *    waiting on them read that as the answer, and the real work then completed on disk and was
 *    discarded unread. A backgrounded job's result is structurally unreachable to its barrier.
 *  - **No explicit timeout.** A silent default timeout is what a caller rationalised
 *    `--background` to escape, so a dispatch must state its own bound.
 *
 * The rule is scoped, not blanket: backgrounding a dispatch that NOTHING awaits is legitimate,
 * and there is a detector control asserting this function stays silent in that case.
 */

import { requireWireInteger, sortedWire } from "./wire.mjs";

export const DISPATCH_VIOLATIONS = Object.freeze([
  "background-on-awaited-dispatch",
  "missing-timeout",
  "nonpositive-timeout",
]);

/** Return the sorted violations for a proposed dispatch; empty means go ahead. */
export function checkDispatch({ background, timeoutS, awaited }) {
  if (timeoutS !== null) {
    requireWireInteger(timeoutS, "timeout_s");
  }
  const found = [];
  if (background && awaited) {
    found.push("background-on-awaited-dispatch");
  }
  if (timeoutS === null) {
    found.push("missing-timeout");
  } else if (timeoutS <= 0) {
    found.push("nonpositive-timeout");
  }
  return sortedWire(found);
}
