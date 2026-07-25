#!/usr/bin/env python3
"""workflow_lint.py -- a static linter for saved Claude Code Workflow scripts.

A saved Workflow is a ``.js``/``.mjs`` orchestration script under ``~/.claude/workflows``
that uses the runtime-injected ``agent`` / ``parallel`` / ``phase`` globals and an
``export const meta`` literal. This linter HARD-FAILS (non-zero exit) on the
determinism-breakers that silently corrupt resume + prompt-cache, and WARNS on the
recorded authoring footguns. Every check is grounded in ``../SKILL.md``:

  HARD-FAIL (exit 1)
    * no-date-now          -- ``Date.now()``      (SKILL.md rule 3: banned non-determinism)
    * no-math-random       -- ``Math.random()``   (SKILL.md rule 3)
    * no-argless-new-date  -- ``new Date()``       (SKILL.md rule 3; ``new Date(x)`` is fine)
    * meta-missing         -- no ``export const meta`` (SKILL.md rule 1 + checklist)
    * meta-not-object      -- ``meta`` is not an object literal
    * meta-not-literal     -- ``meta`` has a computed/non-literal field (rule 3 + cache-cliff rule 8)
  WARN (advisory; exit 0 unless --strict)
    * args-parse-if-string -- ``args.<field>`` with no parse-if-string guard (SKILL.md rule 2)
    * agent-schema         -- an ``agent(...)`` call with no ``schema:`` option (SKILL.md rule 7)
    * parallel-filter-boolean -- a ``parallel(...)`` result not passed through ``.filter(Boolean)`` (rule 5)

METHOD (stated honestly; no overclaiming)
    Python's standard library has no JavaScript parser, so this is NOT a full AST
    analysis. Instead it runs a single-pass lexical MASK (``mask_code``) that blanks
    comment bodies and string/template *literal text* to spaces -- preserving byte
    offsets and newlines so ``file:line`` stays exact -- and then applies well-anchored
    regexes plus small balanced-bracket scans to the masked, code-only text. That mask
    is what keeps false-positives low: a banned call quoted inside a string or comment
    does not fire. The ``meta`` literal-ness check is a dedicated recursive-descent
    parser over the JSON-superset of JS object literals (unquoted keys, single quotes,
    trailing commas, ``//`` + ``/* */`` comments); anything it cannot parse as a pure
    literal -- an identifier, a call, a computed ``[key]``, a ``${...}`` interpolation,
    a spread, a method shorthand -- is reported at the offending line.

KNOWN LIMITS (documented, not hidden)
    * Template-interpolation code is preserved single-level with brace tracking, so
      ``${Date.now()}`` IS caught; deeply nested templates, or a ``}`` inside a string
      inside an interpolation, may be masked imperfectly.
    * The ``agent`` schema check looks for a literal ``schema:`` key in the call; passing
      options via a variable (``agent(p, opts)``) is flagged as a (false) WARN.
    * The ``parallel`` check recognises an immediate ``.filter(Boolean)`` or a
      ``NAME....filter(Boolean)`` member chain on the assigned result; a barrier that
      handles nulls another way (e.g. ``r[i] && ...``) is still WARNed -- advisory only.
    * ``args`` bracket access (``args['x']``) is not inspected; only dot access is.
    These are WARN-level or edge cases by design; the HARD-FAIL checks target the common
    determinism-breaker forms.

Runnable as a CLI or importable::

    python workflow_lint.py path/to/wf.mjs [more...] [--json] [--strict]
    python workflow_lint.py ~/.claude/workflows        # a directory is walked for *.js/*.mjs
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

ERROR = "error"
WARN = "warn"

# String.prototype members: ``args.<member>`` here is legitimate raw-string handling
# (args arrives as one string), NOT the "assumed structured" footgun, so it is exempt.
STRING_MEMBERS = frozenset(
    {
        "length",
        "at",
        "charAt",
        "charCodeAt",
        "codePointAt",
        "concat",
        "endsWith",
        "includes",
        "indexOf",
        "lastIndexOf",
        "localeCompare",
        "match",
        "matchAll",
        "normalize",
        "padEnd",
        "padStart",
        "repeat",
        "replace",
        "replaceAll",
        "search",
        "slice",
        "split",
        "startsWith",
        "substr",
        "substring",
        "toLowerCase",
        "toUpperCase",
        "toLocaleLowerCase",
        "toLocaleUpperCase",
        "toString",
        "trim",
        "trimEnd",
        "trimStart",
        "valueOf",
    }
)


@dataclass(frozen=True)
class Finding:
    """One diagnostic. ``level`` is ``ERROR`` (hard-fail) or ``WARN`` (advisory)."""

    path: str
    line: int
    level: str
    check: str
    message: str


# --------------------------------------------------------------------------- #
# Lexical mask: blank comment + string/template literal text to spaces, keeping
# byte offsets and newlines so regex checks see only code and file:line stays exact.
# --------------------------------------------------------------------------- #
def _mask_string(text: str, i: int, quote: str, out: list[str]) -> int:
    """Mask a ``'``/``"`` string starting at ``i`` (delimiter kept, body blanked)."""
    n = len(text)
    out.append(quote)
    i += 1
    while i < n:
        c = text[i]
        if c == "\\":
            out.append(" ")
            i += 1
            if i < n:
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
        elif c == quote:
            out.append(quote)
            return i + 1
        elif c == "\n":
            out.append("\n")
            i += 1
        else:
            out.append(" ")
            i += 1
    return i


