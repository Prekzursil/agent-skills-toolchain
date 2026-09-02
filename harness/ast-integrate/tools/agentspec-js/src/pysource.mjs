/**
 * Read declared CONSTANTS straight out of the Python package source.
 *
 * This is how acceptance criterion 7 is met without a build step: the closed taxonomy,
 * `PROMPT_TRANSPORTS` and every other shared vocabulary are DERIVED from `agentspec/*.py` at
 * test time rather than retyped as an independent JS decision. `test/crosslang.test.mjs` reads
 * the Python modules through these functions and fails if any JS mirror has drifted.
 *
 * The repo already uses this discipline in the other direction: `agentspec/tests/test_argv.py`
 * parses `tools/glob-argv-guard/glob_argv_guard.py` and asserts its own constant still equals
 * it, so neither file can invent a number.
 *
 * The extractor is deliberately small and is itself validated against KNOWN-BROKEN inputs in
 * `test/pysource.test.mjs` — a parser that silently returns `[]` for a renamed constant would
 * turn the whole drift gate green while measuring nothing, which is the exact failure class
 * this package exists to defeat.
 */

/** A constant could not be read from the Python source. NEVER degrades to an empty result. */
export class PythonSourceError extends Error {
  constructor(message) {
    super(message);
    this.name = "PythonSourceError";
  }
}

/**
 * The string members of a Python tuple literal assigned to `name`.
 *
 * Handles both the annotated (`REASONS: tuple[str, ...] = (`) and bare (`X = (`) forms, and
 * preserves declaration ORDER — order is part of the contract for these tuples, not incidental.
 */
export function readTupleOfStrings(source, name) {
  const body = readAssignedGroup(source, name);
  const members = [...body.matchAll(/"((?:[^"\\]|\\.)*)"/gu)].map((match) =>
    decodePythonStringBody(match[1]),
  );
  if (members.length === 0) {
    throw new PythonSourceError(`tuple ${name} parsed to zero members; the source shape changed`);
  }
  return members;
}

/**
 * A tuple whose members are NAMES of string constants, resolved to their values.
 *
 * `canonical.py` declares `REJECTION_CODES = (E_CYCLIC, E_INT_RANGE, ...)` — references, not
 * literals. `readTupleOfStrings` correctly REFUSES that rather than quietly returning `[]`
 * (which would have turned the drift gate green while checking nothing), so the indirection
 * gets its own reader that follows each name to its own `NAME = "..."` declaration.
 */
export function readTupleOfNamedStrings(source, name) {
  const body = readAssignedGroup(source, name);
  const identifiers = [...body.matchAll(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*,/gmu)].map(
    (match) => match[1],
  );
  if (identifiers.length === 0) {
    throw new PythonSourceError(`tuple ${name} names zero constants; the source shape changed`);
  }
  return identifiers.map((identifier) => readStringConstant(source, identifier));
}

/** The integer literal assigned to `name` (underscore digit separators allowed). */
export function readIntConstant(source, name) {
  const raw = readAssignedExpression(source, name);
  if (!/^-?\d[\d_]*$/u.test(raw)) {
    throw new PythonSourceError(`${name} is not a plain integer literal: ${raw}`);
  }
  return Number.parseInt(raw.replaceAll("_", ""), 10);
}

/** The string literal assigned to `name`. */
export function readStringConstant(source, name) {
  const raw = readAssignedExpression(source, name);
  const match = /^"((?:[^"\\]|\\.)*)"$/u.exec(raw);
  if (match === null) {
    throw new PythonSourceError(`${name} is not a plain string literal: ${raw}`);
  }
  return decodePythonStringBody(match[1]);
}

/** The text between the parentheses of the tuple assigned to `name`. */
function readAssignedGroup(source, name) {
  const start = findAssignment(source, name);
  const open = source.indexOf("(", start);
  if (open === -1) {
    throw new PythonSourceError(`${name} is assigned but no tuple parenthesis follows`);
  }
  let depth = 0;
  let quote = null;
  for (let index = open; index < source.length; index += 1) {
    const char = source[index];
    if (quote !== null) {
      if (char === "\\") {
        index += 1;
      } else if (char === quote) {
        quote = null;
      }
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
    } else if (char === "(") {
      depth += 1;
    } else if (char === ")") {
      depth -= 1;
      if (depth === 0) {
        return source.slice(open + 1, index);
      }
    }
  }
  throw new PythonSourceError(`${name} has an unterminated tuple literal`);
}

/** The single-line expression assigned to `name`, trimmed of trailing comments. */
function readAssignedExpression(source, name) {
  const start = findAssignment(source, name);
  const lineEnd = source.indexOf("\n", start);
  const line = lineEnd === -1 ? source.slice(start) : source.slice(start, lineEnd);
  const equals = line.indexOf("=");
  const raw = line.slice(equals + 1).trim();
  const comment = raw.indexOf("  #");
  return (comment === -1 ? raw : raw.slice(0, comment)).trim();
}

/**
 * The offset of the top-level `name = ...` assignment.
 *
 * Anchored to the start of a line so a mention inside a docstring or an indented local
 * rebinding cannot be mistaken for the declaration — the use-vs-mention trap.
 */
function findAssignment(source, name) {
  const pattern = new RegExp(`^${escapeForRegExp(name)}(?::[^=\\n]+)?\\s*=`, "mu");
  const match = pattern.exec(source);
  if (match === null) {
    throw new PythonSourceError(`no top-level assignment to ${name} found`);
  }
  return match.index;
}

/** The escape forms these constants actually use. Anything else is a hard error, not a guess. */
function decodePythonStringBody(body) {
  return body.replaceAll(/\\(u[0-9a-fA-F]{4}|.)/gu, (whole, escape) => {
    if (escape[0] === "u") {
      return String.fromCharCode(Number.parseInt(escape.slice(1), 16));
    }
    if (escape === "\\" || escape === '"' || escape === "'") {
      return escape;
    }
    if (escape === "n") {
      return "\n";
    }
    if (escape === "t") {
      return "\t";
    }
    throw new PythonSourceError(`unsupported escape ${JSON.stringify(whole)} in a constant`);
  });
}

function escapeForRegExp(text) {
  return text.replaceAll(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}
