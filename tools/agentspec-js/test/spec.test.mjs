/** The declarative spec types and the vacuity predicate the AND-gate depends on. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  BARRIER_POLICIES,
  ISOLATIONS,
  NODE_KINDS,
  RECEIPT_FORMATS,
  barrier,
  fanOut,
  isVacuous,
  nodeIds,
  pipeline,
  receiptSpec,
  unitById,
  unitIds,
  workUnit,
  workflow,
} from "../src/spec.mjs";

const JSON_RECEIPT = receiptSpec({ fmt: "json", requiredFields: ["result"] });

test("the closed vocabularies are declared", () => {
  assert.deepEqual([...RECEIPT_FORMATS], ["json", "text"]);
  assert.deepEqual([...BARRIER_POLICIES], ["all", "any"]);
  assert.deepEqual([...ISOLATIONS], ["shared", "worktree"]);
  assert.deepEqual([...NODE_KINDS], ["fanout", "barrier", "pipeline"]);
});

test("a json spec is vacuous without requiredFields", () => {
  assert.ok(isVacuous(receiptSpec({ fmt: "json" })));
  assert.ok(!isVacuous(JSON_RECEIPT));
});

test("a text spec is vacuous without forbiddenMarkers", () => {
  assert.ok(isVacuous(receiptSpec({ fmt: "text" })));
  assert.ok(!isVacuous(receiptSpec({ fmt: "text", forbiddenMarkers: ["in progress"] })));
});

test("an UNRECOGNISED format is not vacuous, so one defect is not reported as two ids", () => {
  assert.ok(!isVacuous(receiptSpec({ fmt: "yaml" })));
});

test("a work unit freezes its collections and keeps the safe defaults", () => {
  const unit = workUnit({ id: "u1", prompt: "do it", timeoutS: 600, receipt: JSON_RECEIPT });
  assert.ok(Object.isFrozen(unit));
  assert.deepEqual([...unit.dependsOn], []);
  assert.equal(unit.budgetMicro, 0);
  assert.equal(unit.isolation, "shared");
  assert.deepEqual([...unit.writes], []);
});

test("the node constructors tag their kind", () => {
  assert.equal(fanOut({ id: "f", units: ["u1"] }).kind, "fanout");
  assert.equal(barrier({ id: "b", awaits: ["u1"] }).kind, "barrier");
  assert.equal(pipeline({ id: "p", stages: ["u1", "u2"] }).kind, "pipeline");
});

test("a barrier is null-tolerant by default, so one dead unit cannot deadlock the join", () => {
  const join = barrier({ id: "b", awaits: ["u1"] });
  assert.equal(join.nullTolerant, true);
  assert.equal(join.policy, "all");
  assert.equal(barrier({ id: "b", awaits: ["u1"], nullTolerant: false }).nullTolerant, false);
});

test("ids are reported in DECLARATION order, never sorted", () => {
  const wf = workflow({
    id: "w",
    specVersion: "1",
    units: [
      workUnit({ id: "z", prompt: "p", timeoutS: 1, receipt: JSON_RECEIPT }),
      workUnit({ id: "a", prompt: "p", timeoutS: 1, receipt: JSON_RECEIPT }),
    ],
    nodes: [fanOut({ id: "n2", units: ["z"] }), fanOut({ id: "n1", units: ["a"] })],
    budgetMicro: 0,
  });
  assert.deepEqual(unitIds(wf), ["z", "a"]);
  assert.deepEqual(nodeIds(wf), ["n2", "n1"]);
  assert.equal(unitById(wf, "a").id, "a");
  assert.throws(() => unitById(wf, "nope"), /no work unit with id/u);
});
