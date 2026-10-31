/**
 * The injected CLOCK port. There is no real clock in this package.
 *
 * The JS mirror of `agentspec/clock.py`. Determinism is a regression row: two runs of the same
 * spec must produce identical artifacts, so nothing on the dispatch path may read a wall clock
 * or draw entropy. This module therefore ships NO `SystemClock` — a live transport supplies
 * one, the pure core never does. There is no `Date.now()` anywhere under `src/`.
 */

/** A deterministic clock: time moves ONLY when `advance` is called. */
export class FixedClock {
  #nowMs;

  constructor(startMs = 0) {
    if (startMs < 0) {
      throw new RangeError("startMs must be >= 0");
    }
    this.#nowMs = startMs;
  }

  nowMs() {
    return this.#nowMs;
  }

  /** Move time forward by `ms` and return the new reading. */
  advance(ms) {
    if (!Number.isSafeInteger(ms)) {
      throw new TypeError(`ms must be an integer, not ${JSON.stringify(ms)}`);
    }
    if (ms < 0) {
      throw new RangeError("a clock is monotonic: ms must be >= 0");
    }
    this.#nowMs += ms;
    return this.#nowMs;
  }
}

/** Structural check for the read-only Clock port. */
export function isClock(candidate) {
  return typeof candidate?.nowMs === "function";
}

/**
 * Structural check for the steppable port the fake rail needs.
 *
 * Kept separate from `isClock` so a production consumer can inject a read-only clock while the
 * eval rail demands one it can drive. That also removes a duck-typing branch from the rail: no
 * `clock.advance ?? fallback`, so no untestable arm.
 */
export function isSteppableClock(candidate) {
  return isClock(candidate) && typeof candidate.advance === "function";
}

/** Pure interval over two readings of the SAME clock. */
export function elapsedMs(startMs, endMs) {
  if (endMs < startMs) {
    throw new RangeError("a clock is monotonic: endMs must be >= startMs");
  }
  return endMs - startMs;
}
