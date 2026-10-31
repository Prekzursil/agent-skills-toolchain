/**
 * Validate a workflow and return sorted violation ids — the JS mirror of `agentspec/validate.py`.
 *
 * `VIOLATIONS` is the CLOSED set of ids this module can emit. `test/validate.test.mjs` asserts
 * a one-to-one mapping between `VIOLATIONS` and its own negative-case corpus, so a clause
 * cannot be added without a test that exercises it and a test cannot claim an id the validator
 * never emits. That bidirectional lock is the anti-divergence guard, and `crosslang.test.mjs`
 * additionally pins this tuple against the Python one.
 */

import { SPEC_VERSION } from "./version.mjs";
import { isBlank, sortedWire } from "./wire.mjs";
import { BARRIER_POLICIES, ISOLATIONS, RECEIPT_FORMATS, isVacuous, nodeIds, unitIds } from "./spec.mjs";

export const VIOLATIONS = Object.freeze([
  "barrier-awaits-unknown",
  "barrier-empty",
  "barrier-policy-unknown",
  "budget-total-negative",
  "budget-units-exceed-total",
  "fanout-empty",
  "fanout-unit-duplicate",
  "fanout-unit-unknown",
  "node-id-collides-unit",
  "node-id-duplicate",
  "node-id-empty",
  "pipeline-stage-unknown",
  "pipeline-too-short",
  "spec-version-unsupported",
  "unit-budget-negative",
  "unit-dep-cycle",
  "unit-dep-self",
  "unit-dep-unknown",
  "unit-id-duplicate",
  "unit-id-empty",
  "unit-isolation-unknown",
  "unit-prompt-empty",
  "unit-receipt-clause-vacuous",
  "unit-receipt-format-unknown",
  "unit-timeout-missing",
  "unit-worktree-no-writes",
  "workflow-id-empty",
  "workflow-no-units",
]);

/** Return the sorted, deduplicated violation ids for `wf`. */
export function validateWorkflow(wf) {
  const found = [];
  if (wf.specVersion !== SPEC_VERSION) {
    found.push("spec-version-unsupported");
  }
  if (isBlank(wf.id)) {
    found.push("workflow-id-empty");
  }
  if (wf.units.length === 0) {
    found.push("workflow-no-units");
  }
  if (wf.budgetMicro < 0) {
    found.push("budget-total-negative");
  } else if (declaredUnitBudget(wf) > wf.budgetMicro) {
    found.push("budget-units-exceed-total");
  }

  const known = new Set(unitIds(wf));
  for (const unit of wf.units) {
    found.push(...validateUnit(unit, known));
  }
  found.push(...validateDuplicateUnitIds(wf));
  found.push(...validateCycles(wf));
  found.push(...validateNodes(wf, known));
  return sortedWire(new Set(found));
}

function declaredUnitBudget(wf) {
  return wf.units
    .filter((unit) => unit.budgetMicro > 0)
    .reduce((total, unit) => total + unit.budgetMicro, 0);
}

function validateUnit(unit, known) {
  const found = [];
  if (isBlank(unit.id)) {
    found.push("unit-id-empty");
  }
  if (isBlank(unit.prompt)) {
    found.push("unit-prompt-empty");
  }
  if (unit.timeoutS <= 0) {
    found.push("unit-timeout-missing");
  }
  if (unit.budgetMicro < 0) {
    found.push("unit-budget-negative");
  }
  if (!ISOLATIONS.includes(unit.isolation)) {
    found.push("unit-isolation-unknown");
  } else if (unit.isolation === "worktree" && unit.writes.length === 0) {
    found.push("unit-worktree-no-writes");
  }
  found.push(...validateReceipt(unit));
  for (const dep of unit.dependsOn) {
    if (dep === unit.id) {
      found.push("unit-dep-self");
    } else if (!known.has(dep)) {
      found.push("unit-dep-unknown");
    }
  }
  return found;
}

/** A receipt spec must give the AND-gate a NON-VACUOUS content clause. */
function validateReceipt(unit) {
  if (!RECEIPT_FORMATS.includes(unit.receipt.fmt)) {
    return ["unit-receipt-format-unknown"];
  }
  if (isVacuous(unit.receipt)) {
    return ["unit-receipt-clause-vacuous"];
  }
  return [];
}

function validateDuplicateUnitIds(wf) {
  const ids = unitIds(wf);
  if (new Set(ids).size !== ids.length) {
    return ["unit-id-duplicate"];
  }
  return [];
}

/**
 * Depth-first cycle detection over `dependsOn`.
 *
 * Self-edges are reported as `unit-dep-self` by `validateUnit` and are skipped here so one
 * defect does not produce two ids.
 */
function validateCycles(wf) {
  const edges = new Map(
    wf.units.map((unit) => [unit.id, unit.dependsOn.filter((dep) => dep !== unit.id)]),
  );
  const state = new Map();

  const walk = (node) => {
    if (state.get(node) === 1) {
      return true;
    }
    if (state.get(node) === 2) {
      return false;
    }
    state.set(node, 1);
    // `walk` is only ever called with a key that IS in `edges` (the outer loop iterates
    // `edges.keys()` and the recursion is guarded by `edges.has`), so no `?? []` fallback:
    // an unreachable fallback is an uncoverable branch, i.e. a self-inflicted coverage hole.
    for (const next of edges.get(node)) {
      if (edges.has(next) && walk(next)) {
        return true;
      }
    }
    state.set(node, 2);
    return false;
  };

  for (const unitId of edges.keys()) {
    if (walk(unitId)) {
      return ["unit-dep-cycle"];
    }
  }
  return [];
}

function validateNodes(wf, knownUnits) {
  const found = [];
  const ids = nodeIds(wf);
  if (new Set(ids).size !== ids.length) {
    found.push("node-id-duplicate");
  }
  const addressable = new Set([...knownUnits, ...ids]);
  for (const node of wf.nodes) {
    if (isBlank(node.id)) {
      found.push("node-id-empty");
    } else if (knownUnits.has(node.id)) {
      found.push("node-id-collides-unit");
    }
    found.push(...validateNodeBody(node, knownUnits, addressable));
  }
  return found;
}

function validateNodeBody(node, knownUnits, addressable) {
  if (node.kind === "fanout") {
    return validateFanOut(node, knownUnits);
  }
  if (node.kind === "barrier") {
    return validateBarrier(node, addressable);
  }
  return validatePipeline(node, knownUnits);
}

function validateFanOut(node, knownUnits) {
  const found = [];
  if (node.units.length === 0) {
    found.push("fanout-empty");
  }
  if (new Set(node.units).size !== node.units.length) {
    found.push("fanout-unit-duplicate");
  }
  if (node.units.some((unit) => !knownUnits.has(unit))) {
    found.push("fanout-unit-unknown");
  }
  return found;
}

/** A barrier may await a unit OR another node (a fan-out), so it uses `addressable`. */
function validateBarrier(node, addressable) {
  const found = [];
  if (node.awaits.length === 0) {
    found.push("barrier-empty");
  }
  if (!BARRIER_POLICIES.includes(node.policy)) {
    found.push("barrier-policy-unknown");
  }
  if (node.awaits.some((await_) => !addressable.has(await_))) {
    found.push("barrier-awaits-unknown");
  }
  return found;
}

function validatePipeline(node, knownUnits) {
  const found = [];
  if (node.stages.length < 2) {
    found.push("pipeline-too-short");
  }
  if (node.stages.some((stage) => !knownUnits.has(stage))) {
    found.push("pipeline-stage-unknown");
  }
  return found;
}
