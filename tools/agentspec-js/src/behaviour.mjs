/**
 * THE SHARED BEHAVIOURAL CORPUS driver — the second half of the parity contract.
 *
 * `corpus.mjs` proves the two runtimes SERIALISE identically. It cannot prove they BEHAVE
 * identically, and structurally never could: `parity/emit_py.py` calls `dumpb` and nothing else,
 * so `judge`, `missingFields`, `buildArgv`, `checkDispatch`, `planRetry` and every other decision
 * function was outside the oracle entirely. MEASURED CONSEQUENCE: 493 Python tests and 256 JS
 * tests, both at 100% line+branch, both green, while an independent 483-case differential harness
 * found **78 outcome divergences** — including `judge` returning `ok=true` on one runtime and
 * `severed-stream` on the other for the SAME receipt bytes. Coverage was never going to catch
 * that; only executing BOTH runtimes on ONE input and comparing bytes catches it.
 *
 * This module is that comparison's JS half. `parity/emit_behaviour_py.py` is the Python half, and
 * the corpus at `fixtures/behaviour-corpus.json` is the language-neutral contract both read.
 *
 * WHY A TAGGED ARGUMENT DSL: a bare JSON number cannot say whether it means an integer or a
 * double, and the two are a REFUSABILITY difference here — `check_dispatch(timeout_s=2.0)` was a
 * `TypeError` on Python and accepted on JS. Every argument therefore pins its TYPE.
 *
 *   {"s": "text"}   string        {"i": "42"}    integer     {"f": "1.5"}  double
 *   {"b": true}     boolean       {"n": true}    null        {"hex": "7b"} bytes
 *   {"ss": [...]}   string list   {"kv": [[k, tagged], ...]} object, in the given order
 *
 * WHY ONE ERROR VOCABULARY: Python signals a bad value with `ValueError` and JS with
 * `RangeError`; neither name is portable. An outcome is therefore rendered as `{"ok": value}` or
 * `{"err": kind}`, where `kind` is the taxonomy code / reason the exception already carries, or
 * `invalid-type` / `invalid-value` for the two structural classes. An exception carrying NEITHER
 * is re-thrown, never recorded — a crash must not be able to masquerade as conformance.
 */

import { Buffer } from "node:buffer";

import { buildArgv, promptOnArgv, renderCmdline } from "./argv.mjs";
import { costPerSuccess, debit, ledger, spentMicro } from "./budget.mjs";
import { dumps, loadb } from "./canonical.mjs";
import { checkDispatch } from "./dispatchpolicy.mjs";
import { errorDetail, observation, validateObservation } from "./envelope.mjs";
import { judge, railResult } from "./oracle.mjs";
import { classify } from "./progress.mjs";
import { decode, missingFields, parseJsonObject, presentMarkers } from "./receipt.mjs";
import { planRetry, rateLimitBackoffMs } from "./retry.mjs";
import { receiptSpec } from "./spec.mjs";
import { successLine } from "./terminal.mjs";
import { foldAsciiCase, isBlank, isPrintableId, sortedWire, utf16Len } from "./wire.mjs";

/** A corpus file or case is malformed. Distinct from a case producing an `err` outcome. */
export class BehaviourCorpusError extends Error {
  constructor(message) {
    super(message);
    this.name = "BehaviourCorpusError";
  }
}

/** Materialise one tagged argument node. */
export function decodeArg(node) {
  if (node === null || typeof node !== "object" || Array.isArray(node)) {
    throw new BehaviourCorpusError(`arg must be a tagged object, got ${JSON.stringify(node)}`);
  }
  const tags = Object.keys(node);
  if (tags.length !== 1) {
    throw new BehaviourCorpusError(`arg needs exactly one tag, got ${JSON.stringify(tags)}`);
  }
  const [tag] = tags;
  const body = node[tag];
  if (tag === "s") {
    return body;
  }
  if (tag === "i") {
    return Number.parseInt(body, 10);
  }
  if (tag === "f") {
    return Number(body);
  }
  if (tag === "b") {
    return body;
  }
  if (tag === "n") {
    return null;
  }
  if (tag === "hex") {
    return Buffer.from(body, "hex");
  }
  if (tag === "ss") {
    return [...body];
  }
  if (tag === "kv") {
    return Object.fromEntries(body.map((pair) => [pair[0], decodeArg(pair[1])]));
  }
  throw new BehaviourCorpusError(`unknown arg tag ${JSON.stringify(tag)}`);
}

/** The portable name for a thrown failure. Anything unrecognised is RE-THROWN, never recorded. */
export function errorKind(cause) {
  if (typeof cause.code === "string") {
    return cause.code;
  }
  if (typeof cause.reason === "string") {
    return cause.reason;
  }
  if (cause instanceof TypeError) {
    return "invalid-type";
  }
  if (cause instanceof RangeError) {
    return "invalid-value";
  }
  throw cause;
}

