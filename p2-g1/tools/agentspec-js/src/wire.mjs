/**
 * SHARED WIRE RULES — the JS mirror of `agentspec/wire.py`.
 *
 * `canonical.mjs` made the two runtimes agree on the BYTES of a receipt. This module exists
 * because that was only half the contract: a differential harness driving both runtimes over
 * 483 behavioural cases found **78 outcome divergences**, including `oracle.judge` — the
 * AND-gate this whole package is built around — returning `ok=true` here and `severed-stream`
 * in Python for the SAME receipt bytes. Every one came from a MIRRORED PREDICATE: two builtins
 * that look like translations of each other and are not.
 *
 *  - `String.prototype.trim()` vs `str.strip()` strip DIFFERENT sets. Measured by exhaustive
 *    sweep over all 1,114,112 code points: `U+001C U+001D U+001E U+001F U+0085` are blank to
 *    Python only, and `U+FEFF` is blank to JS only. So `BLANK_CHARS` pins the set as DATA.
 *  - `.sort()` orders by UTF-16 code unit and `sorted()` by code point. `sortedWire` is the one
 *    comparator (and it is `.sort()`'s rule, which `canonical` R3 already adopted).
 *  - `.length` counts UTF-16 code units and `len()` counts code points, so `WINDOWS_CMDLINE_CAP`
 *    was the same NUMBER in different UNITS. `utf16Len` is the one unit — the one Windows
 *    `CreateProcess` actually counts.
 *  - `\p{C}` and `str.isprintable()` read DIFFERENT Unicode tables (Node 24 ships 17.0, CPython
 *    3.14 ships 16.0.0, CI Node 22 a third), which disagreed on 4,803 code points.
 *    `NON_PRINTABLE_ID_RANGES` pins that set as explicit numbers, and `foldAsciiCase` pins the
 *    case fold the same way.
 *
 * The Python module is the SINGLE SOURCE OF TRUTH: `test/crosslang.test.mjs` reads BOTH tables
 * out of `wire.py`'s source text and fails if this file has drifted.
 *
 * Zero dependencies.
 */

/** The CLOSED blank set: exactly CPython's `str.isspace()` set, frozen as DATA. */
export const BLANK_CHARS = Object.freeze([
  "\u0009",
  "\u000a",
  "\u000b",
  "\u000c",
  "\u000d",
  "\u001c",
  "\u001d",
  "\u001e",
  "\u001f",
  "\u0020",
  "\u0085",
  "\u00a0",
  "\u1680",
  "\u2000",
  "\u2001",
  "\u2002",
  "\u2003",
  "\u2004",
  "\u2005",
  "\u2006",
  "\u2007",
  "\u2008",
  "\u2009",
  "\u200a",
  "\u2028",
  "\u2029",
  "\u202f",
  "\u205f",
  "\u3000",
]);

/**
 * Inclusive `start-end` hex ranges a terminal-marker id may not contain.
 *
 * Cc / Cf / Cs / Co / Zs / Zl / Zp plus the permanently-reserved noncharacters, as of Unicode
 * 16.0.0. The UNASSIGNED (Cn) clause of Python's `isprintable()` is deliberately DROPPED — Cn
 * is the part that MOVES between Unicode versions, and a newly assigned letter is not the
 * hazard. The hazard is a byte the console re-interprets, or whitespace that makes
 * `FAILED:<id> <reason>` unparseable.
 */
export const NON_PRINTABLE_ID_RANGES = Object.freeze([
  "0000-0020", "007f-00a0", "00ad-00ad", "0600-0605", "061c-061c", "06dd-06dd", "070f-070f",
  "0890-0891", "08e2-08e2", "1680-1680", "180e-180e", "2000-200f", "2028-202f", "205f-2064",
  "2066-206f", "3000-3000", "d800-f8ff", "fdd0-fdef", "feff-feff", "fff9-fffb", "fffe-ffff",
  "110bd-110bd", "110cd-110cd", "13430-1343f", "1bca0-1bca3", "1d173-1d17a", "1fffe-1ffff",
  "2fffe-2ffff", "3fffe-3ffff", "4fffe-4ffff", "5fffe-5ffff", "6fffe-6ffff", "7fffe-7ffff",
  "8fffe-8ffff", "9fffe-9ffff", "afffe-affff", "bfffe-bffff", "cfffe-cffff", "dfffe-dffff",
  "e0001-e0001", "e0020-e007f", "efffe-10ffff",
]);

