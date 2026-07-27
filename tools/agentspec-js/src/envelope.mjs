/**
 * The shared OBSERVATION ENVELOPE — the JS mirror of `agentspec/envelope.py`.
 *
 * Four mandatory fields on every adapter / work-unit result:
 * `status` (`success|warning|error`) - `summary` - `next_actions` - `artifacts`.
 *
 * An ERROR path additionally carries a root-cause hint, a safe retry instruction and an
 * EXPLICIT stop condition. "error-only output without next steps" is a named anti-pattern, so
 * `validateObservation` rejects an error envelope with empty `next_actions`.
 *
 * The wire field names stay snake_case: this object is serialised by `canonical.mjs` and must
 * be byte-identical to the Python one, so the WIRE spelling wins over the JS house style.
 */

import { isReason } from "./taxonomy.mjs";

/** The four mandated field names, in wire order. */
export const ENVELOPE_FIELDS = Object.freeze(["status", "summary", "next_actions", "artifacts"]);

export const STATUSES = Object.freeze(["success", "warning", "error"]);

/** The three recovery affordances an error path MUST carry, plus its taxonomy code. */
export function errorDetail({ code, rootCause, retryInstruction, stopCondition }) {
  return Object.freeze({ code, rootCause, retryInstruction, stopCondition });
}

/** One observation. Frozen: a result is a record, never a mutable accumulator. */
export function observation({ status, summary, nextActions = [], artifacts = [], error = null }) {
  return Object.freeze({
    status,
    summary,
    nextActions: Object.freeze([...nextActions]),
    artifacts: Object.freeze([...artifacts]),
    error,
  });
}

/** The wire form: exactly the four fields, plus `error` only when present. */
export function asWire(obs) {
  const payload = {
    status: obs.status,
    summary: obs.summary,
    next_actions: [...obs.nextActions],
    artifacts: [...obs.artifacts],
  };
  if (obs.error !== null) {
    payload.error = {
      code: obs.error.code,
      root_cause: obs.error.rootCause,
      retry_instruction: obs.error.retryInstruction,
      stop_condition: obs.error.stopCondition,
    };
  }
  return payload;
}

export function success(summary, { nextActions = [], artifacts = [] } = {}) {
  return observation({ status: "success", summary, nextActions, artifacts });
}

export function warning(summary, { nextActions = [], artifacts = [] } = {}) {
  return observation({ status: "warning", summary, nextActions, artifacts });
}

/** Build an error envelope. `nextActions` is REQUIRED and must be non-empty. */
export function error(summary, detail, { nextActions, artifacts = [] }) {
  if (nextActions.length === 0) {
    throw new RangeError("error(): nextActions must be non-empty (error-only output is banned)");
  }
  return observation({ status: "error", summary, nextActions, artifacts, error: detail });
}

/** Return the sorted violation ids for `obs`; empty means valid. */
export function validateObservation(obs) {
  const violations = [];
  if (!STATUSES.includes(obs.status)) {
    violations.push("envelope-status-invalid");
  }
  if (obs.summary.trim() === "") {
    violations.push("envelope-summary-empty");
  }
  if (obs.status === "error") {
    violations.push(...validateErrorPath(obs));
  } else if (obs.error !== null) {
    violations.push("envelope-error-unexpected");
  }
  return Object.freeze(violations.sort());
}

/** Violations that only apply when `status === "error"`. */
function validateErrorPath(obs) {
  if (obs.error === null) {
    return ["envelope-error-missing"];
  }
  const violations = [];
  if (obs.nextActions.length === 0) {
    violations.push("envelope-next-actions-empty");
  }
  if (!isReason(obs.error.code)) {
    violations.push("envelope-error-code-unknown");
  }
  if (obs.error.rootCause.trim() === "") {
    violations.push("envelope-error-root-cause-empty");
  }
  if (obs.error.retryInstruction.trim() === "") {
    violations.push("envelope-error-retry-instruction-empty");
  }
  if (obs.error.stopCondition.trim() === "") {
    violations.push("envelope-error-stop-condition-empty");
  }
  return violations;
}
