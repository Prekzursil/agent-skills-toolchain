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
    * sandbox-forbidden    -- ``require`` / ``import`` / ``eval`` / ``new Function`` / ``process.``
                              (the vm sandbox has no module loader and codeGeneration.strings=false)
  WARN (advisory; exit 0 unless --strict)
    * args-unguarded       -- ``args.<field>`` with no absent-args guard (see below)
    * agent-schema         -- an ``agent(...)`` call with no ``schema:`` option (SKILL.md rule 7)
    * parallel-filter-boolean -- a ``parallel(...)`` result not passed through ``.filter(Boolean)`` (rule 5)
    * barrier-without-timeout -- a ``parallel(...)`` over ``agent(...)`` with no per-agent timeout
                              (design item H6; one hung agent freezes the whole phase)
    * prefer-pipeline      -- two barriers separated only by a pure transform (the runtime's own
                              smell test: "that middle transform doesn't need the barrier")
    * budget-loop-unguarded -- ``while (budget.remaining() ...)`` with no ``budget.total`` guard
                              (with no target, remaining() is Infinity -> runs to the 1000-agent cap)

CORRECTION, 2026-08-12 -- ``args-parse-if-string`` was RENAMED to ``args-unguarded`` because
its premise was measured FALSE. The installed runtime's own tool doc says ``args`` is "the value
passed as Workflow's ``args`` input, **verbatim** (undefined if not provided)". It is NOT coerced
to a string. The real footgun is the *absent* case: with no args, ``args.<field>`` throws a
TypeError. A caller who stringifies a list does reach the script with one string, but that is a
caller-side mistake, not the runtime contract, so the guard is now advisory in both directions.

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
    * The ``agent`` schema check looks for a literal ``schema:`` key in the call. A
      two-parameter forwarding wrapper -- ``function W(p, o) { ... return agent(p, o) }``
      -- is recognised: its forwarding call is exempt and ``W(...)`` call sites are
      checked instead (the governed-run template's ``countedAgent``; the old behaviour
      flagged that template's forwarding line on every use -- measured 2026-08-17,
      the only finding wf_gate produced over the repo's own templates). Any OTHER
      variable-options form (a bare ``agent(p, opts)`` outside such a wrapper, an
      arrow-function wrapper, reordered parameters) is still flagged as a (false) WARN.
      That recognition has three residual shapes, measured 2026-08-18 by two
      independent probes and named here rather than left to be rediscovered:
      (a) ``return await agent(p, o)`` is NOT read as forwarding, so its forwarding
      line still WARNs exactly as before; (b) the ``W(...)`` call-site scan matches
      the bare name lexically, so a same-named method call or definition
      (``tracker.W(...)``) or an unrelated ``W(...)`` can WARN as a false positive
      that did not exist before the exemption; (c) an INDIRECT invocation -- an
      alias (``const W2 = W``) or a wrapper exported for another file -- is not
      retargeted, so a schema-less indirect call is now SILENT where the
      pre-exemption rule at least fired once (at the misleading forwarding line).
      (c) is the deliberate trade: one guaranteed false positive on every wrapper,
      exchanged for a false negative on indirect use. All three are advisory
      WARN-level and produce zero verdict delta over this repo's 1,342-file
      workflow corpus.
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


# A generous ceiling on meta object/array nesting. Real meta is 2-3 deep; this only
# exists so a pathological input raises a clean `meta-not-literal` finding instead of a
# RecursionError -- a linter must never crash on the file it is handed.
_MAX_DEPTH = 100
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


def _parse_value(text: str, i: int, depth: int) -> int:
    if depth > _MAX_DEPTH:
        raise _LiteralError(i, "meta nesting exceeds the depth limit")
    i = _skip_ws(text, i)
    if i >= len(text):
        raise _LiteralError(i, "expected a value")
    c = text[i]
    if c == "{":
        return _parse_object(text, i, depth)
    if c == "[":
        return _parse_array(text, i, depth)
    if c in "'\"`":
        return _parse_string_literal(text, i)
    kw = _parse_keyword(text, i)
    if kw is not None:
        return kw
    num = _NUMBER.match(text, i)
    if num is not None:
        return num.end()
    raise _LiteralError(i, f"non-literal token near {text[i : i + 16]!r}")


def _parse_object(text: str, i: int, depth: int) -> int:
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
        i = _parse_value(text, i + 1, depth + 1)
        i = _skip_ws(text, i)
        c = _peek(text, i)
        if c == ",":
            i += 1
            continue
        if c == "}":
            return i + 1
        raise _LiteralError(i, "expected ',' or '}' in object literal")


def _parse_array(text: str, i: int, depth: int) -> int:
    i += 1  # consume [
    while True:
        i = _skip_ws(text, i)
        c = _peek(text, i)
        if c == "]":
            return i + 1
        i = _parse_value(text, i, depth + 1)
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
        _parse_object(text, start, 0)
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
# Any of these is an acceptable guard: a parse-if-string coercion (for a caller who
# stringified), or a plain absent-args default (`args ?? {}` / `args || {}` /
# `args && ...`), or an explicit `typeof args` probe.
_ARGS_GUARD = re.compile(
    r"JSON\s*\.\s*parse\s*\(\s*args\b"
    r"|typeof\s+args\b"
    r"|\bargs\s*(?:\?\?|\|\||&&)"
    r"|\bargs\s*===?\s*(?:undefined|null)"
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
                "args-unguarded",
                "args is delivered VERBATIM and is `undefined` when the workflow is "
                f"invoked with none, so reading args.{m.group(1)} unguarded throws a "
                "TypeError. Guard it: `const a = args ?? {}`. (A caller who passes a "
                "JSON-ENCODED string instead of a JSON value does reach the script with "
                "one string -- add `typeof args === 'string' ? JSON.parse(args) : args` "
                "if that is possible. The older 'args always arrives as one string' "
                "wording was measured false against the installed runtime.)",
            )
        )


