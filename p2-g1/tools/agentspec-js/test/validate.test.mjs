/**
 * Workflow validation, with the BIDIRECTIONAL lock the Python suite uses.
 *
 * The final test asserts a one-to-one mapping between `VIOLATIONS` and the negative-case corpus
 * below: a clause cannot be added without a test that exercises it, and a test cannot claim an
 * id the validator never emits. That is the anti-divergence guard.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { barrier, fanOut, pipeline, receiptSpec, workUnit, workflow } from "../src/spec.mjs";
import { VIOLATIONS, validateWorkflow } from "../src/validate.mjs";
import { SPEC_VERSION } from "../src/version.mjs";

const RECEIPT = receiptSpec({ fmt: "json", requiredFields: ["result"] });

function unit(overrides = {}) {
  return workUnit({ id: "u1", prompt: "do it", timeoutS: 600, receipt: RECEIPT, ...overrides });
}

function wf(overrides = {}) {
  return workflow({
    id: "w1",
    specVersion: SPEC_VERSION,
    units: [unit()],
    nodes: [],
    budgetMicro: 0,
    ...overrides,
  });
}

/** `[violation id, workflow]` — the negative corpus the bidirectional lock is computed over. */
const CASES = [
  ["spec-version-unsupported", wf({ specVersion: "99" })],
  ["workflow-id-empty", wf({ id: "  " })],
  ["workflow-no-units", wf({ units: [] })],
  ["budget-total-negative", wf({ budgetMicro: -1 })],
  ["budget-units-exceed-total", wf({ units: [unit({ budgetMicro: 500 })], budgetMicro: 100 })],
  ["unit-id-empty", wf({ units: [unit({ id: " " })] })],
  ["unit-prompt-empty", wf({ units: [unit({ prompt: "  " })] })],
  ["unit-timeout-missing", wf({ units: [unit({ timeoutS: 0 })] })],
  ["unit-budget-negative", wf({ units: [unit({ budgetMicro: -1 })] })],
  ["unit-isolation-unknown", wf({ units: [unit({ isolation: "container" })] })],
  ["unit-worktree-no-writes", wf({ units: [unit({ isolation: "worktree" })] })],
  ["unit-receipt-format-unknown", wf({ units: [unit({ receipt: receiptSpec({ fmt: "yaml" }) })] })],
  ["unit-receipt-clause-vacuous", wf({ units: [unit({ receipt: receiptSpec({ fmt: "json" }) })] })],
  ["unit-dep-self", wf({ units: [unit({ dependsOn: ["u1"] })] })],
  ["unit-dep-unknown", wf({ units: [unit({ dependsOn: ["ghost"] })] })],
  ["unit-id-duplicate", wf({ units: [unit(), unit()] })],
  [
    "unit-dep-cycle",
    wf({ units: [unit({ id: "a", dependsOn: ["b"] }), unit({ id: "b", dependsOn: ["a"] })] }),
  ],
  ["node-id-empty", wf({ nodes: [fanOut({ id: " ", units: ["u1"] })] })],
  ["node-id-collides-unit", wf({ nodes: [fanOut({ id: "u1", units: ["u1"] })] })],
  [
    "node-id-duplicate",
    wf({ nodes: [fanOut({ id: "n", units: ["u1"] }), fanOut({ id: "n", units: ["u1"] })] }),
  ],
  ["fanout-empty", wf({ nodes: [fanOut({ id: "n", units: [] })] })],
  ["fanout-unit-duplicate", wf({ nodes: [fanOut({ id: "n", units: ["u1", "u1"] })] })],
  ["fanout-unit-unknown", wf({ nodes: [fanOut({ id: "n", units: ["ghost"] })] })],
  ["barrier-empty", wf({ nodes: [barrier({ id: "n", awaits: [] })] })],
  ["barrier-policy-unknown", wf({ nodes: [barrier({ id: "n", awaits: ["u1"], policy: "most" })] })],
  ["barrier-awaits-unknown", wf({ nodes: [barrier({ id: "n", awaits: ["ghost"] })] })],
  ["pipeline-too-short", wf({ nodes: [pipeline({ id: "n", stages: ["u1"] })] })],
  ["pipeline-stage-unknown", wf({ nodes: [pipeline({ id: "n", stages: ["u1", "ghost"] })] })],
];

for (const [violation, broken] of CASES) {
  test(`${violation} is detected`, () => {
    assert.ok(
      validateWorkflow(broken).includes(violation),
      `expected ${violation}, got ${JSON.stringify(validateWorkflow(broken))}`,
    );
  });
}

test("a well-formed workflow reports NOTHING", () => {
  const clean = workflow({
    id: "w1",
    specVersion: SPEC_VERSION,
    units: [
      unit({ id: "a", budgetMicro: 100 }),
      unit({ id: "b", dependsOn: ["a"], isolation: "worktree", writes: ["src/x.mjs"] }),
    ],
    nodes: [
      fanOut({ id: "phase-1", units: ["a", "b"] }),
      barrier({ id: "join", awaits: ["phase-1"] }),
      pipeline({ id: "chain", stages: ["a", "b"] }),
    ],
    budgetMicro: 1000,
  });
  assert.deepEqual([...validateWorkflow(clean)], []);
});

test("a barrier may await another NODE, not only a unit", () => {
  const clean = wf({
    nodes: [fanOut({ id: "phase-1", units: ["u1"] }), barrier({ id: "join", awaits: ["phase-1"] })],
  });
  assert.deepEqual([...validateWorkflow(clean)], []);
});

test("results are sorted and deduplicated", () => {
  const broken = wf({ units: [unit({ id: " " }), unit({ id: " " })] });
  const found = validateWorkflow(broken);
  assert.deepEqual([...found], [...found].sort());
  assert.equal(new Set(found).size, found.length);
});

test("a self-edge is reported ONCE as unit-dep-self, never also as a cycle", () => {
  const found = validateWorkflow(wf({ units: [unit({ dependsOn: ["u1"] })] }));
  assert.ok(found.includes("unit-dep-self"));
  assert.ok(!found.includes("unit-dep-cycle"), "one defect must not produce two ids");
});

test("a diamond dependency is NOT a cycle", () => {
  const diamond = wf({
    units: [
      unit({ id: "a" }),
      unit({ id: "b", dependsOn: ["a"] }),
      unit({ id: "c", dependsOn: ["a"] }),
      unit({ id: "d", dependsOn: ["b", "c"] }),
    ],
  });
  assert.deepEqual([...validateWorkflow(diamond)], []);
});

test("a zero-budget unit does not count against the total", () => {
  assert.deepEqual([...validateWorkflow(wf({ units: [unit({ budgetMicro: 0 })], budgetMicro: 0 }))], []);
});

test("VIOLATIONS and the negative corpus map ONE-TO-ONE", () => {
  // The bidirectional lock. Neither side can grow without the other.
  const covered = [...new Set(CASES.map(([violation]) => violation))].sort();
  assert.deepEqual(covered, [...VIOLATIONS]);
  const emitted = new Set(CASES.flatMap(([, broken]) => validateWorkflow(broken)));
  for (const violation of emitted) {
    assert.ok(VIOLATIONS.includes(violation), `${violation} is emitted but not declared`);
  }
});
