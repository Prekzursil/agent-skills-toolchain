/**
 * THE COMPLETION ORACLE — the JS mirror of `agentspec/oracle.py`, and the most important
 * function in this package.
 *
 * A unit is SUCCESS only on the AND of six clauses:
 *
 *  1. `exit-zero`         — the rail exited 0;
 *  2. `receipt-present`   — the receipt exists (`receiptBytes !== null`);
 *  3. `receipt-non-empty` — it is not blank;
 *  4. `receipt-parses`    — it decodes, and for `fmt: "json"` it parses to an object;
 *  5. `receipt-schema`    — every `requiredFields` key is present and non-blank;
 *  6. `receipt-content`   — no `forbiddenMarkers`, and the body is not a progress stream.
 *
 * **Blocking on process exit is NOT proof of completion.** Exit 0 with a receipt that is
 * missing, empty, unparseable, schema-invalid or "still in progress" is SEVERED, never SUCCESS.
 * Measured: a foreground dispatch returned after 6m59s carrying only a progress prefix, and the
 * caller forwarded that as its terminal result while the job was still running.
 *
 * `verdict.reason` is the FINE cause (for the operator) and `verdict.severed` is the family
 * flag (for consumers matching on `severed-stream`). Both are emitted, so neither audience has
 * to parse the other's string.
 *
 * `judge` also REFUSES a vacuous receipt spec (fail-closed). Only `validateWorkflow` used to
 * catch that, so a consumer that hand-built a spec and called `judge` directly lost the catch
 * and silently ran a two-clause gate.
 */

import { dumps as canonicalDumps } from "./canonical.mjs";
import { errorDetail, error as errorEnvelope, success } from "./envelope.mjs";
import { looksLikeProgress } from "./progress.mjs";
import * as receiptModule from "./receipt.mjs";
import { RATE_LIMIT_MAX_ATTEMPTS } from "./retry.mjs";
import { RECEIPT_FORMATS, isVacuous } from "./spec.mjs";
import { family, railExit } from "./taxonomy.mjs";
import { isBlank, requireWireInteger } from "./wire.mjs";

export const CLAUSES = Object.freeze([
  "exit-zero",
  "receipt-present",
  "receipt-non-empty",
  "receipt-parses",
  "receipt-schema",
  "receipt-content",
]);

/** What a rail hands back. `wallMs` is an integer; a float would break wire parity. */
export function railResult({ exitCode, receiptBytes, progress = "", wallMs = 0 }) {
  // The WIRE spelling (`wall_ms`) is used in the message so the two runtimes emit the
  // same bytes; the JS-side field name stays camelCase.
  requireWireInteger(wallMs, "wall_ms");
  if (wallMs < 0) {
    throw new RangeError("wallMs must be >= 0");
  }
  return Object.freeze({ exitCode, receiptBytes, progress, wallMs });
}

/** The taxonomy reason for a FAILED verdict; the empty string for a successful one. */
export function failureReason(verdict) {
  return verdict.reason ?? "";
}

/** Apply the six-clause AND-gate to `result`. */
export function judge(unitId, result, spec) {
  if (isBlank(unitId)) {
    throw new RangeError("unitId must be non-empty");
  }
  if (!RECEIPT_FORMATS.includes(spec.fmt)) {
    throw new RangeError(`receipt spec fmt must be one of ${JSON.stringify(RECEIPT_FORMATS)}`);
  }
  if (isVacuous(spec)) {
    throw new RangeError(
      "receipt spec is vacuous: a json spec needs requiredFields and a text spec needs " +
        "forbiddenMarkers, or the AND-gate silently reduces to 'exit 0 AND non-empty' and a " +
        "receipt reading 'work is still in progress' reports SUCCESS",
    );
  }

  if (result.exitCode !== 0) {
    return fail(unitId, railExit(result.exitCode), [], result, { severed: false });
  }

  let passed = ["exit-zero"];
  if (result.receiptBytes === null) {
    return fail(unitId, "receipt-missing", passed, result);
  }

  passed = [...passed, "receipt-present"];
  let text;
  try {
    text = receiptModule.decode(result.receiptBytes);
  } catch (cause) {
    return fail(unitId, "receipt-unparseable", passed, result, { detail: cause.message });
  }
  if (isBlank(text)) {
    return fail(unitId, "receipt-empty", passed, result);
  }

  passed = [...passed, "receipt-non-empty"];
  let payload = null;
  if (spec.fmt === "json") {
    try {
      payload = receiptModule.parseJsonObject(text);
    } catch (cause) {
      return fail(unitId, "receipt-unparseable", passed, result, { detail: cause.message });
    }
  }

  passed = [...passed, "receipt-parses"];
  if (payload !== null) {
    const absent = receiptModule.missingFields(payload, spec);
    if (absent.length > 0) {
      return fail(unitId, "schema-invalid", passed, result, {
        detail: `schema-invalid: missing or blank ${canonicalDumps(absent)}`,
      });
    }
  }

  passed = [...passed, "receipt-schema"];
  const markers = receiptModule.presentMarkers(text, spec);
  if (markers.length > 0) {
    return fail(unitId, "receipt-incomplete", passed, result, {
      detail: `receipt-incomplete: body carries ${canonicalDumps(markers)}`,
    });
  }
  if (looksLikeProgress(text)) {
    return fail(unitId, "progress-stream", passed, result, {
      detail: "progress-stream: the receipt body is a progress/status stream",
    });
  }

  return Object.freeze({
    unitId,
    ok: true,
    reason: null,
    severed: false,
    passedClauses: CLAUSES,
    detail: "all six clauses passed",
    payload,
    text,
    wallMs: result.wallMs,
  });
}

