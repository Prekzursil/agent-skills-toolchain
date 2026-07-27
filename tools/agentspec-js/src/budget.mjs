/**
 * Budget accounting: an immutable ledger that is monotonic and cannot double-count.
 *
 * The JS mirror of `agentspec/budget.py`. Every amount is an integer count of MICRO-units.
 * Non-integers are refused at the boundary, not merely discouraged: an integral float
 * serialises as `1.0` from Python and `1` from JS, and `-0.0`/`1e16` diverge too. Refusing them
 * deletes that whole divergence class from the wire instead of canonicalising it later.
 *
 * `debit` returns a NEW ledger. A counter mutated inside a helper is a measured loss class, so
 * the ledger is a value, not an accumulator.
 */

import { requireWireInteger } from "./wire.mjs";

/** Raised when a debit would exceed the ceiling. Carries the taxonomy reason. */
export class BudgetExhausted extends Error {
  constructor(requestedMicro, remainingMicro) {
    super(
      `budget-exhausted: requested ${requestedMicro} micro, ${remainingMicro} micro remaining`,
    );
    this.name = "BudgetExhausted";
    this.reason = "budget-exhausted";
    this.requestedMicro = requestedMicro;
    this.remainingMicro = remainingMicro;
  }
}

/** One charge, keyed by `(unitId, attempt)` so a replay cannot double-count. */
export function debitRecord({ unitId, attempt, micro }) {
  return Object.freeze({ unitId, attempt, micro });
}

/** A budget ceiling plus the ordered debits taken against it. */
export function ledger({ limitMicro, debits = [] }) {
  requireWireInteger(limitMicro, "limit_micro");
  if (limitMicro < 0) {
    throw new RangeError("limitMicro must be >= 0");
  }
  return Object.freeze({ limitMicro, debits: Object.freeze([...debits]) });
}

/** The sum of every debit — the totals ALWAYS reconcile by construction. */
export function spentMicro(book) {
  return book.debits.reduce((total, entry) => total + entry.micro, 0);
}

export function remainingMicro(book) {
  return book.limitMicro - spentMicro(book);
}

export function exhausted(book) {
  return remainingMicro(book) <= 0;
}

/** Return a new ledger with one more debit, or throw. */
export function debit(book, unitId, { attempt, micro }) {
  requireWireInteger(micro, "micro");
  if (micro <= 0) {
    throw new RangeError("micro must be positive (a zero debit is not an observation)");
  }
  if (attempt <= 0) {
    throw new RangeError("attempt must be >= 1");
  }
  if (unitId === "") {
    throw new RangeError("unitId must be non-empty");
  }
  if (book.debits.some((entry) => entry.unitId === unitId && entry.attempt === attempt)) {
    throw new RangeError(`already debited: ${JSON.stringify(unitId)} attempt ${attempt}`);
  }
  const available = remainingMicro(book);
  if (micro > available) {
    throw new BudgetExhausted(micro, available);
  }
  return ledger({
    limitMicro: book.limitMicro,
    debits: [...book.debits, debitRecord({ unitId, attempt, micro })],
  });
}

/**
 * Cost per SUCCESSFUL task, floor-divided — the benchmark metric that matters.
 *
 * Raw token totals flatter a run that retried a lot; this divides the WHOLE spend (including
 * failed attempts) by the number of units that actually succeeded.
 */
export function costPerSuccess(book, { successes }) {
  requireWireInteger(successes, "successes");
  if (successes < 0) {
    throw new RangeError("successes must be >= 0");
  }
  if (successes === 0) {
    return 0;
  }
  // BigInt, not `Math.floor(a / b)`: the double division is only PROVABLY equal to
  // Python's `//` once both operands are bounded, and proving it for every pair in the
  // range is harder than just doing the exact integer division. The quotient of two
  // wire integers is a wire integer, so the `Number` conversion is lossless.
  return Number(BigInt(spentMicro(book)) / BigInt(successes));
}
