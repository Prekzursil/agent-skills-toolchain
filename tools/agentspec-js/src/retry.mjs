/**
 * RETRY POLICY — pure, and deliberately almost empty. The JS mirror of `agentspec/retry.py`.
 *
 * Exactly two families retry, and both are BOUNDED:
 *  - `win-arg-limit` retries EXACTLY once (route the prompt to a file/stdin and try again);
 *  - `rate-limited` retries up to `RATE_LIMIT_MAX_ATTEMPTS` total attempts with a deterministic
 *    doubling backoff.
 *
 * Everything else stops. A blind retry on a severed stream re-runs work that may already have
 * landed, and a blind retry on a policy violation just re-violates the policy.
 *
 * **JITTER IS DELIBERATELY ABSENT.** Jitter needs entropy, and this package is hermetic so that
 * every eval row stays byte-reproducible. agentspec supplies the deterministic SCHEDULE; the
 * transport shim adds jitter to it.
 */

import { family } from "./taxonomy.mjs";
import { requireWireInteger } from "./wire.mjs";

export const RETRYABLE_ONCE = Object.freeze(["win-arg-limit"]);

/** Total attempts for a rate limit: 1 initial + 5 retries. */
export const RATE_LIMIT_MAX_ATTEMPTS = 6;

/** First wait, in ms. Doubles per attempt, so the full schedule is 1+2+4+8+16 = 31 s. */
export const RATE_LIMIT_BASE_BACKOFF_MS = 1000;

/**
 * Whether to retry, which attempt number comes next, WHY, and how long to wait first.
 *
 * `backoffMs` is 0 for every non-rate-limited decision, so a consumer may sleep it
 * unconditionally. It is an INTEGER for the same wire-parity reason as `wallMs`: an integral
 * float renders `1.0` in Python and `1` in JS.
 */
export function retryDecision({ retry, nextAttempt, reason, rationale, backoffMs = 0 }) {
  requireWireInteger(backoffMs, "backoff_ms");
  if (backoffMs < 0) {
    throw new RangeError("backoffMs must be >= 0");
  }
  return Object.freeze({ retry, nextAttempt, reason, rationale, backoffMs });
}

/**
 * The wait before the retry that follows `attempt`. Pure: no clock, no entropy.
 *
 * The domain is BOUNDED to the declared schedule. Unbounded, the doubling leaves the
 * range both runtimes represent exactly: measured `rateLimitBackoffMs(60)` gave
 * `576460752303423500000` here (a rounded double) and `576460752303423488000` in Python
 * (an exact int). Nothing legitimately asks for attempt 60 — the ceiling is
 * `RATE_LIMIT_MAX_ATTEMPTS` — so refusing is strictly better than diverging.
 */
export function rateLimitBackoffMs(attempt) {
  if (attempt <= 0) {
    throw new RangeError("attempt must be >= 1");
  }
  if (attempt > RATE_LIMIT_MAX_ATTEMPTS) {
    throw new RangeError(
      `attempt must be <= RATE_LIMIT_MAX_ATTEMPTS (${RATE_LIMIT_MAX_ATTEMPTS})`,
    );
  }
  return RATE_LIMIT_BASE_BACKOFF_MS * 2 ** (attempt - 1);
}

/**
 * Decide whether `reason` on `attempt` earns another try.
 *
 * Matching is on the taxonomy MEMBER, so `win-arg-limit-34472` and `rate-limited-429` get the
 * same policy as their bare forms — a suffix must not silently disable a retry.
 */
export function planRetry(reason, { attempt }) {
  if (attempt <= 0) {
    throw new RangeError("attempt must be >= 1");
  }
  const member = family(reason);
  if (member === "") {
    throw new RangeError(`reason ${JSON.stringify(reason)} is not in the closed taxonomy`);
  }
  if (member === "rate-limited") {
    return planRateLimited(reason, attempt);
  }
  if (!RETRYABLE_ONCE.includes(member)) {
    return retryDecision({
      retry: false,
      nextAttempt: attempt,
      reason,
      rationale: `no automatic retry for ${reason}`,
    });
  }
  if (attempt >= 2) {
    return retryDecision({
      retry: false,
      nextAttempt: attempt,
      reason,
      rationale: `already retried once for ${reason}; stop`,
    });
  }
  return retryDecision({
    retry: true,
    nextAttempt: attempt + 1,
    reason,
    rationale: "retry once with the prompt routed to a file/stdin",
  });
}

/** Bounded backoff. The EXPLICIT stop condition is the attempt ceiling, never a loop. */
function planRateLimited(reason, attempt) {
  if (attempt >= RATE_LIMIT_MAX_ATTEMPTS) {
    return retryDecision({
      retry: false,
      nextAttempt: attempt,
      reason,
      rationale:
        `rate-limited: all ${RATE_LIMIT_MAX_ATTEMPTS} attempts spent; stop and report FAILED`,
    });
  }
  const waitMs = rateLimitBackoffMs(attempt);
  return retryDecision({
    retry: true,
    nextAttempt: attempt + 1,
    reason,
    rationale:
      `rate-limited: back off ${waitMs} ms, then retry as attempt ` +
      `${attempt + 1} of ${RATE_LIMIT_MAX_ATTEMPTS}`,
    backoffMs: waitMs,
  });
}