def _mask_interp(text: str, i: int, out: list[str]) -> int:
    """Copy ``${...}`` interpolation CODE verbatim (so banned calls stay visible),
    tracking brace depth to find the matching close."""
    n = len(text)
    depth = 1
    while i < n:
        c = text[i]
        if c == "{":
            depth += 1
            out.append(c)
            i += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                out.append(" ")
                return i + 1
            out.append(c)
            i += 1
        else:
            out.append(c)
            i += 1
    return i


def _mask_template(text: str, i: int, out: list[str]) -> int:
    """Mask a template literal: blank the literal text, preserve ``${...}`` code."""
    n = len(text)
    out.append("`")
    i += 1
    while i < n:
        c = text[i]
        if c == "\\":
            out.append(" ")
            i += 1
            if i < n:
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
        elif c == "`":
            out.append("`")
            return i + 1
        elif text.startswith("${", i):
            out.append("  ")
            i = _mask_interp(text, i + 2, out)
        elif c == "\n":
            out.append("\n")
            i += 1
        else:
            out.append(" ")
            i += 1
    return i


def mask_code(text: str) -> str:
    """Return ``text`` with comment + string/template literal bodies blanked to spaces.

    Same length and same newline positions as the input, so a regex match offset maps
    back to the original ``file:line`` unchanged.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            out.append("  ")
            i += 2
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
        elif text.startswith("/*", i):
            out.append("  ")
            i += 2
            while i < n and not text.startswith("*/", i):
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
        elif c in "'\"":
            i = _mask_string(text, i, c, out)
        elif c == "`":
            i = _mask_template(text, i, out)
        else:
            out.append(c)
            i += 1
    return "".join(out)


# --------------------------------------------------------------------------- #
# Pure-literal parser for the ``meta`` initializer (JSON-superset of JS object literals).
# --------------------------------------------------------------------------- #
class _LiteralError(Exception):
    """Raised at the offset where the ``meta`` initializer stops being a pure literal."""

    def __init__(self, offset: int, message: str) -> None:
        super().__init__(message)
        self.offset = offset
        self.message = message


_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
_NUMBER = re.compile(
    r"[+-]?(?:0[xX][0-9a-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+|"
    r"(?:\d[\d_]*)?\.\d[\d_]*(?:[eE][+-]?\d+)?|"
    r"\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?)n?"
)


def _skip_ws(text: str, i: int) -> int:
    """Skip whitespace and ``//`` / ``/* */`` comments; raise on an unterminated block."""
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j == -1:
                raise _LiteralError(i, "unterminated block comment")
            i = j + 2
        else:
            break
    return i


def _peek(text: str, i: int) -> str:
    if i >= len(text):
        raise _LiteralError(i, "unexpected end of input inside literal")
    return text[i]


