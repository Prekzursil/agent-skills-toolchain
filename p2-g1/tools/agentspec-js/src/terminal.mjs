/**
 * TERMINAL-STATE rendering: every unit result is `SUCCESS:<id>` or `FAILED:<id> <reason>`.
 *
 * The JS mirror of `agentspec/terminal.py`. Open-ended prose is the measured driver of
 * repetitive-action loops, and a vague summary was how a severed dispatch got reported as done.
 * So the shape is enforced, not merely recommended: `<id>` may not contain whitespace (it would
 * make the marker unparseable) nor any other control byte (it would render as an escape
 * sequence in the console printing the marker), and `<reason>` must be a taxonomy member.
 *
 * A SEVERED verdict renders `FAILED:<id> severed-stream (<fine-reason>)` — `severed-stream`
 * comes FIRST so a consumer that greps for it matches, while the operator still sees the cause.
 */

import { isReason } from "./taxonomy.mjs";
import { isPrintableId } from "./wire.mjs";

/** Anchored at both ends: a line either IS a terminal marker or it is not. */
export const TERMINAL_RE = /^(?:SUCCESS:\S+|FAILED:\S+ [^\s].*)$/u;

/** Render `SUCCESS:<id>`. */
export function successLine(unitId) {
  return `SUCCESS:${checkedId(unitId)}`;
}

/** Render `FAILED:<id> <reason>` with `reason` checked against the taxonomy. */
export function failureLine(unitId, reason) {
  const checked = checkedId(unitId);
  if (!isReason(reason)) {
    throw new RangeError(`reason ${JSON.stringify(reason)} is not in the closed taxonomy`);
  }
  return `FAILED:${checked} ${reason}`;
}

/**
 * Render any verdict-shaped record as its terminal marker.
 *
 * Duck-typed on purpose: importing the verdict type here would make `oracle.mjs` and this
 * module mutually dependent, and duck-typing keeps the renderer usable by a runtime that
 * carries its own verdict record.
 */
export function terminalLine(verdict) {
  const unitId = String(verdict.unitId ?? "");
  if (verdict.ok === true) {
    return successLine(unitId);
  }
  const reason = String(verdict.reason ?? "");
  if (verdict.severed === true) {
    return `${failureLine(unitId, "severed-stream")} (${reason})`;
  }
  return failureLine(unitId, reason);
}

/**
 * Refuse an id that would corrupt the marker line or the terminal rendering it.
 *
 * The predicate is `wire.isPrintableId`, an EXPLICIT range table, not `/[\p{C}\p{Z}]/u`.
 * A regex property escape reads the ENGINE's Unicode tables and `str.isprintable()` reads
 * the INTERPRETER's; measured, Node 24 (Unicode 17.0) and CPython 3.14 (16.0.0) disagreed
 * on 4,803 code points, and CI's Node 22 is a third table again. A contract must not move
 * when a runtime is upgraded.
 */
function checkedId(unitId) {
  if (!isPrintableId(unitId)) {
    throw new RangeError(
      `unitId must be non-empty, whitespace-free and printable, got ${JSON.stringify(unitId)}`,
    );
  }
  return unitId;
}
