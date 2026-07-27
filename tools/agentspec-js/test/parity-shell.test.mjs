/**
 * `parity/` is EXCLUDED from the coverage gate, so this test stops logic hiding there.
 *
 * The exclusion is deliberate and narrow: `parity/*` are executable scripts exercised
 * end-to-end by `npm run parity` in CI, not unit-tested modules, and forcing them into the
 * census would mean unit-testing `spawnSync` plumbing. But "excluded from coverage" is exactly
 * the shape of the blindness trap this package exists to defeat, so the exclusion is bounded by
 * an ALLOWLIST plus a line budget: real logic cannot migrate out of `src/` to dodge the gate.
 */

import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const PARITY_DIR = fileURLToPath(new URL("../parity/", import.meta.url));

/**
 * Every file allowed to live uncovered in `parity/`, with its maximum code-line budget.
 *
 * `emit_py.py` has the largest budget for a stated reason, not a convenient one: it carries the
 * PYTHON half of the corpus DSL builder, mirroring `src/corpus.mjs`. That half cannot live in
 * `agentspec` — the Python package is a zero-dependency runtime held at 100% coverage, and
 * putting test-harness code in it would be neither minimal nor additive. It is not
 * line-coverage-measured, but it is not unexercised either: the parity oracle drives every one
 * of its branches across all 88 corpus cases and FAILS if any case disagrees with its
 * expectation, so a defect in the builder cannot pass silently. What the budget protects
 * against is CANONICALISATION logic migrating here, which the delegation test below pins.
 */
const ALLOWLIST = new Map([
  ["emit_js.mjs", 30],
  ["emit_py.py", 110],
  ["oracle.mjs", 70],
]);

function codeLines(path) {
  return readFileSync(path, "utf8")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "" && !line.startsWith("//") && !line.startsWith("#") && !line.startsWith("*") && !line.startsWith("/*") && !line.startsWith('"""')).length;
}

test("parity/ contains exactly the allowlisted shells", () => {
  const present = readdirSync(PARITY_DIR).sort();
  assert.deepEqual(present, [...ALLOWLIST.keys()].sort(), "a new file appeared in the uncovered parity/ directory");
});

test("each parity shell stays THIN, so logic cannot migrate out of the coverage gate", () => {
  for (const [name, budget] of ALLOWLIST) {
    const measured = codeLines(`${PARITY_DIR}${name}`);
    assert.ok(
      measured <= budget,
      `parity/${name} has ${measured} code lines, budget ${budget}; move the logic into src/`,
    );
  }
});

test("the emitters delegate to the COVERED modules rather than reimplementing them", () => {
  const emitJs = readFileSync(`${PARITY_DIR}emit_js.mjs`, "utf8");
  assert.match(emitJs, /from "\.\.\/src\/corpus\.mjs"/u);
  assert.ok(
    !emitJs.includes("src/canonical.mjs"),
    "the emitter must reach canonicalisation THROUGH the covered corpus module",
  );
  const emitPy = readFileSync(`${PARITY_DIR}emit_py.py`, "utf8");
  assert.match(emitPy, /from agentspec\.canonical import/u);
});

test("both emitters write BINARY with explicit LF", () => {
  // A text-mode write on Windows appends CR and every downstream byte comparison becomes a
  // false mismatch — measured as 209,442 phantom failures in the scout probe.
  assert.match(readFileSync(`${PARITY_DIR}emit_js.mjs`, "utf8"), /writeFileSync\(process\.argv\[2\], Buffer\.from\(/u);
  assert.match(readFileSync(`${PARITY_DIR}emit_py.py`, "utf8"), /write_bytes\(/u);
});