def _parse_string_literal(text: str, i: int) -> int:
    quote = text[i]
    n = len(text)
    i += 1
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if quote == "`" and text.startswith("${", i):
            raise _LiteralError(
                i, "template-literal interpolation ${...} is not a pure literal"
            )
        if c == quote:
            return i + 1
        i += 1
    raise _LiteralError(i, "unterminated string literal")


def _parse_keyword(text: str, i: int) -> int | None:
    for kw in ("true", "false", "null"):
        if text.startswith(kw, i):
            j = i + len(kw)
            if j >= len(text) or not (text[j].isalnum() or text[j] in "_$"):
                return j
    return None


def _parse_value(text: str, i: int) -> int:
    i = _skip_ws(text, i)
    if i >= len(text):
        raise _LiteralError(i, "expected a value")
    c = text[i]
    if c == "{":
        return _parse_object(text, i)
    if c == "[":
        return _parse_array(text, i)
    if c in "'\"`":
        return _parse_string_literal(text, i)
    kw = _parse_keyword(text, i)
    if kw is not None:
        return kw
    num = _NUMBER.match(text, i)
    if num is not None:
        return num.end()
    raise _LiteralError(i, f"non-literal token near {text[i : i + 16]!r}")


def _parse_object(text: str, i: int) -> int:
    i += 1  # consume {
    while True:
        i = _skip_ws(text, i)
        c = _peek(text, i)
        if c == "}":
            return i + 1
        if c == "[":
            raise _LiteralError(i, "computed property key [...] is not a pure literal")
        if c in "'\"":
            i = _parse_string_literal(text, i)
        else:
            km = _IDENT.match(text, i)
            if km is None:
                raise _LiteralError(i, "expected a property name")
            i = km.end()
        i = _skip_ws(text, i)
        c = _peek(text, i)
        if c == "(":
            raise _LiteralError(i, "method definition is not a pure literal value")
        if c != ":":
            raise _LiteralError(i, "expected ':' after property name")
        i = _parse_value(text, i + 1)
        i = _skip_ws(text, i)
        c = _peek(text, i)
        if c == ",":
            i += 1
            continue
        if c == "}":
            return i + 1
        raise _LiteralError(i, "expected ',' or '}' in object literal")


def _parse_array(text: str, i: int) -> int:
    i += 1  # consume [
    while True:
        i = _skip_ws(text, i)
        c = _peek(text, i)
        if c == "]":
            return i + 1
        i = _parse_value(text, i)
        i = _skip_ws(text, i)
        c = _peek(text, i)
        if c == ",":
            i += 1
            continue
        if c == "]":
            return i + 1
        raise _LiteralError(i, "expected ',' or ']' in array literal")


# --------------------------------------------------------------------------- #
# Balanced-bracket + member-chain scans over MASKED text.
# --------------------------------------------------------------------------- #
_PAIRS = {"(": ")", "[": "]", "{": "}"}


def _match_bracket(masked: str, open_idx: int) -> int | None:
    """Index of the bracket matching ``masked[open_idx]``, or ``None`` if unbalanced."""
    opening = masked[open_idx]
    closing = _PAIRS[opening]
    depth = 0
    n = len(masked)
    i = open_idx
    while i < n:
        ch = masked[i]
        if ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _member_chain_end(masked: str, i: int) -> int:
    """Consume a ``.member`` / ``(...)`` / ``[...]`` chain from ``i``; return its end."""
    n = len(masked)
    while i < n:
        j = i
        while j < n and masked[j] in " \t\r\n":
            j += 1
        if j < n and masked[j] == ".":
            j += 1
            while j < n and masked[j] in " \t\r\n":
                j += 1
            while j < n and (masked[j].isalnum() or masked[j] in "_$"):
                j += 1
            i = j
        elif j < n and masked[j] in "([":
            close = _match_bracket(masked, j)
            if close is None:
                return j
            i = close + 1
        else:
            return i
    return i


def _line_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


# --------------------------------------------------------------------------- #
# Checks.
# --------------------------------------------------------------------------- #
# Match up to and including the ``=`` only (NOT trailing whitespace/comments): the
# initializer is then located on the ORIGINAL text via ``_skip_ws`` so an unterminated
# comment right after ``=`` is reported rather than silently masked away.
_META_RE = re.compile(r"\bexport\s+const\s+meta\s*=")


