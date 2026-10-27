/**
 * CANONICAL JSON — the JS half of the ONE serialisation both runtimes reproduce byte-for-byte.
 *
 * The Python half is `agentspec/canonical.py`; the rule numbering (R1-R15) is shared and its
 * module docstring carries the measured evidence for each rule. The short version: stock
 * `json.dumps` and stock `JSON.stringify` disagree on 47 of 75 probe cases, and on 15 of 15
 * container cases carrying an object key or two array elements — i.e. every realistic receipt.
 * Tuning the two stdlib encoders towards each other still leaves 32 divergences, so BOTH sides
 * run a custom encoder and neither ever calls `JSON.stringify` for structure.
 *
 * JS-side notes where the two languages differ in KIND, not just in output:
 *
 *  - A JS string is a sequence of UTF-16 CODE UNITS, so a well-formed surrogate pair is emitted
 *    raw (it already IS the astral character). Python iterates CODE POINTS, so its encoder folds
 *    an adjacent well-formed pair into the astral code point to reach the same bytes.
 *  - `Number` is always a double, so R7's safe-integer bound applies ONLY to `BigInt` — the
 *    integer-typed value. Applying `Number.isSafeInteger` to a `number` wrongly rejects 1e16,
 *    1e21, 1e100 and `Number.MAX_VALUE` (a measured false-rejection in an earlier draft).
 *  - `String(x)` already IS the ECMAScript `Number::toString` of R5, so R5 is free here and is
 *    the thing Python has to implement.
 *  - An ACCESSOR property is rejected rather than read: `value[key]` on a getter runs arbitrary
 *    code, which is the same hijack class as `toJSON` and has no Python counterpart.
 *
 * Zero dependencies: `node:buffer` only, for the UTF-8 encode.
 */

import { Buffer } from "node:buffer";


/** R7. Beyond this an integer-typed value cannot survive a JS `Number` round trip. */
export const MAX_SAFE_INTEGER = 9007199254740991n;

export const MIN_SAFE_INTEGER = -9007199254740991n;

/** R13. The shared nesting cap, so the boundary is identical on both runtimes. */
export const MAX_DEPTH = 100;

export const E_NONFINITE = "schema-invalid-nonfinite";
export const E_INT_RANGE = "schema-invalid-int-range";
export const E_KEY_TYPE = "schema-invalid-nonstring-key";
export const E_VALUE_TYPE = "schema-invalid-unsupported-type";
export const E_CYCLIC = "schema-invalid-cyclic";
export const E_MAX_DEPTH = "schema-invalid-max-depth";
export const E_KEY_COLLISION = "schema-invalid-key-collision";
export const E_INVALID_UTF8 = "schema-invalid-utf8";

/** Sorted and CLOSED. `test/crosslang.test.mjs` asserts equality with the Python tuple. */
export const REJECTION_CODES = Object.freeze([
  E_CYCLIC,
  E_INT_RANGE,
  E_KEY_COLLISION,
  E_MAX_DEPTH,
  E_NONFINITE,
  E_KEY_TYPE,
  E_VALUE_TYPE,
  E_INVALID_UTF8,
]);

const SHORT_ESCAPES = new Map([
  [0x08, "\\b"],
  [0x09, "\\t"],
  [0x0a, "\\n"],
  [0x0c, "\\f"],
  [0x0d, "\\r"],
  [0x22, '\\"'],
  [0x5c, "\\\\"],
]);

const HIGH_SURROGATE_FIRST = 0xd800;
const HIGH_SURROGATE_LAST = 0xdbff;
const LOW_SURROGATE_FIRST = 0xdc00;
const LOW_SURROGATE_LAST = 0xdfff;

const LINE_SEPARATOR = 0x2028;
const PARAGRAPH_SEPARATOR = 0x2029;

/** A value canonical JSON refuses to represent, carrying its `schema-invalid` sub-code. */
export class CanonicalJsonError extends Error {
  static reason = "schema-invalid";

  constructor(code, detail) {
    super(`${code}: ${detail}`);
    this.name = "CanonicalJsonError";
    this.reason = "schema-invalid";
    this.code = code;
    this.detail = detail;
  }
}