# --------------------------------------------------------------------------- #
# Sandbox reality: the workflow body runs in a Node `vm` context built with
# codeGeneration.strings=false and NO module loader. These are not style
# preferences -- each one is a guaranteed runtime failure, so they are ERRORs.
# --------------------------------------------------------------------------- #
_FORBIDDEN = (
    (
        re.compile(r"\brequire\s*\("),
        "require() -- the workflow sandbox has no module loader",
    ),
    (
        re.compile(r"\bimport\s*\("),
        "dynamic import() -- throws in the workflow sandbox",
    ),
    (
        re.compile(r"^[ \t]*import\s+[^\n(]*\bfrom\b", re.MULTILINE),
        "a static `import ... from` -- the script is not an ES module",
    ),
    (
        re.compile(r"\beval\s*\("),
        "eval() -- blocked by codeGeneration.strings=false",
    ),
    (
        re.compile(r"\bnew\s+Function\s*\("),
        "new Function() -- blocked by codeGeneration.strings=false",
    ),
    (
        re.compile(r"\bprocess\s*\.\s*[A-Za-z_$]"),
        "process.* -- no Node.js API is exposed to the sandbox",
    ),
)


def _check_sandbox(masked: str, path: str, findings: list[Finding]) -> None:
    for rx, what in _FORBIDDEN:
        for m in rx.finditer(masked):
            findings.append(
                Finding(
                    path,
                    _line_at(masked, m.start()),
                    ERROR,
                    "sandbox-forbidden",
                    f"{what}. Paste the code inline, or do the work inside an agent().",
                )
            )


_AGENT_CALL = re.compile(r"\bagent\s*\(")
_SCHEMA_KEY = re.compile(r"\bschema\s*:")

