/** Receipt decode / parse / content checks, including the lossy-decode trap Node ships with. */

import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import test from "node:test";

import { capture } from "./helpers.mjs";

import { ReceiptUnparseable, decode, missingFields, parseJsonObject, presentMarkers } from "../src/receipt.mjs";
import { receiptSpec } from "../src/spec.mjs";

test("valid UTF-8 decodes, and a leading BOM is tolerated as a Windows artefact", () => {
  assert.equal(decode(Buffer.from("hello", "utf8")), "hello");
  assert.equal(decode(Buffer.from("\ufeffhello", "utf8")), "hello");
  // A BOM in the MIDDLE is data and must survive.
  assert.equal(decode(Buffer.from("a\ufeffb", "utf8")), "a\ufeffb");
});

test("invalid UTF-8 is REFUSED, not silently replaced", () => {
  // Node's Buffer.toString("utf8") is LOSSY: it substitutes U+FFFD and never throws, so without
  // the explicit fatal TextDecoder this runtime would ACCEPT receipts Python rejects. A lossy
  // decode turns a corrupt receipt into a plausible-looking one.
  const invalid = Buffer.from([0x61, 0xff, 0xfe, 0x62]);
  assert.equal(invalid.toString("utf8"), "a\ufffd\ufffdb", "the lossy default this guard replaces");
  const caught = capture(() => decode(invalid));
  assert.ok(caught instanceof ReceiptUnparseable, `expected ReceiptUnparseable, got ${caught}`);
  assert.equal(caught.reason, "receipt-unparseable");
});

test("a truncated multi-byte sequence is refused", () => {
  assert.throws(() => decode(Buffer.from([0xe6, 0x97])), ReceiptUnparseable);
});

test("a JSON object parses; an array or scalar does not", () => {
  assert.deepEqual(parseJsonObject('{"a":1}'), { a: 1 });
  for (const [text, described] of [
    ["[1,2]", "array"],
    ["null", "null"],
    ['"text"', "string"],
    ["42", "number"],
    ["true", "boolean"],
  ]) {
    const caught = capture(() => parseJsonObject(text));
  assert.ok(caught instanceof ReceiptUnparseable, `expected ReceiptUnparseable, got ${caught}`);
    assert.match(caught.message, new RegExp(`top level must be an object, got ${described}`, "u"));
  }
});

test("malformed JSON is refused with the parse reason", () => {
  const caught = capture(() => parseJsonObject("{not json"));
  assert.ok(caught instanceof ReceiptUnparseable, `expected ReceiptUnparseable, got ${caught}`);
  assert.match(caught.message, /invalid JSON/u);
});

test("missingFields treats falsy-but-real values as PRESENT", () => {
  const spec = receiptSpec({ fmt: "json", requiredFields: ["zero", "no", "empty", "blank", "nil", "gone"] });
  const payload = { zero: 0, no: false, empty: [], blank: "   ", nil: null };
  // 0 / false / [] are work products. Only null and all-whitespace count as missing.
  assert.deepEqual([...missingFields(payload, spec)], ["blank", "gone", "nil"]);
});

test("missingFields returns nothing when every required field is real", () => {
  const spec = receiptSpec({ fmt: "json", requiredFields: ["result"] });
  assert.deepEqual([...missingFields({ result: "done" }, spec)], []);
});

test("an inherited property does NOT satisfy a required field", () => {
  const spec = receiptSpec({ fmt: "json", requiredFields: ["toString"] });
  assert.deepEqual([...missingFields({}, spec)], ["toString"]);
});

test("presentMarkers matches case-insensitively and sorts", () => {
  const spec = receiptSpec({ fmt: "text", forbiddenMarkers: ["TODO", "in progress", "absent"] });
  assert.deepEqual([...presentMarkers("Work is In Progress; todo later", spec)], [
    "TODO",
    "in progress",
  ]);
  assert.deepEqual([...presentMarkers("all done", spec)], []);
});
