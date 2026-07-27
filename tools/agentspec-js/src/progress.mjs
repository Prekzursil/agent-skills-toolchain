/**
 * A progress/status stream is NEVER a result — the JS mirror of `agentspec/progress.py`.
 *
 * MEASURED FAILURES THIS EXISTS FOR:
 *  - an agent's ENTIRE final answer was a receipt reading "started in the background as task-…",
 *    and its real finding then completed on disk and was discarded unread;
 *  - another forwarded a raw `[codex] …` progress stream as its terminal result.
 *
 * `classify` returns a tagged RESULT or PROGRESS record. Only a result can be unwrapped by
 * `asResult`; handing it a progress record throws. A caller cannot accidentally return the
 * progress stream, because the two are different shapes and the unwrap is the only door.
 */

import { foldAsciiCase, isBlank } from "./wire.mjs";

/** Sorted and closed. Each is a receipt phrase observed on a real fire-and-forget return. */
export const BACKGROUND_PHRASES = Object.freeze([
  "check /codex:status",
  "check the job status",
  "launched in the background",
  "running in the background",
  "started in the background",
]);

/** A bracketed-tag progress line, e.g. `[codex] reading files`. */
export const PROGRESS_LINE_RE = /^\s*\[[A-Za-z0-9_.-]+\]\s/u;

/**
 * Every boundary Python's `str.splitlines()` splits on — NOT just CR/LF.
 *
 * A naive `/\r\n|\r|\n/` here is a real parity defect, not a nicety: Python additionally
 * splits on VT, FF, FS, GS, RS, NEL and U+2028/U+2029, so a payload separated by any of those
 * is ONE line to JS and SEVERAL to Python, and `classify` then disagrees across runtimes on
 * whether the body is progress-line-only.
 */
export const LINE_BOUNDARY_RE = /\r\n|[\n\r\v\f\u001c\u001d\u001e\u0085\u2028\u2029]/u;

/** Raised when a progress payload is asked to act as a result. */
export class ProgressStreamRejected extends Error {
  constructor(marker) {
    super(`progress-stream: payload matched ${JSON.stringify(marker)} and is not a result`);
    this.name = "ProgressStreamRejected";
    this.reason = "progress-stream";
    this.marker = marker;
  }
}

/** Split `payload` into the result variant or the progress variant. */
export function classify(payload) {
  const lowered = foldAsciiCase(payload);
  for (const phrase of BACKGROUND_PHRASES) {
    if (lowered.includes(foldAsciiCase(phrase))) {
      return Object.freeze({ kind: "progress", text: payload, marker: phrase });
    }
  }
  const lines = payload.split(LINE_BOUNDARY_RE).filter((line) => !isBlank(line));
  if (lines.length > 0 && lines.every((line) => PROGRESS_LINE_RE.test(line))) {
    return Object.freeze({ kind: "progress", text: payload, marker: "progress-line-only" });
  }
  return Object.freeze({ kind: "result", text: payload, marker: null });
}

/** Unwrap a result record. A progress record throws; anything else is a bug. */
export function asResult(classified) {
  if (classified.kind === "result") {
    return classified.text;
  }
  if (classified.kind === "progress") {
    throw new ProgressStreamRejected(classified.marker);
  }
  throw new TypeError(`expected a classified payload, got kind ${JSON.stringify(classified.kind)}`);
}

/** Boolean shorthand over `classify`, for call sites that only need the flag. */
export function looksLikeProgress(payload) {
  return classify(payload).kind === "progress";
}