def _check_meta(text: str, masked: str, path: str, findings: list[Finding]) -> None:
    m = _META_RE.search(masked)
    if m is None:
        findings.append(
            Finding(
                path,
                1,
                ERROR,
                "meta-missing",
                "missing top-level `export const meta = { ... }` (SKILL.md rule 1)",
            )
        )
        return
    try:
        start = _skip_ws(text, m.end())
    except _LiteralError as exc:
        findings.append(
            Finding(
                path,
                _line_at(text, exc.offset),
                ERROR,
                "meta-not-literal",
                f"`export const meta` is not a pure literal: {exc.message}",
            )
        )
        return
    if start >= len(text) or text[start] != "{":
        findings.append(
            Finding(
                path,
                _line_at(text, start),
                ERROR,
                "meta-not-object",
                "`export const meta` must be an object literal `{ ... }`",
            )
        )
        return
    try:
        _parse_object(text, start)
    except _LiteralError as exc:
        findings.append(
            Finding(
                path,
                _line_at(text, exc.offset),
                ERROR,
                "meta-not-literal",
                f"`export const meta` has a non-literal (computed) field: {exc.message}. "
                "meta must be a pure literal (SKILL.md rules 1 + 3 + 8)",
            )
        )


_BANNED = (
    (
        re.compile(r"\bDate\s*\.\s*now\s*\("),
        "no-date-now",
        "Date.now() is banned in workflow JS -- it breaks resume + busts the prompt "
        "cache (SKILL.md rule 3). Generate timestamps inside an agent tool call instead.",
    ),
    (
        re.compile(r"\bMath\s*\.\s*random\s*\("),
        "no-math-random",
        "Math.random() is banned in workflow JS -- non-deterministic, breaks resume "
        "(SKILL.md rule 3). Generate random ids inside an agent tool call instead.",
    ),
    (
        re.compile(r"\bnew\s+Date\s*\(\s*\)"),
        "no-argless-new-date",
        "argless new Date() is banned in workflow JS -- non-deterministic (SKILL.md "
        "rule 3). Use new Date(<explicit value>) or produce time inside an agent.",
    ),
)


def _check_banned(masked: str, path: str, findings: list[Finding]) -> None:
    for rx, check, message in _BANNED:
        for m in rx.finditer(masked):
            findings.append(
                Finding(path, _line_at(masked, m.start()), ERROR, check, message)
            )


_ARGS_ACCESS = re.compile(r"\bargs\s*\.\s*([A-Za-z_$][\w$]*)")
_ARGS_GUARD = re.compile(
    r"JSON\s*\.\s*parse\s*\(\s*args\b|typeof\s+args\s*===?\s*['\"]string['\"]"
)


def _check_args(masked: str, path: str, findings: list[Finding]) -> None:
    if _ARGS_GUARD.search(masked):
        return
    seen: set[int] = set()
    for m in _ARGS_ACCESS.finditer(masked):
        if m.group(1) in STRING_MEMBERS:
            continue
        line = _line_at(masked, m.start())
        if line in seen:
            continue
        seen.add(line)
        findings.append(
            Finding(
                path,
                line,
                WARN,
                "args-parse-if-string",
                "args arrives as ONE string, not a parsed object (SKILL.md rule 2). "
                f"Reading args.{m.group(1)} without a parse-if-string guard "
                "(typeof args === 'string' ? JSON.parse(args) : args) silently reads "
                "undefined. Parse args, or have agents auto-discover their input.",
            )
        )


_AGENT_CALL = re.compile(r"\bagent\s*\(")
_SCHEMA_KEY = re.compile(r"\bschema\s*:")


def _check_agent_schema(masked: str, path: str, findings: list[Finding]) -> None:
    for m in _AGENT_CALL.finditer(masked):
        close = _match_bracket(masked, m.end() - 1)
        if close is None:
            continue
        if _SCHEMA_KEY.search(masked, m.end(), close):
            continue
        findings.append(
            Finding(
                path,
                _line_at(masked, m.start()),
                WARN,
                "agent-schema",
                "agent(...) has no schema: option (SKILL.md rule 7). A fan-in agent "
                "should return a parsed schema object, not prose to re-parse. Add a "
                "schema with additionalProperties:false and an explicit required[].",
            )
        )


