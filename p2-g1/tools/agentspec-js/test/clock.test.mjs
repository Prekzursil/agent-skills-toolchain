/** The injected clock port. There is deliberately no real clock in this package. */

import assert from "node:assert/strict";
import test from "node:test";

import { FixedClock, elapsedMs, isClock, isSteppableClock } from "../src/clock.mjs";

test("time moves ONLY when advance is called", () => {
  const clock = new FixedClock();
  assert.equal(clock.nowMs(), 0);
  assert.equal(clock.nowMs(), 0, "reading the clock must not move it");
  assert.equal(clock.advance(250), 250);
  assert.equal(clock.nowMs(), 250);
  assert.equal(clock.advance(0), 250, "a zero step is legal and is a no-op");
});

test("a start offset is honoured and a negative one refused", () => {
  assert.equal(new FixedClock(1000).nowMs(), 1000);
  assert.throws(() => new FixedClock(-1), /startMs must be >= 0/u);
});

test("a clock is monotonic: a negative or non-integer step is refused", () => {
  const clock = new FixedClock();
  assert.throws(() => clock.advance(-1), /a clock is monotonic/u);
  assert.throws(() => clock.advance(1.5), TypeError);
  assert.throws(() => clock.advance(true), TypeError);
  assert.equal(clock.nowMs(), 0, "a refused step must not move the clock");
});

test("the port predicates distinguish read-only from steppable", () => {
  const clock = new FixedClock();
  assert.ok(isClock(clock));
  assert.ok(isSteppableClock(clock));
  const readOnly = { nowMs: () => 5 };
  assert.ok(isClock(readOnly));
  assert.ok(!isSteppableClock(readOnly), "a read-only clock is not steppable");
  assert.ok(!isClock({}));
  assert.ok(!isClock(null));
  assert.ok(!isClock(undefined));
});

test("elapsedMs is a pure interval over two readings of the SAME clock", () => {
  assert.equal(elapsedMs(100, 350), 250);
  assert.equal(elapsedMs(100, 100), 0);
  assert.throws(() => elapsedMs(350, 100), /a clock is monotonic/u);
});

test("the internal reading is private, so it cannot be rewound from outside", () => {
  const clock = new FixedClock(10);
  assert.deepEqual(Object.keys(clock), []);
  clock.advance(5);
  assert.equal(clock.nowMs(), 15);
});
