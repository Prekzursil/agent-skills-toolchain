/**
 * The vendor-neutral workflow SPEC — the JS mirror of `agentspec/spec.py`.
 *
 * The Python module is the SINGLE SOURCE OF TRUTH; this file translates it, it does not fork
 * it. `test/crosslang.test.mjs` asserts the three closed vocabularies below still equal the
 * Python tuples.
 *
 * Design rules carried over verbatim, each with a measured reason:
 *
 *  - **Frozen records.** A work-unit result is a record; a counter mutated inside a helper is a
 *    measured loss class.
 *  - **Integers only for anything numeric on the wire.** `wallMs`, `budgetMicro`, `timeoutS` are
 *    integers. An integral float round-trips as `1.0` in Python and `1` in JS — one of the
 *    measured canonicalisation divergences, deleted at the boundary rather than papered over.
 *  - **No defaults that hide a hazard.** `timeoutS` has no default: "no dispatch without an
 *    explicit timeout" is a regression row.
 *  - **A worktree unit declares its `writes`.** File-disjoint agents share one git index and a
 *    broad `git add` sweeps a sibling's files.
 */

export const RECEIPT_FORMATS = Object.freeze(["json", "text"]);
export const BARRIER_POLICIES = Object.freeze(["all", "any"]);
export const ISOLATIONS = Object.freeze(["shared", "worktree"]);

export const NODE_KINDS = Object.freeze(["fanout", "barrier", "pipeline"]);

/**
 * How a unit's receipt is recognised as a real work product.
 *
 * `requiredFields` (json) and `forbiddenMarkers` (text) are what stop the completion AND-gate's
 * content clause from being VACUOUS. Measured failure this prevents: a rail exits 0 having
 * written a non-empty text receipt saying "work is still in progress", and a two-clause gate
 * reports SUCCESS.
 */
export function receiptSpec({ fmt, requiredFields = [], forbiddenMarkers = [] }) {
  return Object.freeze({
    fmt,
    requiredFields: Object.freeze([...requiredFields]),
    forbiddenMarkers: Object.freeze([...forbiddenMarkers]),
  });
}

/**
 * True when this spec gives the AND-gate NO content clause for its own format.
 *
 * The ONE predicate shared by `validateWorkflow` (which reports `unit-receipt-clause-vacuous`)
 * and `judge` (which refuses outright), so a consumer that skips the Workflow layer cannot lose
 * the catch. An unrecognised `fmt` is NOT vacuous: both call sites reject an unknown format
 * first, and answering true here would report one defect as two ids.
 */
export function isVacuous(spec) {
  if (spec.fmt === "json") {
    return spec.requiredFields.length === 0;
  }
  if (spec.fmt === "text") {
    return spec.forbiddenMarkers.length === 0;
  }
  return false;
}

/** One dispatchable unit of work. */
export function workUnit({
  id,
  prompt,
  timeoutS,
  receipt,
  dependsOn = [],
  budgetMicro = 0,
  isolation = "shared",
  writes = [],
}) {
  return Object.freeze({
    id,
    prompt,
    timeoutS,
    receipt,
    dependsOn: Object.freeze([...dependsOn]),
    budgetMicro,
    isolation,
    writes: Object.freeze([...writes]),
  });
}

/** Run `units` concurrently. The receipt set MUST equal the unit set. */
export function fanOut({ id, units }) {
  return Object.freeze({ kind: "fanout", id, units: Object.freeze([...units]) });
}

/**
 * Join on `awaits`.
 *
 * `nullTolerant` defaults true: a unit that died and produced no result must not deadlock the
 * join — the measured shape is one hung agent stalling a whole phase.
 */
export function barrier({ id, awaits, policy = "all", nullTolerant = true }) {
  return Object.freeze({
    kind: "barrier",
    id,
    awaits: Object.freeze([...awaits]),
    policy,
    nullTolerant,
  });
}

/** Run `stages` in order. Distinct from a barrier: no cohort, so one slow stage cannot block
 * a sibling cohort. */
export function pipeline({ id, stages }) {
  return Object.freeze({ kind: "pipeline", id, stages: Object.freeze([...stages]) });
}

/** A whole declarative workflow: units, the graph over them, and the budget ceiling. */
export function workflow({ id, specVersion, units, nodes, budgetMicro }) {
  return Object.freeze({
    id,
    specVersion,
    units: Object.freeze([...units]),
    nodes: Object.freeze([...nodes]),
    budgetMicro,
  });
}

/** Declared unit ids in declaration order (never sorted — order is data). */
export function unitIds(wf) {
  return wf.units.map((unit) => unit.id);
}

/** Declared node ids in declaration order. */
export function nodeIds(wf) {
  return wf.nodes.map((node) => node.id);
}

/** Look up a declared unit, throwing when it is absent. */
export function unitById(wf, unitId) {
  for (const unit of wf.units) {
    if (unit.id === unitId) {
      return unit;
    }
  }
  throw new RangeError(`no work unit with id ${JSON.stringify(unitId)}`);
}