/** R10/R11. ES2019 well-formed `QuoteJSONString`, with U+2028/U+2029 also escaped. */
export function encodeString(text) {
  let out = '"';
  let index = 0;
  while (index < text.length) {
    const code = text.charCodeAt(index);
    const short = SHORT_ESCAPES.get(code);
    if (short !== undefined) {
      out += short;
    } else if (code < 0x20 || code === LINE_SEPARATOR || code === PARAGRAPH_SEPARATOR) {
      out += hex4(code);
    } else if (code >= HIGH_SURROGATE_FIRST && code <= HIGH_SURROGATE_LAST) {
      if (lowSurrogateAt(text, index + 1) === null) {
        out += hex4(code);
      } else {
        // Already the astral character in UTF-16; emit both units raw.
        out += text[index] + text[index + 1];
        index += 2;
        continue;
      }
    } else if (code >= LOW_SURROGATE_FIRST && code <= LOW_SURROGATE_LAST) {
      out += hex4(code);
    } else {
      out += text[index];
    }
    index += 1;
  }
  return `${out}"`;
}

/** R5/R8/R9. `String(x)` IS `Number::toString`; only the rejections need writing. */
export function numberToString(value) {
  if (!Number.isFinite(value)) {
    throw new CanonicalJsonError(E_NONFINITE, String(value));
  }
  if (value === 0) {
    return "0"; // R9: `-0 === 0`, so this also normalises negative zero.
  }
  return String(value);
}

/** The canonical TEXT for `value`. */
export function dumps(value) {
  const out = [];
  encode(value, out, 0, new Set());
  return out.join("");
}

/** R1. The canonical BYTES: always valid UTF-8, because R10 escapes lone surrogates first. */
export function dumpb(value) {
  return Buffer.from(dumps(value), "utf8");
}

/**
 * R14/R15. Decode canonical JSON so `dumps(loads(dumps(x))) === dumps(x)` holds.
 *
 * Both rules are FREE on this side and are asserted rather than implemented: `JSON.parse`
 * already rejects bare `NaN`/`Infinity` (R14) and already yields a double for every numeric
 * literal (R15). Python needs real code for both.
 */
export function loads(text) {
  return JSON.parse(text);
}

/**
 * Decode canonical BYTES, REFUSING a lossy decode.
 *
 * `Buffer.toString("utf8")` is LOSSY: it substitutes U+FFFD and NEVER throws, while
 * Python's `bytes.decode("utf-8")` raises. MEASURED before the fix:
 * `loadb(Buffer.from([0x7b,0x22,0x61,0x22,0x3a,0x22,0xff,0x22,0x7d]))` returned
 * `{"a":"\ufffd"}` here and raised there, so `dumpb(loadb(corrupt))` manufactured a
 * well-formed, plausible-looking canonical receipt out of corrupt bytes — the exact
 * silent-coercion class `receipt.decode` already had a fatal `TextDecoder` for, applied
 * to everything EXCEPT the function this module is named for.
 *
 * `ignoreBOM: true` means "do not strip a leading BOM", matching Python: a BOM is DATA
 * here, and stripping one is `receipt.decode`'s separate, single, leading concern.
 */
export function loadb(raw) {
  let text;
  try {
    text = STRICT_UTF8.decode(Buffer.from(raw));
  } catch {
    throw new CanonicalJsonError(E_INVALID_UTF8, "not valid UTF-8");
  }
  return loads(text);
}

const STRICT_UTF8 = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });

function hex4(code) {
  return `\\u${code.toString(16).padStart(4, "0")}`;
}

function lowSurrogateAt(text, index) {
  if (index >= text.length) {
    return null;
  }
  const code = text.charCodeAt(index);
  if (code >= LOW_SURROGATE_FIRST && code <= LOW_SURROGATE_LAST) {
    return code;
  }
  return null;
}