const OPS = Object.freeze({
  judge: (a) => {
    const verdict = judge(
      a.unit,
      railResult({ exitCode: a.exit, receiptBytes: a.receipt, wallMs: a.wall }),
      receiptSpec({ fmt: a.fmt, requiredFields: a.required, forbiddenMarkers: a.forbidden }),
    );
    return {
      ok: verdict.ok,
      reason: verdict.reason,
      severed: verdict.severed,
      passed: [...verdict.passedClauses],
      detail: verdict.detail,
    };
  },
  missing_fields: (a) => [
    ...missingFields(a.payload, receiptSpec({ fmt: "json", requiredFields: a.required })),
  ],
  present_markers: (a) => [
    ...presentMarkers(a.text, receiptSpec({ fmt: "text", forbiddenMarkers: a.forbidden })),
  ],
  decode: (a) => decode(a.receipt),
  parse_json_object: (a) => [...sortedWire(Object.keys(parseJsonObject(a.text)))],
  loadb: (a) => dumps(loadb(a.receipt)),
  render_cmdline: (a) => renderCmdline(a.argv),
  build_argv: (a) =>
    buildArgv({
      exe: a.exe,
      prompt: a.prompt,
      transport: a.transport,
      flags: a.flags,
      promptFlag: a.prompt_flag,
      promptPath: a.prompt_path,
    }).cmdlineLen,
  prompt_on_argv: (a) => promptOnArgv(a.element, a.prompt),
  check_dispatch: (a) => [
    ...checkDispatch({ background: a.background, timeoutS: a.timeout, awaited: a.awaited }),
  ],
  debit: (a) => spentMicro(debit(ledger({ limitMicro: a.limit }), a.unit, { attempt: a.attempt, micro: a.micro })),
  cost_per_success: (a) =>
    costPerSuccess(
      debit(ledger({ limitMicro: a.limit }), "u", { attempt: 1, micro: a.micro }),
      { successes: a.successes },
    ),
  rate_limit_backoff_ms: (a) => rateLimitBackoffMs(a.attempt),
  plan_retry: (a) => {
    const decision = planRetry(a.reason, { attempt: a.attempt });
    return { retry: decision.retry, next: decision.nextAttempt, backoff: decision.backoffMs };
  },
  success_line: (a) => successLine(a.unit),
  classify: (a) => {
    const classified = classify(a.text);
    return { kind: classified.kind, marker: classified.marker };
  },
  validate_observation: (a) => [
    ...validateObservation(
      observation({
        status: a.status,
        summary: a.summary,
        nextActions: a.next,
        error:
          a.code === null
            ? null
            : errorDetail({
                code: a.code,
                rootCause: a.root_cause,
                retryInstruction: a.retry_instruction,
                stopCondition: a.stop_condition,
              }),
      }),
    ),
  ],
  wire_is_blank: (a) => isBlank(a.text),
  wire_utf16_len: (a) => utf16Len(a.text),
  wire_fold_ascii_case: (a) => foldAsciiCase(a.text),
  wire_is_printable_id: (a) => isPrintableId(a.text),
});

/** Every operation the corpus may name, sorted. The Python emitter asserts the SAME set. */
export const OPERATIONS = Object.freeze(Object.keys(OPS).sort());

/** Run one case and render its outcome as canonical JSON text. */
export function runCase(entry) {
  if (!Object.hasOwn(OPS, entry.op)) {
    throw new BehaviourCorpusError(`case ${entry.id}: unknown op ${JSON.stringify(entry.op)}`);
  }
  const args = Object.fromEntries(
    Object.entries(entry.args).map(([name, node]) => [name, decodeArg(node)]),
  );
  let outcome;
  try {
    outcome = { ok: OPS[entry.op](args) };
  } catch (cause) {
    outcome = { err: errorKind(cause) };
  }
  return { id: entry.id, output: dumps(outcome) };
}

/** Run every case. Refuses a corpus that would pass vacuously. */
export function runCorpus(corpus) {
  if (!Array.isArray(corpus.cases) || corpus.cases.length === 0) {
    throw new BehaviourCorpusError("corpus has no cases; an empty corpus passes vacuously");
  }
  const ids = corpus.cases.map((entry) => entry.id);
  if (new Set(ids).size !== ids.length) {
    throw new BehaviourCorpusError("corpus has duplicate case ids");
  }
  const exercised = new Set(corpus.cases.map((entry) => entry.op));
  for (const op of OPERATIONS) {
    if (!exercised.has(op)) {
      throw new BehaviourCorpusError(`no corpus case exercises op ${JSON.stringify(op)}`);
    }
  }
  return corpus.cases.map((entry) => runCase(entry));
}
