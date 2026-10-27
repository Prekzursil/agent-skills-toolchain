/** The closed failure taxonomy, and the boundary rule that stops a near-miss resolving. */

import assert from "node:assert/strict";
import test from "node:test";

import { REASONS, envMissing, family, isReason, railExit, rateLimited, timeout } from "../src/taxonomy.mjs";

test("the member set is sorted, unique and closed", () => {
  assert.deepEqual([...REASONS], [...REASONS].sort());
  assert.equal(new Set(REASONS).size, REASONS.length);
  assert.ok(Object.isFrozen(REASONS));
});

test("family resolves a bare member and a parametrised one", () => {
  for (const member of REASONS) {
    assert.equal(family(member), member);
    assert.equal(family(`${member}-detail`), member);
    assert.ok(isReason(member));
  }
});

test("the hyphen boundary is REQUIRED, so a near-miss does NOT resolve", () => {
  // The measured lesson: a comparison regex of `[<>=]{1,2}` matched a bare `=` and read an
  // initialiser as a threshold. A prefix matcher must pin the boundary, not just the prefix.
  assert.equal(family("rail-exiting"), "");
  assert.equal(family("timeouts"), "");
  assert.equal(family("schema-invalidate"), "");
  assert.equal(family(""), "");
  assert.equal(family("not-a-reason"), "");
  assert.ok(!isReason("rail-exiting"));
});

test("railExit renders a non-zero exit and REFUSES exit 0", () => {
  assert.equal(railExit(137), "rail-exit-137");
  assert.equal(railExit(-1), "rail-exit--1");
  assert.throws(() => railExit(0), /exit 0 is never a rail failure/u);
});

test("timeout requires a positive, explicit bound", () => {
  assert.equal(timeout(1800), "timeout-1800s");
  assert.throws(() => timeout(0), /must be positive/u);
  assert.throws(() => timeout(-5), /must be positive/u);
});

test("rateLimited accepts only a 4xx/5xx status", () => {
  assert.equal(rateLimited(429), "rate-limited-429");
  assert.equal(rateLimited(400), "rate-limited-400");
  assert.equal(rateLimited(599), "rate-limited-599");
  // Minting `rate-limited-200` would be a reason nobody can act on — that is how a closed
  // taxonomy stops being closed in practice.
  assert.throws(() => rateLimited(200), /not a 4xx\/5xx status/u);
  assert.throws(() => rateLimited(600), /not a 4xx\/5xx status/u);
});

test("envMissing carries the NAME and never the value", () => {
  assert.equal(envMissing("XAI_API_KEY"), "env-missing-XAI_API_KEY");
  assert.throws(() => envMissing(""), /must be non-empty/u);
});

test("every rendered reason resolves back to its own member", () => {
  assert.equal(family(railExit(137)), "rail-exit");
  assert.equal(family(timeout(1800)), "timeout");
  assert.equal(family(rateLimited(429)), "rate-limited");
  assert.equal(family(envMissing("TOKEN")), "env-missing");
});
