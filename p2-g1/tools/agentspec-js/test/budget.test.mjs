/** The immutable budget ledger: monotonic, reconciling, and unable to double-count. */

import assert from "node:assert/strict";
import test from "node:test";

import { capture } from "./helpers.mjs";

import {
  BudgetExhausted,
  costPerSuccess,
  debit,
  debitRecord,
  exhausted,
  ledger,
  remainingMicro,
  spentMicro,
} from "../src/budget.mjs";

test("a fresh ledger reconciles at zero spend", () => {
  const book = ledger({ limitMicro: 1000 });
  assert.equal(spentMicro(book), 0);
  assert.equal(remainingMicro(book), 1000);
  assert.equal(exhausted(book), false);
  assert.ok(Object.isFrozen(book));
});

test("a negative ceiling is refused", () => {
  assert.throws(() => ledger({ limitMicro: -1 }), /limitMicro must be >= 0/u);
});

test("debit returns a NEW ledger and the totals always reconcile", () => {
  // A counter mutated inside a helper is a measured loss class, so the ledger is a value.
  const start = ledger({ limitMicro: 1000 });
  const after = debit(start, "wu-1", { attempt: 1, micro: 400 });
  assert.equal(spentMicro(start), 0, "the original ledger must not mutate");
  assert.equal(spentMicro(after), 400);
  assert.equal(remainingMicro(after), 600);
  const twice = debit(after, "wu-1", { attempt: 2, micro: 600 });
  assert.equal(spentMicro(twice), 1000);
  assert.equal(exhausted(twice), true);
});

test("the same (unit, attempt) cannot be charged twice", () => {
  const book = debit(ledger({ limitMicro: 1000 }), "wu-1", { attempt: 1, micro: 10 });
  assert.throws(() => debit(book, "wu-1", { attempt: 1, micro: 10 }), /already debited/u);
  // A different attempt for the same unit IS a distinct charge.
  assert.equal(spentMicro(debit(book, "wu-1", { attempt: 2, micro: 10 })), 20);
});

test("a debit past the ceiling raises with the budget-exhausted reason", () => {
  const book = ledger({ limitMicro: 100 });
  const caught = capture(() => debit(book, "wu-1", { attempt: 1, micro: 101 }));
  assert.ok(caught instanceof BudgetExhausted, `expected BudgetExhausted, got ${caught}`);
  assert.equal(caught.reason, "budget-exhausted");
  assert.equal(caught.requestedMicro, 101);
  assert.equal(caught.remainingMicro, 100);
  // Exactly the remaining amount is allowed.
  assert.equal(spentMicro(debit(book, "wu-1", { attempt: 1, micro: 100 })), 100);
});

test("a non-integer, zero, negative or bool amount is refused at the boundary", () => {
  const book = ledger({ limitMicro: 1000 });
  // Floats are refused rather than canonicalised later: an integral float serialises as `1.0`
  // from Python and `1` from JS. Refusing deletes the divergence class from the wire.
  assert.throws(() => debit(book, "wu-1", { attempt: 1, micro: 1.5 }), TypeError);
  assert.throws(() => debit(book, "wu-1", { attempt: 1, micro: true }), TypeError);
  assert.throws(() => debit(book, "wu-1", { attempt: 1, micro: Number.NaN }), TypeError);
  assert.throws(() => debit(book, "wu-1", { attempt: 1, micro: 0 }), /must be positive/u);
  assert.throws(() => debit(book, "wu-1", { attempt: 1, micro: -5 }), /must be positive/u);
});

test("an invalid attempt or unit id is refused", () => {
  const book = ledger({ limitMicro: 1000 });
  assert.throws(() => debit(book, "wu-1", { attempt: 0, micro: 10 }), /attempt must be >= 1/u);
  assert.throws(() => debit(book, "", { attempt: 1, micro: 10 }), /unitId must be non-empty/u);
});

test("cost per success divides the WHOLE spend, including failed attempts", () => {
  let book = ledger({ limitMicro: 1000 });
  book = debit(book, "wu-1", { attempt: 1, micro: 300 });
  book = debit(book, "wu-1", { attempt: 2, micro: 200 });
  book = debit(book, "wu-2", { attempt: 1, micro: 200 });
  // 700 micro spent, 2 units succeeded -> 350, not 200. Raw totals flatter a retrying run.
  assert.equal(costPerSuccess(book, { successes: 2 }), 350);
  assert.equal(costPerSuccess(book, { successes: 3 }), 233, "floor division");
});

test("zero successes is 0, and a negative count is refused", () => {
  const book = debit(ledger({ limitMicro: 100 }), "wu-1", { attempt: 1, micro: 50 });
  assert.equal(costPerSuccess(book, { successes: 0 }), 0);
  assert.throws(() => costPerSuccess(book, { successes: -1 }), /successes must be >= 0/u);
});

test("a debit record is a frozen value", () => {
  const record = debitRecord({ unitId: "wu-1", attempt: 1, micro: 10 });
  assert.ok(Object.isFrozen(record));
  assert.deepEqual({ ...record }, { unitId: "wu-1", attempt: 1, micro: 10 });
});
