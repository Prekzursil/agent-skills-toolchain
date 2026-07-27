/**
 * Receipt decoding, parsing and content checks — the raw material of the AND-gate.
 *
 * The JS mirror of `agentspec/receipt.py`. Kept separate from `oracle.mjs` so each function is
 * single-purpose and each failure mode maps to exactly one taxonomy reason.
 */

import { Buffer } from "node:buffer";

const BOM = "\ufeff";

/** The receipt bytes are not decodable / not the declared shape. */
export class ReceiptUnparseable extends Error {
  constructor(message) {
    super(message);
    this.name = "ReceiptUnparseable";
    this.reason = "receipt-unparseable";
  }
}

/**
 * Decode receipt bytes as UTF-8, tolerating a BOM, refusing anything else.
 *
 * A BOM is tolerated because Windows writers emit one and it is not a content defect. Invalid
 * UTF-8 IS a content defect and must not be silently replaced — a lossy decode turns a corrupt
 * receipt into a plausible-looking one. Node's `Buffer.toString("utf8")` is LOSSY by default
 * (it substitutes U+FFFD and never throws), so validity is checked explicitly with a fatal
 * `TextDecoder`; this is a real behavioural difference from Python's `bytes.decode`, and
 * without the explicit check the JS runtime would ACCEPT receipts the Python one rejects.
 */
export function decode(raw) {
  const buffer = Buffer.from(raw);
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(buffer);
  } catch {
    throw new ReceiptUnparseable("receipt-unparseable: not valid UTF-8 (invalid continuation)");
  }
  if (text.startsWith(BOM)) {
    return text.slice(BOM.length);
  }
  return text;
}

/** Parse `text` as a JSON OBJECT. An array or scalar has no field to validate. */
export function parseJsonObject(text) {
  let payload;
  try {
    payload = JSON.parse(text);
  } catch (cause) {
    throw new ReceiptUnparseable(`receipt-unparseable: invalid JSON (${cause.message})`);
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    throw new ReceiptUnparseable(
      `receipt-unparseable: top level must be an object, got ${describeTopLevel(payload)}`,
    );
  }
  return payload;
}

/**
 * Required keys that are absent, `null`, or blank whitespace — sorted.
 *
 * `0` / `false` / `[]` are PRESENT: a falsy-but-real value is a work product. Only `null` and
 * an all-whitespace string count as missing.
 */
export function missingFields(payload, spec) {
  const missing = spec.requiredFields.filter(
    (field) => !Object.hasOwn(payload, field) || isBlank(payload[field]),
  );
  return Object.freeze(missing.sort());
}

/**
 * Forbidden markers found in `text`, case-insensitively — sorted.
 *
 * These are the "not actually finished" phrases. Their absence is the AND-gate's content
 * clause, without which the gate reduces to "exit 0 and non-empty" on a text receipt.
 */
export function presentMarkers(text, spec) {
  const lowered = text.toLowerCase();
  const found = spec.forbiddenMarkers.filter((marker) => lowered.includes(marker.toLowerCase()));
  return Object.freeze(found.sort());
}

function isBlank(value) {
  if (value === null) {
    return true;
  }
  return typeof value === "string" && value.trim() === "";
}

function describeTopLevel(payload) {
  if (payload === null) {
    return "null";
  }
  if (Array.isArray(payload)) {
    return "array";
  }
  return typeof payload;
}
