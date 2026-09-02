/**
 * The canonical JSON form, JS side. Rule numbering (R1-R15) is shared with `canonical.py`.
 *
 * The cross-runtime half of this contract is `fixtures/canonical-corpus.json`, driven against
 * both runtimes and byte-compared by `parity/oracle.mjs`. These are the JS unit gates under it,
 * concentrated on the cases where JS is the side that behaves badly by default.
 */

import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import test from "node:test";

import {
  CanonicalJsonError,
  E_CYCLIC,
  E_INT_RANGE,
  E_KEY_TYPE,
  E_MAX_DEPTH,
  E_NONFINITE,
  E_VALUE_TYPE,
  MAX_DEPTH,
  MAX_SAFE_INTEGER,
  MIN_SAFE_INTEGER,
  REJECTION_CODES,
  dumpb,
  dumps,
  encodeString,
  loadb,
  loads,
  numberToString,
} from "../src/canonical.mjs";

function rejects(thunk, code) {
  assert.throws(thunk, (caught) => {
    assert.ok(caught instanceof CanonicalJsonError, `expected CanonicalJsonError, got ${caught}`);
    assert.equal(caught.code, code);
    assert.equal(caught.reason, "schema-invalid");
    return true;
  });
}

test("the rejection codes are sorted, unique and carry the taxonomy reason", () => {
  assert.deepEqual([...REJECTION_CODES], [...REJECTION_CODES].sort());
  assert.equal(new Set(REJECTION_CODES).size, REJECTION_CODES.length);
  const failure = new CanonicalJsonError(E_INT_RANGE, "9007199254740993");
  assert.equal(failure.message, "schema-invalid-int-range: 9007199254740993");
  assert.equal(failure.detail, "9007199254740993");
  assert.equal(CanonicalJsonError.reason, "schema-invalid");
});

// ---------------------------------------------------------------------------------------
// R2 separators / R3 key order / R4 key type
// ---------------------------------------------------------------------------------------

test("R2: no insignificant whitespace", () => {
  assert.equal(dumps({ a: 1n, b: [1n, 2n] }), '{"a":1,"b":[1,2]}');
});

test("R3: keys sort by UTF-16 code unit, defeating V8's integer-key reordering", () => {
  // V8 iterates integer-like keys FIRST in ascending numeric order, so insertion order is not
  // what `Object.keys` returns; the explicit sort is what makes the output deterministic.
  assert.equal(dumps({ 10: 0n, 2: 0n, b: 0n, 1: 0n }), '{"1":0,"10":0,"2":0,"b":0}');
  assert.deepEqual(Object.keys({ 10: 0, 2: 0, b: 0, 1: 0 }), ["1", "2", "10", "b"]);
});

test("R3: an astral key sorts BEFORE U+FFFF, because its lead surrogate is 0xD83D", () => {
  assert.equal(dumps({ "\uffff": 1n, "😀": 2n }), '{"😀":2,"\uffff":1}');
});

test("R4: a symbol key is rejected, never silently dropped", () => {
  // `JSON.stringify` ignores symbol keys entirely. Python has no symbols, so dropping one would
  // make the JS runtime emit a document the Python runtime could never produce.
  rejects(() => dumps({ [Symbol("s")]: 1n, a: 1n }), E_KEY_TYPE);
});

test("R12: an accessor property is rejected rather than invoked", () => {
  // `value[key]` on a getter executes arbitrary code mid-serialisation — the same hijack class
  // as `toJSON`, with no Python counterpart.
  let called = 0;
  const target = {};
  Object.defineProperty(target, "trap", {
    get() {
      called += 1;
      return 1n;
    },
    enumerable: true,
  });
  rejects(() => dumps(target), E_VALUE_TYPE);
  assert.equal(called, 0, "the getter must never run");
});

test("a toJSON property is DATA, never a hook", () => {
  assert.equal(dumps({ toJSON: "not-a-hook", real: 1n }), '{"real":1,"toJSON":"not-a-hook"}');
  // The classic hijack: JSON.stringify would return "HIJACKED" for this object.
  const hijack = { toJSON: () => "HIJACKED", real: 1n };
  assert.equal(JSON.stringify(hijack), '"HIJACKED"');
  rejects(() => dumps(hijack), E_VALUE_TYPE);
});

// ---------------------------------------------------------------------------------------
// R5 / R6 / R7 / R8 / R9 numbers
// ---------------------------------------------------------------------------------------

