/** The bounded retry policy: two families retry, everything else stops. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  RATE_LIMIT_BASE_BACKOFF_MS,
  RATE_LIMIT_MAX_ATTEMPTS,
  RETRYABLE_ONCE,
  planRetry,
  rateLimitBackoffMs,
  retryDecision,
} from "../src/retry.mjs";

test("the policy constants mirror the hooks-side 429 handler", () => {
  assert.deepEqual([...RETRYABLE_ONCE], ["win-arg-limit"]);
  assert.equal(RATE_LIMIT_MAX_ATTEMPTS, 6);
  assert.equal(RATE_LIMIT_BASE_BACKOFF_MS, 1000);
});

test("the backoff schedule doubles deterministically and totals 31 s", () => {
  const schedule = [1, 2, 3, 4, 5].map((attempt) => rateLimitBackoffMs(attempt));
  assert.deepEqual(schedule, [1000, 2000, 4000, 8000, 16000]);
  assert.equal(schedule.reduce((total, wait) => total + wait, 0), 31000);
  // No jitter here by design: jitter needs entropy, and this package stays byte-reproducible.
  assert.equal(rateLimitBackoffMs(1), rateLimitBackoffMs(1));
});

test("an attempt below 1 is refused", () => {
  assert.throws(() => rateLimitBackoffMs(0), /attempt must be >= 1/u);
  assert.throws(() => planRetry("win-arg-limit", { attempt: 0 }), /attempt must be >= 1/u);
});

test("win-arg-limit retries exactly ONCE", () => {
  const first = planRetry("win-arg-limit", { attempt: 1 });
  assert.equal(first.retry, true);
  assert.equal(first.nextAttempt, 2);
  assert.equal(first.backoffMs, 0);
  const second = planRetry("win-arg-limit", { attempt: 2 });
  assert.equal(second.retry, false);
  assert.equal(second.nextAttempt, 2);
  assert.match(second.rationale, /already retried once/u);
});

test("rate-limited backs off up to the attempt ceiling, then STOPS", () => {
  for (let attempt = 1; attempt < RATE_LIMIT_MAX_ATTEMPTS; attempt += 1) {
    const decision = planRetry("rate-limited-429", { attempt });
    assert.equal(decision.retry, true);
    assert.equal(decision.nextAttempt, attempt + 1);
    assert.equal(decision.backoffMs, rateLimitBackoffMs(attempt));
  }
  const spent = planRetry("rate-limited-429", { attempt: RATE_LIMIT_MAX_ATTEMPTS });
  assert.equal(spent.retry, false);
  assert.equal(spent.backoffMs, 0);
  assert.match(spent.rationale, /all 6 attempts spent/u);
});

test("matching is on the taxonomy MEMBER, so a suffix cannot disable a retry", () => {
  assert.equal(planRetry("win-arg-limit-34472", { attempt: 1 }).retry, true);
  assert.equal(planRetry("rate-limited", { attempt: 1 }).retry, true);
});

test("every other family stops with no automatic retry", () => {
  for (const reason of ["severed-stream", "policy-violation", "schema-invalid", "timeout-60s"]) {
    const decision = planRetry(reason, { attempt: 1 });
    assert.equal(decision.retry, false, reason);
    assert.equal(decision.backoffMs, 0);
    assert.match(decision.rationale, /no automatic retry/u);
  }
});

test("a reason outside the closed taxonomy is refused", () => {
  assert.throws(() => planRetry("invented", { attempt: 1 }), /not in the closed taxonomy/u);
});

test("decisions are frozen records with an integer backoff", () => {
  const decision = planRetry("rate-limited-429", { attempt: 1 });
  assert.ok(Object.isFrozen(decision));
  assert.ok(Number.isSafeInteger(decision.backoffMs));
});

test("the decision constructor refuses a non-integer or negative backoff", () => {
  // Public for the same reason Python's RetryDecision.__post_init__ is reachable: `backoffMs`
  // is an integer for wire parity (an integral float renders `1.0` in Python and `1` in JS),
  // and a guard nothing can reach is a guard nobody has tested.
  const base = { retry: false, nextAttempt: 1, reason: "timeout-60s", rationale: "r" };
  assert.throws(() => retryDecision({ ...base, backoffMs: 1.5 }), TypeError);
  assert.throws(() => retryDecision({ ...base, backoffMs: true }), TypeError);
  assert.throws(() => retryDecision({ ...base, backoffMs: Number.NaN }), TypeError);
  assert.throws(() => retryDecision({ ...base, backoffMs: -1 }), /backoffMs must be >= 0/u);
  assert.equal(retryDecision({ ...base }).backoffMs, 0);
});