_PARALLEL_CALL = re.compile(r"\bparallel\s*\(")
_FILTER_AFTER = re.compile(r"\s*\)?\s*\.\s*filter\s*\(\s*Boolean\s*\)")
_FILTER_CHAIN = re.compile(r"\.\s*filter\s*\(\s*Boolean\s*\)")
_ASSIGN_BEFORE = re.compile(
    r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:await\s+)?\(?\s*(?:await\s+)?$"
)


def _var_has_filter(masked: str, name: str, from_idx: int) -> bool:
    pattern = re.compile(r"\b" + re.escape(name) + r"\b")
    for um in pattern.finditer(masked, from_idx):
        end = _member_chain_end(masked, um.end())
        if _FILTER_CHAIN.search(masked, um.end(), end):
            return True
    return False


def _check_parallel_filter(masked: str, path: str, findings: list[Finding]) -> None:
    for m in _PARALLEL_CALL.finditer(masked):
        close = _match_bracket(masked, m.end() - 1)
        if close is None:
            continue
        if _FILTER_AFTER.match(masked, close + 1):
            continue
        assign = _ASSIGN_BEFORE.search(masked, 0, m.start())
        if assign is not None and _var_has_filter(masked, assign.group(1), close + 1):
            continue
        findings.append(
            Finding(
                path,
                _line_at(masked, m.start()),
                WARN,
                "parallel-filter-boolean",
                "parallel(...) result is not passed through .filter(Boolean) "
                "(SKILL.md rule 5). A throwing thunk resolves to null; without the "
                "null-tolerant barrier one dead agent poisons the aggregation.",
            )
        )


def lint_text(text: str, path: str = "<workflow>") -> list[Finding]:
    """Lint workflow source ``text``; return findings sorted by (line, check)."""
    masked = mask_code(text)
    findings: list[Finding] = []
    _check_meta(text, masked, path, findings)
    _check_banned(masked, path, findings)
    _check_args(masked, path, findings)
    _check_agent_schema(masked, path, findings)
    _check_parallel_filter(masked, path, findings)
    findings.sort(key=lambda f: (f.line, f.check))
    return findings


def lint_file(path: str | Path) -> list[Finding]:
    """Read and lint one file; a read/decoding failure is itself an ERROR finding."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [Finding(str(path), 1, ERROR, "read-error", f"cannot read file: {exc}")]
    return lint_text(text, str(path))


def iter_workflow_files(paths: Sequence[str]) -> list[Path]:
    """Expand each path: a directory is walked for ``*.js``/``*.mjs``; a file is kept
    as-is (even if it does not exist -- so ``lint_file`` reports a read-error)."""
    result: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found = sorted(set(p.rglob("*.js")) | set(p.rglob("*.mjs")))
        else:
            found = [p]
        for q in found:
            resolved = q.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            result.append(q)
    return result


def format_finding(f: Finding) -> str:
    return f"{f.path}:{f.line}: {f.level.upper()}[{f.check}]: {f.message}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="workflow_lint",
        description="Lint saved Claude Code Workflow scripts for determinism-breakers "
        "and authoring footguns.",
    )
    parser.add_argument("paths", nargs="+", help="workflow files or directories")
    parser.add_argument(
        "--json", action="store_true", help="emit findings as a JSON array"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="also exit non-zero when only warnings are found",
    )
    ns = parser.parse_args(argv)

    files = iter_workflow_files(ns.paths)
    findings: list[Finding] = []
    for f in files:
        findings.extend(lint_file(f))

    if ns.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        for finding in findings:
            print(format_finding(finding))
        errors = sum(1 for f in findings if f.level == ERROR)
        warnings = sum(1 for f in findings if f.level == WARN)
        print(
            f"workflow-lint: {errors} error(s), {warnings} warning(s) "
            f"across {len(files)} file(s)",
            file=sys.stderr,
        )

    has_error = any(f.level == ERROR for f in findings)
    failed = has_error or (ns.strict and bool(findings))
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