test("R5: String(x) is Number::toString, so the JS side gets the algorithm for free", () => {
  const rows = [
    [0, "0"],
    [-0, "0"],
    [1, "1"],
    [1.5, "1.5"],
    [1e-7, "1e-7"],
    [1e21, "1e+21"],
    [1e100, "1e+100"],
    [5e-324, "5e-324"],
    [Number.MAX_VALUE, "1.7976931348623157e+308"],
  ];
  for (const [value, expected] of rows) {
    assert.equal(numberToString(value), expected, `Number::toString(${value})`);
  }
});

test("R9: negative zero normalises to 0", () => {
  assert.equal(numberToString(-0), "0");
  assert.equal(dumps(-0), "0");
  assert.ok(Object.is(-0, -0));
});

test("R8: NaN and the infinities are rejected, not silently turned into null", () => {
  assert.equal(JSON.stringify(Number.NaN), "null", "the default behaviour this rule replaces");
  for (const value of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
    rejects(() => numberToString(value), E_NONFINITE);
    rejects(() => dumps({ score: value }), E_NONFINITE);
  }
});

test("R7: the safe-integer bound applies to BigInt, and NEVER to a double", () => {
  assert.equal(dumps(MAX_SAFE_INTEGER), "9007199254740991");
  assert.equal(dumps(MIN_SAFE_INTEGER), "-9007199254740991");
  rejects(() => dumps(MAX_SAFE_INTEGER + 1n), E_INT_RANGE);
  rejects(() => dumps(MIN_SAFE_INTEGER - 1n), E_INT_RANGE);
  rejects(() => dumps(10n ** 30n), E_INT_RANGE);
  // A double claims no precision beyond IEEE-754, so every finite magnitude is accepted.
  assert.equal(dumps(1e16), "10000000000000000");
  assert.equal(dumps(1e21), "1e+21");
  assert.equal(dumps(1e100), "1e+100");
  assert.equal(dumps(Number.MAX_VALUE), "1.7976931348623157e+308");
});

test("R6: the int/float tag is erased, so 1 and 1.0 are one wire value", () => {
  assert.equal(dumps(1n), dumps(1));
  assert.equal(dumps(1n), "1");
});

test("booleans are literals, not numbers", () => {
  assert.equal(dumps([true, false, null]), "[true,false,null]");
});

// ---------------------------------------------------------------------------------------
// R10 / R11 strings
// ---------------------------------------------------------------------------------------

test("R10: escaping is ES2019 well-formed QuoteJSONString with lowercase hex", () => {
  const rows = [
    ["", '""'],
    ["abc", '"abc"'],
    ["\b\t\n\f\r", '"\\b\\t\\n\\f\\r"'],
    ['a"b\\c', '"a\\"b\\\\c"'],
    ["a/b", '"a/b"'],
    ["\u0000", '"\\u0000"'],
    ["\u001f", '"\\u001f"'],
    ["\u007f", '"\u007f"'],
    ["é", '"é"'],
  ];
  for (const [text, expected] of rows) {
    assert.equal(encodeString(text), expected);
  }
});

test("R11: U+2028 and U+2029 are escaped, unlike JSON.stringify's default", () => {
  assert.equal(encodeString("\u2028"), '"\\u2028"');
  assert.equal(encodeString("\u2029"), '"\\u2029"');
  assert.equal(JSON.stringify("\u2028"), '"\u2028"', "the default this rule deviates from");
});

test("R10: unpaired surrogates are escaped; a well-formed pair stays raw", () => {
  assert.equal(encodeString("\ud800"), '"\\ud800"');
  assert.equal(encodeString("\udc00"), '"\\udc00"');
  assert.equal(encodeString("\ud800a"), '"\\ud800a"');
  assert.equal(encodeString("\ud800\ud800"), '"\\ud800\\ud800"');
  assert.equal(encodeString("😀"), '"😀"');
  assert.equal(encodeString("😀\ud800"), '"😀\\ud800"');
});

test("R1: the canonical bytes are always valid UTF-8, even for a lone surrogate", () => {
  assert.deepEqual(dumpb("\ud800"), Buffer.from('"\\ud800"', "utf8"));
  assert.deepEqual(dumpb("😀"), Buffer.from([0x22, 0xf0, 0x9f, 0x98, 0x80, 0x22]));
  assert.deepEqual(dumpb("\ufeff"), Buffer.from([0x22, 0xef, 0xbb, 0xbf, 0x22]));
});