/**
 * Project a verdict onto the shared observation envelope.
 *
 * Every error path carries a root-cause hint, a safe retry instruction and an EXPLICIT stop
 * condition — "error-only output without next steps" is a named anti-pattern.
 */
export function observe(verdict, { artifacts = [] } = {}) {
  if (verdict.ok) {
    return success(`${verdict.unitId}: completed (${verdict.wallMs} ms)`, {
      nextActions: ["consume the receipt payload"],
      artifacts,
    });
  }
  const reason = failureReason(verdict);
  return errorEnvelope(
    `${verdict.unitId}: ${reason}`,
    errorDetail({
      code: reason,
      rootCause: rootCause(verdict, reason),
      retryInstruction: retryInstruction(reason),
      stopCondition: stopCondition(reason),
    }),
    { nextActions: [`resolve ${reason} before treating this unit as done`], artifacts },
  );
}

function fail(unitId, reason, passed, result, { severed = true, detail = "" } = {}) {
  return Object.freeze({
    unitId,
    ok: false,
    reason,
    severed,
    passedClauses: Object.freeze([...passed]),
    detail: detail === "" ? reason : detail,
    payload: null,
    text: null,
    wallMs: result.wallMs,
  });
}

function rootCause(verdict, reason) {
  if (verdict.severed) {
    return (
      `severed-stream: the rail exited 0 but produced no usable work product ` +
      `(${verdict.detail}). Exit 0 is not proof of completion.`
    );
  }
  return `the rail itself failed: ${reason} (${verdict.detail})`;
}

function retryInstruction(reason) {
  if (family(reason) === "rate-limited") {
    return (
      "back off and re-dispatch the SAME unit: planRetry returns the bounded doubling " +
      "schedule; add jitter in the transport, never here"
    );
  }
  if (reason === "receipt-missing") {
    return (
      "re-dispatch the SAME unit once, in the FOREGROUND, with an explicit receipt-path flag " +
      "(never --background)"
    );
  }
  if (reason === "receipt-empty" || reason === "receipt-unparseable") {
    return "re-dispatch the SAME unit once; do not parse the progress stream as a fallback";
  }
  if (reason === "schema-invalid" || reason === "receipt-incomplete" || reason === "progress-stream") {
    return (
      "do NOT retry blindly: the rail returned a real but unusable body, so re-dispatch only " +
      "after the prompt states the required receipt shape"
    );
  }
  return "inspect the diagnostic tail first; retry only after the cause is understood";
}

function stopCondition(reason) {
  if (family(reason) === "rate-limited") {
    return (
      `stop after ${RATE_LIMIT_MAX_ATTEMPTS} attempts and report FAILED <unit> ${reason}; ` +
      `never retry unbounded`
    );
  }
  if (reason === "receipt-missing" || reason === "receipt-empty" || reason === "receipt-unparseable") {
    return "stop after 1 retry and report FAILED severed-stream; never report SUCCESS";
  }
  return `stop immediately and report FAILED <unit> ${reason}; no automatic retry`;
}