/** R12. The closed dispatch over accepted types; anything else is rejected. */
function encode(value, out, depth, seen) {
  if (value === null) {
    out.push("null");
    return;
  }
  const kind = typeof value;
  if (kind === "boolean") {
    out.push(value ? "true" : "false");
    return;
  }
  if (kind === "string") {
    out.push(encodeString(value));
    return;
  }
  if (kind === "number") {
    out.push(numberToString(value));
    return;
  }
  if (kind === "bigint") {
    out.push(encodeBigInt(value));
    return;
  }
  if (Array.isArray(value)) {
    encodeContainer(value, out, depth, seen, encodeSequence);
    return;
  }
  if (kind === "object" && isPlainObject(value)) {
    encodeContainer(value, out, depth, seen, encodeMapping);
    return;
  }
  throw new CanonicalJsonError(E_VALUE_TYPE, describe(value, kind));
}

/** R7. The safe-integer bound is a property of the INTEGER TYPE, never of a double. */
function encodeBigInt(value) {
  if (value > MAX_SAFE_INTEGER || value < MIN_SAFE_INTEGER) {
    throw new CanonicalJsonError(E_INT_RANGE, String(value));
  }
  return String(value);
}

/**
 * R12. Only a plain or null-prototype object is a mapping.
 *
 * This one predicate is what rejects `Date`, `Map`, `Set`, boxed primitives and class
 * instances — every type `JSON.stringify` silently mangles into `{}` or an ISO string.
 */
function isPlainObject(value) {
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

/** R13 + the cycle guard, shared by both container kinds so neither can drift. */
function encodeContainer(value, out, depth, seen, body) {
  if (seen.has(value)) {
    throw new CanonicalJsonError(E_CYCLIC, Array.isArray(value) ? "Array" : "Object");
  }
  if (depth >= MAX_DEPTH) {
    throw new CanonicalJsonError(E_MAX_DEPTH, `nesting exceeds ${MAX_DEPTH}`);
  }
  seen.add(value);
  body(value, out, depth + 1, seen);
  seen.delete(value);
}

/** R3/R4. Keys checked before ANY output, so a rejection never emits a partial object. */
function encodeMapping(value, out, depth, seen) {
  if (Object.getOwnPropertySymbols(value).length > 0) {
    throw new CanonicalJsonError(E_KEY_TYPE, "symbol");
  }
  // Default `.sort()` compares by UTF-16 code unit — exactly R3, and exactly what the Python
  // side reproduces via `utf16_sort_key`. Python's own `sorted()` would order by code point.
  // `getOwnPropertyNames`, not `keys`: a Python dict has no enumerable/non-enumerable
  // distinction, so a non-enumerable own data property was silently DROPPED here and
  // emitted there. (`__proto__` assigned on a producer object is NOT recoverable from
  // inside an encoder — no own property is ever created — and is disclosed instead.)
  const keys = Object.getOwnPropertyNames(value).sort();
  out.push("{");
  for (let position = 0; position < keys.length; position += 1) {
    if (position > 0) {
      out.push(",");
    }
    out.push(encodeString(keys[position]));
    out.push(":");
    encode(readDataProperty(value, keys[position]), out, depth, seen);
  }
  out.push("}");
}

/**
 * R12. Read the property as DATA, refusing an accessor.
 *
 * `value[key]` on a getter executes arbitrary code during serialisation — the same hijack class
 * as `toJSON`, and a Python dict has no counterpart. Refusing is the only symmetric answer.
 */
function readDataProperty(value, key) {
  const descriptor = Object.getOwnPropertyDescriptor(value, key);
  if (!("value" in descriptor)) {
    throw new CanonicalJsonError(E_VALUE_TYPE, `accessor property ${JSON.stringify(key)}`);
  }
  return descriptor.value;
}

function encodeSequence(value, out, depth, seen) {
  out.push("[");
  for (let position = 0; position < value.length; position += 1) {
    if (position > 0) {
      out.push(",");
    }
    if (!(position in value)) {
      // A hole. `JSON.stringify` renders it `null`; Python cannot express it at all.
      throw new CanonicalJsonError(E_VALUE_TYPE, `array hole at ${position}`);
    }
    encode(value[position], out, depth, seen);
  }
  out.push("]");
}

function describe(value, kind) {
  if (kind === "object") {
    return value.constructor === undefined ? "Object" : value.constructor.name;
  }
  return kind;
}