// ---------------------------------------------------------------------------------------
// R12 types / R13 depth / cycles
// ---------------------------------------------------------------------------------------

test("R12: the types JSON.stringify silently mangles are all rejected", () => {
  const hazards = [
    new Date(0),
    new Map([["a", 1]]),
    new Set([1]),
    // eslint-disable-next-line no-new-wrappers
    new Number(1),
    () => 1,
    undefined,
    Symbol("s"),
    new Error("boom"),
  ];
  for (const value of hazards) {
    rejects(() => dumps(value), E_VALUE_TYPE);
  }
  // What the default would have done instead of refusing:
  assert.equal(JSON.stringify(new Map([["a", 1]])), "{}");
  assert.equal(JSON.stringify({ gone: undefined }), "{}");
});

test("R12: an object with an exotic prototype chain is rejected and described", () => {
  const exotic = Object.create(Object.create(null));
  assert.equal(exotic.constructor, undefined);
  rejects(() => dumps(exotic), E_VALUE_TYPE);
});

test("R12: a null-prototype object IS a plain mapping", () => {
  const bare = Object.create(null);
  bare.a = 1n;
  assert.equal(dumps(bare), '{"a":1}');
});

test("R12: an array HOLE is rejected, not rendered as null", () => {
  const holed = [1n, , 3n];
  assert.equal(JSON.stringify([1, , 3]), "[1,null,3]", "the default this rule refuses");
  rejects(() => dumps(holed), E_VALUE_TYPE);
});

test("R12: an explicit undefined element is rejected too", () => {
  rejects(() => dumps([1n, undefined]), E_VALUE_TYPE);
});

test("empty containers round-trip", () => {
  assert.equal(dumps([]), "[]");
  assert.equal(dumps({}), "{}");
  assert.equal(dumps({ a: [], b: {} }), '{"a":[],"b":{}}');
});

test("R13: depth at the cap is accepted and beyond it is rejected", () => {
  const nest = (depth, wrap) => {
    let value = 1n;
    for (let level = 0; level < depth; level += 1) {
      value = wrap(value);
    }
    return value;
  };
  assert.equal(dumps(nest(MAX_DEPTH, (inner) => [inner])).split("[").length - 1, MAX_DEPTH);
  rejects(() => dumps(nest(MAX_DEPTH + 1, (inner) => [inner])), E_MAX_DEPTH);
  rejects(() => dumps(nest(MAX_DEPTH + 1, (inner) => ({ n: inner }))), E_MAX_DEPTH);
});

test("a reference cycle is rejected in both container kinds", () => {
  const cyclicArray = [];
  cyclicArray.push(cyclicArray);
  rejects(() => dumps(cyclicArray), E_CYCLIC);
  const cyclicObject = {};
  cyclicObject.self = cyclicObject;
  rejects(() => dumps(cyclicObject), E_CYCLIC);
});

test("a shared but acyclic subobject is NOT a cycle", () => {
  const shared = { x: 1n };
  assert.equal(dumps([shared, shared]), '[{"x":1},{"x":1}]');
  assert.equal(dumps({ a: shared, b: shared }), '{"a":{"x":1},"b":{"x":1}}');
});

// ---------------------------------------------------------------------------------------
// R14 / R15 decoder
// ---------------------------------------------------------------------------------------

test("R14: bare non-finite literals are rejected on decode", () => {
  // Free on this side — JSON.parse already refuses them. Python needs `parse_constant=`.
  for (const literal of ["NaN", "Infinity", "-Infinity"]) {
    assert.throws(() => loads(literal), SyntaxError);
  }
});

test("R15: every numeric literal decodes to a double, so the round trip is a fixed point", () => {
  assert.equal(typeof loads("10000000000000000"), "number");
  for (const value of [null, true, 1n, 1.5, "text", [], {}, { a: [1n, { b: null }] }, 1e16, 1e21]) {
    const once = dumps(value);
    assert.equal(dumps(loads(once)), once, `not a fixed point: ${once}`);
  }
});

test("loadb decodes canonical bytes", () => {
  assert.deepEqual(loadb(Buffer.from('{"a":[1,2]}', "utf8")), { a: [1, 2] });
});

test("__proto__ round-trips as ordinary data, not as a prototype mutation", () => {
  const decoded = loads('{"__proto__":1}');
  assert.ok(Object.hasOwn(decoded, "__proto__"));
  assert.equal(dumps(decoded), '{"__proto__":1}');
});
