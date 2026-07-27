/**
 * agentspec-js — the JS runtime for the agentspec workflow SPEC.
 *
 * This barrel re-exports every module under `src/`. That is not cosmetic: it is HALF of the
 * defence against the measured Node coverage-blindness trap (`node --test
 * --experimental-test-coverage` exits 0 while a source file no test imports is absent from the
 * table entirely). The other half is `test/census.test.mjs`, which walks `src/` on DISK and
 * asserts this barrel re-exports every file it finds — a barrel alone cannot close the hole,
 * because a new file nobody adds to the barrel stays invisible.
 *
 * Namespace exports (rather than flat re-exports) are deliberate: `receipt.decode` and
 * `canonical.loads` would otherwise collide, and a rename-to-avoid-collision is exactly the
 * kind of drift that makes a mirror stop mirroring.
 */

export * as argv from "./argv.mjs";
export * as budget from "./budget.mjs";
export * as canonical from "./canonical.mjs";
export * as clock from "./clock.mjs";
export * as corpus from "./corpus.mjs";
export * as dispatchpolicy from "./dispatchpolicy.mjs";
export * as envelope from "./envelope.mjs";
export * as oracle from "./oracle.mjs";
export * as progress from "./progress.mjs";
export * as pysource from "./pysource.mjs";
export * as receipt from "./receipt.mjs";
export * as retry from "./retry.mjs";
export * as spec from "./spec.mjs";
export * as taxonomy from "./taxonomy.mjs";
export * as terminal from "./terminal.mjs";
export * as validate from "./validate.mjs";
export * as version from "./version.mjs";

/**
 * The module basenames this barrel covers, as the census test's expected set.
 *
 * Declared explicitly rather than derived from the export list so the census compares TWO
 * independent statements of the same fact — the disk walk and this literal. A single derived
 * list would agree with itself no matter what was missing.
 */
export const MODULES = Object.freeze([
  "argv",
  "budget",
  "canonical",
  "clock",
  "corpus",
  "dispatchpolicy",
  "envelope",
  "index",
  "oracle",
  "progress",
  "pysource",
  "receipt",
  "retry",
  "spec",
  "taxonomy",
  "terminal",
  "validate",
  "version",
]);