/** The largest integer BOTH runtimes represent exactly. */
export const MAX_WIRE_INTEGER = 9007199254740991;

export const MIN_WIRE_INTEGER = -9007199254740991;

const BLANK_SET = new Set(BLANK_CHARS);

const NON_PRINTABLE_ID = NON_PRINTABLE_ID_RANGES.map((item) =>
  item.split("-").map((part) => Number.parseInt(part, 16)),
);

/** True when `text` holds no non-blank character. The empty string IS blank. */
export function isBlank(text) {
  for (const char of text) {
    if (!BLANK_SET.has(char)) {
      return false;
    }
  }
  return true;
}

/** True when `text` holds at least one blank character. */
export function containsBlank(text) {
  for (const char of text) {
    if (BLANK_SET.has(char)) {
      return true;
    }
  }
  return false;
}

/** The length of `text` in UTF-16 CODE UNITS — the unit Windows counts, and Python must adopt. */
export function utf16Len(text) {
  return text.length;
}

/** Sort the way `.sort()` does. Python reaches the same order through `utf16_sort_key`. */
export function sortedWire(items) {
  return Object.freeze([...items].sort());
}

/** Lowercase ASCII A-Z and NOTHING else — a case fold pinned to a spec, not to ICU. */
export function foldAsciiCase(text) {
  return text.replaceAll(/[A-Z]/gu, (char) => String.fromCharCode(char.charCodeAt(0) + 32));
}

/** True when every code point of a NON-EMPTY `text` is outside the pinned reject set. */
export function isPrintableId(text) {
  if (text === "") {
    return false;
  }
  for (const char of text) {
    if (isNonPrintable(char.codePointAt(0))) {
      return false;
    }
  }
  return true;
}

/**
 * True for a number both runtimes represent exactly as an integer.
 *
 * `Number.isSafeInteger` already rejects `true`, a `BigInt`, `NaN` and any non-number, which is
 * what Python must reproduce by excluding `bool` and bounding `int` explicitly.
 */
export function isWireInteger(value) {
  return Number.isSafeInteger(value);
}

/**
 * Return `value` as a wire integer, or throw `TypeError`.
 *
 * The message carries NO rendering of the offending value on purpose: Python prints `2.0` and
 * JS prints `2` for the same double, which would make the two runtimes' error text differ on
 * the very check that exists to keep them identical.
 */
export function requireWireInteger(value, name) {
  if (!isWireInteger(value)) {
    throw new TypeError(
      `${name} must be an integer in [${MIN_WIRE_INTEGER}, ${MAX_WIRE_INTEGER}]`,
    );
  }
  return value;
}

/**
 * The JSON type of a DECODED value, in the one vocabulary both runtimes report.
 *
 * `typeof` gives `object` for null and for an array, and Python's `type(x).__name__` gives
 * `NoneType`/`list`/`str` — neither is portable, and this string reaches `error.root_cause`.
 */
export function jsonTypeName(value) {
  if (value === null) {
    return "null";
  }
  if (Array.isArray(value)) {
    return "array";
  }
  const kind = typeof value;
  if (kind === "boolean") {
    return "boolean";
  }
  if (kind === "number") {
    return "number";
  }
  if (kind === "string") {
    return "string";
  }
  return "object";
}

function isNonPrintable(code) {
  for (const [start, end] of NON_PRINTABLE_ID) {
    if (code >= start && code <= end) {
      return true;
    }
  }
  return false;
}
