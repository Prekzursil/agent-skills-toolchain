/**
 * The SHARED CONFORMANCE CORPUS driver — the contract both runtimes are executed against.
 *
 * The corpus itself is language-neutral plain JSON at `fixtures/canonical-corpus.json`. It is
 * THE contract; this module and `parity/emit_py.py` are two readers of it, and the parity
 * oracle byte-compares what they emit.
 *
 * Why a tagged construction DSL instead of raw JSON values: a bare JSON number cannot say
 * whether it means a Python `int` or a Python `float`, and those render differently under R6/R7
 * (`{"int": "1"}` is an integer-typed value bounded by 2**53; `{"num": "1"}` is a double). A
 * measured false DIFFERENT in the scout probe came from exactly that ambiguity — Python `2**53`
 * opposite JS `2 ** 53` compared an int against a double. Every case therefore pins the TYPE,
 * not just the value. A plain JSON object also cannot preserve insertion order for
 * integer-like keys in JS, so mappings are built from ordered PAIRS.
 *
 * Grammar — every value node is an object with EXACTLY ONE key:
 *
 *   {"str": "text"}                    a string (JSON escapes give lone surrogates)
 *   {"int": "123"}                     integer-typed: Python int / JS BigInt
 *   {"num": "1.5"}                     double: Python float / JS number
 *                                      also "NaN" / "Infinity" / "-Infinity" / "-0"
 *   {"bool": true}                     a boolean
 *   {"null": true}                     null / None
 *   {"arr": [node, ...]}               array / list
 *   {"obj": [[key, node], ...]}        object / dict, in the given insertion order
 *   {"nest": {"depth": N, "kind": K}}  a chain of N nested "arr" or "obj" around an int 1
 */

import { CanonicalJsonError, dumps } from "./canonical.mjs";

/** A corpus file or case is malformed. Distinct from a case FAILING its expectation. */
export class CorpusError extends Error {
  constructor(message) {
    super(message);
    this.name = "CorpusError";
  }
}

const NEST_KINDS = Object.freeze(["arr", "obj"]);

/** Materialise one value node into a native JS value. */
export function buildValue(node) {
  if (node === null || typeof node !== "object" || Array.isArray(node)) {
    throw new CorpusError(`value node must be a tagged object, got ${JSON.stringify(node)}`);
  }
  const tags = Object.keys(node);
  if (tags.length !== 1) {
    throw new CorpusError(`value node must have exactly one tag, got ${JSON.stringify(tags)}`);
  }
  const [tag] = tags;
  const body = node[tag];
  if (tag === "str") {
    return body;
  }
  if (tag === "int") {
    return BigInt(body);
  }
  if (tag === "num") {
    return Number(body);
  }
  if (tag === "bool") {
    return body;
  }
  if (tag === "null") {
    return null;
  }
  if (tag === "arr") {
    return body.map((item) => buildValue(item));
  }
  if (tag === "obj") {
    return buildMapping(body);
  }
  if (tag === "nest") {
    return buildNest(body);
  }
  throw new CorpusError(`unknown value tag ${JSON.stringify(tag)}`);
}

/**
 * Build a mapping from ORDERED pairs.
 *
 * `Object.fromEntries` would be shorter but a null-prototype object built by hand is what keeps
 * a key like `__proto__` a plain data property instead of mutating the prototype — the
 * pollution hazard the scout flagged for decode-side consumers.
 */
function buildMapping(pairs) {
  const target = Object.create(null);
  for (const pair of pairs) {
    if (!Array.isArray(pair) || pair.length !== 2) {
      throw new CorpusError(`obj entries must be [key, node] pairs, got ${JSON.stringify(pair)}`);
    }
    Object.defineProperty(target, pair[0], {
      value: buildValue(pair[1]),
      enumerable: true,
      writable: true,
      configurable: true,
    });
  }
  return target;
}

function buildNest({ depth, kind }) {
  if (!NEST_KINDS.includes(kind)) {
    throw new CorpusError(`nest kind must be one of ${JSON.stringify(NEST_KINDS)}, got ${kind}`);
  }
  let value = 1n;
  for (let level = 0; level < depth; level += 1) {
    value = kind === "arr" ? [value] : wrap(value);
  }
  return value;
}

function wrap(inner) {
  const target = Object.create(null);
  Object.defineProperty(target, "n", {
    value: inner,
    enumerable: true,
    writable: true,
    configurable: true,
  });
  return target;
}

/**
 * Run one case and report what this runtime actually did.
 *
 * The shape is deliberately terminal: `{ id, status, output }` where `status` is `"ok"` or
 * `"reject"`. A thrown non-canonical error is NOT swallowed — it propagates, because an
 * unexpected crash must not be recorded as a tidy rejection.
 */
export function runCase(entry, encoder = dumps) {
  let value;
  try {
    value = buildValue(entry.value);
  } catch (cause) {
    throw new CorpusError(`case ${entry.id}: ${cause.message}`);
  }
  try {
    return { id: entry.id, status: "ok", output: encoder(value) };
  } catch (cause) {
    if (cause instanceof CanonicalJsonError) {
      return { id: entry.id, status: "reject", output: cause.code };
    }
    // NOT swallowed. Only a CanonicalJsonError is a REJECTION; anything else is a defect, and
    // recording it as a tidy `reject` row would let a crash masquerade as conformance. The
    // `encoder` seam above exists solely so a test can drive this arm — the same reason
    // `build_for_rail(inject_hardening=False)` exists on the Python side.
    throw cause;
  }
}

/** Run every case and pair each result with the corpus expectation. */
export function runCorpus(corpus, encoder = dumps) {
  assertShape(corpus);
  return corpus.cases.map((entry) => {
    const actual = runCase(entry, encoder);
    const expected = expectationOf(entry);
    return { ...actual, expected, agrees: actual.status === expected.status && actual.output === expected.output };
  });
}

/** The ids whose observed behaviour differs from the corpus expectation. */
export function disagreements(results) {
  return results.filter((result) => !result.agrees);
}

function expectationOf(entry) {
  if (Object.hasOwn(entry.expect, "ok")) {
    return { status: "ok", output: entry.expect.ok };
  }
  if (Object.hasOwn(entry.expect, "reject")) {
    return { status: "reject", output: entry.expect.reject };
  }
  throw new CorpusError(`case ${entry.id}: expect must carry "ok" or "reject"`);
}

/**
 * Refuse a corpus that could report a vacuous pass.
 *
 * An empty or duplicated case list would make every downstream gate green while measuring
 * nothing — the same failure mode as the Node coverage blindness this package guards against.
 */
function assertShape(corpus) {
  if (!Array.isArray(corpus.cases) || corpus.cases.length === 0) {
    throw new CorpusError("corpus has no cases; an empty corpus passes vacuously");
  }
  const ids = corpus.cases.map((entry) => entry.id);
  if (new Set(ids).size !== ids.length) {
    throw new CorpusError("corpus has duplicate case ids");
  }
}
