/** A progress stream is never a result — including across Python's full set of line boundaries. */

import assert from "node:assert/strict";
import test from "node:test";

import { capture } from "./helpers.mjs";

import {
  BACKGROUND_PHRASES,
  LINE_BOUNDARY_RE,
  PROGRESS_LINE_RE,
  ProgressStreamRejected,
  asResult,
  classify,
  looksLikeProgress,
} from "../src/progress.mjs";

test("the background phrases are sorted and closed", () => {
  assert.deepEqual([...BACKGROUND_PHRASES], [...BACKGROUND_PHRASES].sort());
  assert.equal(BACKGROUND_PHRASES.length, 5);
});

test("every background phrase is detected, case-insensitively", () => {
  for (const phrase of BACKGROUND_PHRASES) {
    const classified = classify(`Task ${phrase.toUpperCase()} as task-42`);
    assert.equal(classified.kind, "progress");
    assert.equal(classified.marker, phrase);
    assert.ok(looksLikeProgress(`x ${phrase} y`));
  }
});

test("a body that is ONLY bracketed progress lines is progress", () => {
  const stream = "[codex] reading files\n[codex] thinking\n\n[codex] done";
  const classified = classify(stream);
  assert.equal(classified.kind, "progress");
  assert.equal(classified.marker, "progress-line-only");
});

test("a real answer among progress lines is a RESULT", () => {
  const mixed = "[codex] reading files\nThe answer is 42.";
  assert.equal(classify(mixed).kind, "result");
  assert.equal(asResult(classify(mixed)), mixed);
});

test("an empty or whitespace-only body is a result, not progress", () => {
  // No lines means nothing matched; `every` on an empty list is vacuously true, so the explicit
  // length check is what stops a blank body being classified as a progress stream.
  assert.equal(classify("").kind, "result");
  assert.equal(classify("   \n  ").kind, "result");
});

test("a progress payload can NEVER be unwrapped as a result", () => {
  const classified = classify("started in the background as task-9");
  const caught = capture(() => asResult(classified));
  assert.ok(caught instanceof ProgressStreamRejected, `expected ProgressStreamRejected, got ${caught}`);
  assert.equal(caught.reason, "progress-stream");
  assert.equal(caught.marker, "started in the background");
});

test("an unrecognised classification shape is a TypeError, not a silent pass", () => {
  assert.throws(() => asResult({ kind: "invented", text: "x" }), TypeError);
});

test("line splitting matches Python's str.splitlines(), not just CR/LF", () => {
  // A naive CR/LF-only split is a real parity defect: Python also splits on VT, FF, FS, GS, RS,
  // NEL and U+2028/U+2029, so the two runtimes would disagree on whether a body is
  // progress-line-only.
  for (const separator of ["\n", "\r", "\r\n", "\v", "\f", "\u001c", "\u001d", "\u001e", "\u0085", "\u2028", "\u2029"]) {
    const stream = `[a] one${separator}[b] two`;
    assert.equal(
      classify(stream).kind,
      "progress",
      `separator U+${separator.codePointAt(0).toString(16)} did not split`,
    );
  }
});

test("the boundary regex is exported and matches every declared separator", () => {
  assert.ok(LINE_BOUNDARY_RE.test("a\u2028b"));
  assert.ok(LINE_BOUNDARY_RE.test("a\u0085b"));
  assert.ok(!LINE_BOUNDARY_RE.test("plain text"));
});

test("the progress-line pattern requires a bracketed tag followed by whitespace", () => {
  assert.ok(PROGRESS_LINE_RE.test("[codex] x"));
  assert.ok(PROGRESS_LINE_RE.test("  [a.b-c_1] x"));
  assert.ok(!PROGRESS_LINE_RE.test("[codex]x"));
  assert.ok(!PROGRESS_LINE_RE.test("no tag here"));
});