# A two-parameter FORWARDING WRAPPER -- ``function W(p, o) { ... return agent(p, o) }``
# -- forwards its options VERBATIM, so a literal ``schema:`` can never appear at the
# forwarding call: the schema duty sits at W's call sites. The governed-run template
# ships exactly this wrapper (``countedAgent``, its agent-call budget reserve), and
# flagging the forwarding line was a measured false positive: the ONLY finding
# ``wf_gate`` produced over the repo's own templates (2026-08-17), red under
# ``--strict`` on the canonical template the skill tells authors to paste.
# Recognising the wrapper does two things AT ONCE: the forwarding call stops firing,
# and the wrapper's own call sites are checked for a literal ``schema:`` under the
# same rule -- so the exemption closes a blind spot instead of opening one.
_WRAPPER_DEF = re.compile(
    r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\("
    r"\s*([A-Za-z_$][\w$]*)\s*,\s*([A-Za-z_$][\w$]*)\s*\)\s*\{"
)


def _forwarding_wrappers(masked: str) -> tuple[set[str], set[int]]:
    """Names of verbatim-forwarding wrappers, plus masked offsets to EXEMPT from the
    schema scan: each recognised wrapper's definition-site name token (so its own
    parameter list is not read as a schema-less call) and each forwarding ``agent``
    token itself. Reordered/renamed forwarding (``return agent(o, p)``) is NOT a
    verbatim forward and stays under the plain advisory."""
    names: set[str] = set()
    skip: set[int] = set()
    for m in _WRAPPER_DEF.finditer(masked):
        body_close = _match_bracket(masked, m.end() - 1)
        if body_close is None:
            continue
        fwd = re.compile(
            r"\breturn\s+(agent)\s*\(\s*"
            + re.escape(m.group(2))
            + r"\s*,\s*"
            + re.escape(m.group(3))
            + r"\s*\)"
        ).search(masked, m.end(), body_close)
        if fwd is None:
            continue
        names.add(m.group(1))
        skip.add(m.start(1))
        skip.add(fwd.start(1))
    return names, skip


def _check_agent_schema(masked: str, path: str, findings: list[Finding]) -> None:
    wrapper_names, skip = _forwarding_wrappers(masked)
    calls: list[tuple[int, int]] = [
        (m.start(), m.end() - 1)
        for m in _AGENT_CALL.finditer(masked)
        if m.start() not in skip
    ]
    for name in sorted(wrapper_names):
        rx = re.compile(r"\b" + re.escape(name) + r"\s*\(")
        calls.extend(
            (m.start(), m.end() - 1)
            for m in rx.finditer(masked)
            if m.start() not in skip
        )
    for at, open_idx in sorted(set(calls)):
        close = _match_bracket(masked, open_idx)
        if close is None:
            continue
        if _SCHEMA_KEY.search(masked, open_idx + 1, close):
            continue
        findings.append(
            Finding(
                path,
                _line_at(masked, at),
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


# `.filter(Boolean)` is one way to be null-tolerant; a `.map(...)` that NAMES
# `null` is a stronger one -- it TYPES the drop instead of deleting it, which is
# what the H6 `settle()` helper does (design item H3: the runtime yields null for
# at least three different causes, and filtering throws that distinction away, so
# "12 of 15 returned" becomes unauditable). Recognising it keeps the rule from
# firing on the very helper that `barrier-without-timeout` recommends.
_MAP_AFTER = re.compile(r"\s*\)?\s*\.\s*map\s*\(")


_NULL_WORD = re.compile(r"\bnull\b")


def _maps_nulls(masked: str, at: int) -> bool:
    """True if a ``.map(...)`` starting at ``at`` mentions ``null`` in its body.

    The match is word-bounded on purpose. A bare substring test also matched
    ``v.nullable`` / ``nullish``, so a ``.map()`` that merely CONTAINS the letters
    silently suppressed ``parallel-filter-boolean`` -- a false negative in a rule
    that CI now runs over real template source.
    """
    m = _MAP_AFTER.match(masked, at)
    if m is None:
        return False
    body_close = _match_bracket(masked, m.end() - 1)
    if body_close is None:
        return False
    return _NULL_WORD.search(masked[m.end() : body_close]) is not None


def _var_is_null_tolerant(masked: str, name: str, from_idx: int) -> bool:
    """True if ``name`` is later `.filter(Boolean)`-ed or null-typed by a `.map`."""
    pattern = re.compile(r"\b" + re.escape(name) + r"\b")
    for um in pattern.finditer(masked, from_idx):
        end = _member_chain_end(masked, um.end())
        if _FILTER_CHAIN.search(masked, um.end(), end):
            return True
        if _maps_nulls(masked, um.end()):
            return True
    return False


def _check_parallel_filter(masked: str, path: str, findings: list[Finding]) -> None:
    for m in _PARALLEL_CALL.finditer(masked):
        close = _match_bracket(masked, m.end() - 1)
        if close is None:
            continue
        if _FILTER_AFTER.match(masked, close + 1):
            continue
        if _maps_nulls(masked, close + 1):
            continue
        assign = _ASSIGN_BEFORE.search(masked, 0, m.start())
        if assign is not None and _var_is_null_tolerant(
            masked, assign.group(1), close + 1
        ):
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


# --------------------------------------------------------------------------- #
# H6 -- barrier-without-timeout.
#
# `parallel()` is a BARRIER: it settles only when EVERY thunk settles. One agent
# that never returns therefore freezes the whole phase. Measured on this estate:
# a 13-hour deadlock, and 11 lanes stalled behind one hung reviewer. The fix is
# templates/h6-timeout-heartbeat.md -- wrap each thunk in `withTimeout(...)`, or
# call `settle(...)` instead of `parallel(...)`.
#
# HONEST SCOPE, so the WARN does not overclaim: the wrapper unblocks the BARRIER.
# It does NOT kill the agent -- the dropped agent keeps running and keeps its
# concurrency slot until it dies on its own.
# --------------------------------------------------------------------------- #
_TIMEOUT_WRAPPER = re.compile(
    r"\bwithTimeout\s*\(|\bsettle\s*\(|\bPromise\s*\.\s*race\s*\("
)


def _check_barrier_timeout(masked: str, path: str, findings: list[Finding]) -> None:
    for m in _PARALLEL_CALL.finditer(masked):
        close = _match_bracket(masked, m.end() - 1)
        if close is None:
            continue
        body = masked[m.end() : close]
        if not _AGENT_CALL.search(body):
            continue
        if _TIMEOUT_WRAPPER.search(body):
            continue
        findings.append(
            Finding(
                path,
                _line_at(masked, m.start()),
                WARN,
                "barrier-without-timeout",
                "parallel(...) fans out agent() calls with no per-agent timeout. "
                "parallel is a BARRIER, so ONE agent that never returns freezes the "
                "whole phase (measured: a 13-hour deadlock; 11 lanes behind one hung "
                "reviewer). Wrap each thunk with withTimeout(), or use settle() -- see "
                "templates/h6-timeout-heartbeat.md (design item H6). Note the wrapper "
                "unblocks the BARRIER only; the dropped agent keeps running and keeps "
                "its concurrency slot.",
            )
        )


# --------------------------------------------------------------------------- #
# prefer-pipeline -- the RUNTIME's own smell test, quoted verbatim from the
# installed tool doc:
#
#     Smell test: if you wrote
#       const a = await parallel(...)
#       const b = transform(a)     // flatten, map, filter - no cross-item dependency
#       const c = await parallel(b.map(...))
#     that middle transform doesn't need the barrier.
#
# The runtime also enumerates the THREE shapes where a barrier IS correct, so the
# rule stays silent on all three by requiring that the span between the two
# barriers contains no cross-item aggregation marker:
#   1. dedup/merge across the full set   -> new Set / .reduce / .sort / Object.*
#   2. early-exit when the count is zero -> .length
#   3. stage N's prompt cites "the other findings" -> .join / JSON.stringify
# DETECTOR LIMIT, stated rather than hidden: this is a lexical proximity check,
# not dataflow. A cross-item dependency expressed without any of these markers
# will still be flagged -- which is why it is a WARN, never an ERROR.
# --------------------------------------------------------------------------- #
_AGGREGATION_MARKER = re.compile(
    r"\.\s*(?:length|reduce|sort|join|every|some|find|findIndex|includes|indexOf)\b"
    r"|\bnew\s+Set\s*\(|\bJSON\s*\.\s*stringify\s*\(|\bObject\s*\.\s*[A-Za-z]"
)


def _check_prefer_pipeline(masked: str, path: str, findings: list[Finding]) -> None:
    barriers = list(_PARALLEL_CALL.finditer(masked))
    for first, second in zip(barriers, barriers[1:]):
        close = _match_bracket(masked, first.end() - 1)
        if close is None:
            continue
        assign = _ASSIGN_BEFORE.search(masked, 0, first.start())
        if assign is None:
            continue
        span = masked[close + 1 : second.start()]
        if not re.search(r"\b" + re.escape(assign.group(1)) + r"\b", span):
            continue
        if _AGGREGATION_MARKER.search(span):
            continue
        findings.append(
            Finding(
                path,
                _line_at(masked, second.start()),
                WARN,
                "prefer-pipeline",
                "two parallel() barriers separated only by a pure transform of "
                f"`{assign.group(1)}` (no cross-item aggregation between them). The "
                'runtime\'s own guidance is "DEFAULT TO pipeline()": a barrier is '
                "justified only by dedup/merge across the full set, an early exit on "
                "zero, or a stage that cites the other items. Otherwise the transform "
                "belongs inside a pipeline() stage and the barrier wait is pure "
                "latency.",
            )
        )


# --------------------------------------------------------------------------- #
# budget-loop-unguarded -- the runtime's own warning, quoted from the tool doc:
# "Guard on budget.total: with no target set, remaining() is Infinity and the
#  loop would run straight to the 1000-agent cap."
# --------------------------------------------------------------------------- #
_WHILE_CALL = re.compile(r"\bwhile\s*\(")
_BUDGET_REMAINING = re.compile(r"\bbudget\s*\.\s*remaining\s*\(")
_BUDGET_TOTAL = re.compile(r"\bbudget\s*\.\s*total\b")


def _check_budget_loop(masked: str, path: str, findings: list[Finding]) -> None:
    for m in _WHILE_CALL.finditer(masked):
        close = _match_bracket(masked, m.end() - 1)
        if close is None:
            continue
        cond = masked[m.end() : close]
        if not _BUDGET_REMAINING.search(cond):
            continue
        if _BUDGET_TOTAL.search(cond):
            continue
        findings.append(
            Finding(
                path,
                _line_at(masked, m.start()),
                WARN,
                "budget-loop-unguarded",
                "while (budget.remaining() ...) with no budget.total guard. When the "
                "user set no token target, budget.total is null and remaining() is "
                "Infinity, so this loop runs straight to the 1000-agent lifetime cap. "
                "Write `while (budget.total && budget.remaining() > 50_000)`.",
            )
        )


def lint_text(text: str, path: str = "<workflow>") -> list[Finding]:
    """Lint workflow source ``text``; return findings sorted by (line, check)."""
    masked = mask_code(text)
    findings: list[Finding] = []
    _check_meta(text, masked, path, findings)
    _check_banned(masked, path, findings)
    _check_sandbox(masked, path, findings)
    _check_args(masked, path, findings)
    _check_agent_schema(masked, path, findings)
    _check_parallel_filter(masked, path, findings)
    _check_barrier_timeout(masked, path, findings)
    _check_prefer_pipeline(masked, path, findings)
    _check_budget_loop(masked, path, findings)
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
