#!/usr/bin/env python3
"""use_vs_mention.py — the shared use-vs-mention discriminator (D1b).

Three independent guards on this box fail the same way: they pattern-match the
PAYLOAD of a write instead of the SEMANTIC ROLE of the text. A document that
DESCRIBES a destructive command, a stub, or a marker is treated identically to
one that IS one, and negation is invisible to them. Rewording the patterns was
tried three times and the matcher followed every time — so the fix cannot live
in the pattern, it must live in the discriminator.

This module is that discriminator, implemented ONCE so every guard (including
guards not yet written) is correct by construction.

    from use_vs_mention import Context, is_real_occurrence, find_real

    ctx = Context(tool_name=data["tool_name"],
                  file_path=data["tool_input"].get("file_path", ""),
                  source="tool_input")
    hits = find_real(content, MY_PATTERN, ctx, kind="marker")

THREE RULES, matching the D1 fix direction:
  (a) `kind="command"` — a match counts only when the tool_use VERB is a shell
      that could execute it, and the match sits in command position rather than
      inside a quoted literal or here-string. Never the payload body.
  (b) `kind="marker"`  — in prose (a .md target or an assistant message) a match
      counts only inside a fenced code block; a paragraph, table cell,
      blockquote or inline `code span` is a MENTION. In a real source file a
      match counts unless the enclosing sentence negates it.
  (c) `kind="doclink"` — a markdown link `[label](target)`. THE POLARITY IS
      INVERTED relative to `marker`, and that inversion is the entire point: a
      link sitting in a PARAGRAPH is a real USE (the author asserts the target
      exists, so a missing target is genuine rot), while the SAME link inside a
      fenced block or an inline `code span` is syntax being DEMONSTRATED and must
      stay silent. Reusing `marker` here would invert every verdict — flagging
      every documentation example while ignoring every real broken link.
      No negation test: a link is structural rather than assertional, so the mood
      of the surrounding sentence carries no signal, and a cue-based test would
      misread the common "see [the old plan](x) — now removed" phrasing.
  (d) `kind="result"` — a TOOL RESULT payload. A match counts only when the payload
      REPORTS the condition; it is a MENTION when the payload merely CONTAINS the
      word — inside a field NAME, inside a CLOSED fenced example or an inline
      `code span` in a returned document, or in a negated sentence. Closes the
      corpus GAP recorded as RES-FP-fieldname / RES-TP-failvalue.

FAIL-OPEN BY DESIGN: any malformed input or internal error returns True
("treat as real"). A crashing or over-eager discriminator would silently disarm
a guard, which is strictly worse than the false positives it replaces.

Stdlib only. No I/O. Pure functions — safe to call from any hook event.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

__all__ = ["Context", "is_real_occurrence", "find_real"]

# Tools whose input is EXECUTED (a destructive token here can really run).
_SHELL_TOOLS = {
    "bash",
    "powershell",
    "shell",
    "sh",
    "zsh",
    "cmd",
    "terminal",
    "run_command",
}
# Tools whose input is DATA being written to disk (a destructive token is inert).
_DATA_TOOLS = {
    "write",
    "edit",
    "multiedit",
    "notebookedit",
    "apply_patch",
    "str_replace",
}

# Targets whose content is PROSE: only a fenced block counts as code.
_PROSE_EXT = {".md", ".markdown", ".txt", ".rst", ".adoc", ".org", ".mdx"}

_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[^\n]*$", re.MULTILINE)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_NEGATION = re.compile(
    r"\b(?:no|not|never|nothing|none|without|cannot|can't|won't|don't|doesn't|"
    r"isn't|aren't|nor|avoid|instead\s+of|rather\s+than|must\s+not|need\s+not)\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"[.!?](?:\s|$)|\n")


@dataclass(frozen=True)
class Context:
    """Where a candidate match came from.

    tool_name: the tool_use VERB (PreToolUse/PostToolUse payloads carry this
               separately from tool_input — verified against the CLI's own
               hook-input construction).
    file_path: tool_input.file_path — the write TARGET.
    source:    "tool_input" | "assistant_message" | "file".
    """

    tool_name: str = ""
    file_path: str = ""
    source: str = "file"


def _is_prose(ctx: Context) -> bool:
    if ctx.source == "assistant_message":
        return True
    return os.path.splitext(str(ctx.file_path or ""))[1].lower() in _PROSE_EXT


def _fenced_spans(text: str) -> list[tuple[int, int]]:
    """Content ranges of ``` / ~~~ fenced blocks (unclosed fence runs to EOF)."""
    spans, open_at = [], None
    for m in _FENCE.finditer(text):
        if open_at is None:
            open_at = m.end() + 1
        else:
            spans.append((open_at, m.start()))
            open_at = None
    if open_at is not None:
        spans.append((open_at, len(text)))
    return spans


def _quoted_spans(text: str) -> list[tuple[int, int]]:
    """Ranges inside shell quotes / PowerShell here-strings — i.e. inert DATA."""
    spans: list[tuple[int, int]] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        # PowerShell here-string: @' ... '@   /   @" ... "@
        if ch == "@" and i + 1 < n and text[i + 1] in "'\"":
            q = text[i + 1]
            close = text.find(q + "@", i + 2)
            end = n if close < 0 else close
            spans.append((i + 2, end))
            i = n if close < 0 else close + 2
            continue
        if ch in "'\"":
            j = i + 1
            while j < n and text[j] != ch:
                j += 2 if (ch == '"' and text[j] == "\\") else 1
            spans.append((i + 1, min(j, n)))
            i = j + 1
            continue
        i += 1
    return spans


def _within(spans, start: int, end: int) -> bool:
    return any(lo <= start and end <= hi for lo, hi in spans)


def _line_bounds(text: str, start: int) -> tuple[int, int]:
    lo = text.rfind("\n", 0, start) + 1
    hi = text.find("\n", start)
    return lo, (len(text) if hi < 0 else hi)


def _inline_code_spans(text: str, start: int) -> list[tuple[int, int]]:
    """Absolute ranges of `code spans` on the ONE line holding `start`.

    Scoped to a single line because an unbalanced backtick elsewhere in a long
    document would otherwise swallow half the file and silence real matches.
    """
    line_lo, line_hi = _line_bounds(text, start)
    line = text[line_lo:line_hi]
    return [
        (line_lo + m.start(), line_lo + m.end()) for m in _INLINE_CODE.finditer(line)
    ]


def _is_negated(text: str, start: int) -> bool:
    """True when the sentence up to the match carries a negation cue."""
    lo = 0
    for m in _SENTENCE_END.finditer(text, 0, start):
        lo = m.end()
    return bool(_NEGATION.search(text[lo:start]))


# ---------------------------------------------------------------- kind="stub" support
# A code-comment opener. `#(?!\d)` so a GitHub issue reference (`#1785`) is not read as a
# comment intro -- the same narrowing stubscan.py already carries, for the same measured reason.
_CODE_COMMENT_INTRO = re.compile(r"(?:#(?!\d)|//|/\*|<!--)")
# A markdown table row cell: the match sits BETWEEN two pipes on its own line. Kept separate
# from "the line starts with |" because the measured fire
# (INPUT-ADDENDUM-live-fires.md:82) is a labelled listing --
# `R14  markdown table cell:      | prompts/list_changed | Not implemented ... |` -- whose line
# begins with prose, not a pipe.
_STRIKE = re.compile(r"~~[^\n]+?~~")


def _in_table_cell(text: str, start: int, end: int) -> bool:
    lo, hi = _line_bounds(text, start)
    line = text[lo:hi]
    return "|" in line[: start - lo] and "|" in line[end - lo :]


def _in_blockquote(text: str, start: int) -> bool:
    lo, hi = _line_bounds(text, start)
    return text[lo:hi].lstrip().startswith(">")


def _strike_spans(text: str, start: int) -> list[tuple[int, int]]:
    lo, hi = _line_bounds(text, start)
    return [(lo + m.start(), lo + m.end()) for m in _STRIKE.finditer(text[lo:hi])]


def _stub_negation_window(text: str, start: int) -> int:
    """Offset from which to scan for a negation cue, for `kind="stub"`.

    Negation is a property of PROSE. Scanning back to the sentence start drags the CODE that
    precedes an end-of-line comment into the window, and Python's `None` literal then reads as
    the English quantifier "none". Measured 2026-07-24: the line
    `cert = None  # placeholder PEM until the loader lands` was scored NEGATED and silently
    dropped -- a real placeholder the guard is supposed to catch. Clamping the window to the
    comment body removes the code from view.

    (Both quotes above are kept on ONE line each: `_inline_code_spans` is deliberately
    line-scoped, so a backticked marker WRAPPED across two lines is not recognised as a code
    span and this very docstring would flag itself. That wrapped-span gap is real but out of
    scope here; the settling experiment is a two-line comment-continuation span test.)
    """
    lo = 0
    for m in _SENTENCE_END.finditer(text, 0, start):
        lo = m.end()
    line_lo, _ = _line_bounds(text, start)
    for m in _CODE_COMMENT_INTRO.finditer(text[line_lo:start]):
        lo = max(lo, line_lo + m.end())
    return lo


# ------------------------------------------------------ kind="result" support
# Characters legal in a bare JSON/YAML field name. A match containing anything else
# (a space, a colon) cannot BE a field name, which is what makes the early-out below
# safe: `timedout` could be a key, `timed out` is a phrase.
_KEY_CHAR = re.compile(r"[A-Za-z0-9_.$-]")
# `[ \t]*` not `\s*`: a formatter emits `"key" : v` on ONE line. Allowing a newline
# would let a quoted token be adopted as the key of a colon on the following line.
# Pinned by test_a_NEWLINE_between_the_token_and_the_colon_is_NOT_a_key -- a `\s*`
# relaxation SURVIVED an independent mutation harness while this was comment-only.
_KEY_COLON = re.compile(r"^[ \t]*:")
# Negation is a property of a clause. A serialized payload has few sentence
# terminators, so an unclamped window can reach kilobytes back and let an unrelated
# "no"/"not" silence a genuine failure report. Clamping can only make the guard fire
# MORE, never less, which is the safe direction for a detector.
_RESULT_NEG_LOOKBACK = 200


def _in_json_key(text: str, start: int, end: int) -> bool:
    """True when the match sits inside a QUOTED JSON/YAML field NAME.

    A field NAME mentions a condition; it never reports one. `json_value_text()`
    already enforces that STRUCTURALLY by dropping keys, but only while the whole
    payload parses. Two measured roads around it, both landing here:
      * the caller's scan-surface cap truncates a real payload mid-document, so it
        stops parsing and every key returns to the raw scan surface. Measured
        2026-07-24: a 14,060-char `dbx_run_get` body clipped to the sentinel's
        8,000-char cap, after which `"user_cancelled_or_timedout": false` matched
        /tim(ed|e)-?out/ on a RUNNING job -- the SAME defect the structural rule was
        written to kill, reached by a different road.
      * a JSON/YAML document embedded inside a returned STRING value (a fetched
        config file) is never parsed as JSON at all. Measured 2026-07-24: a github
        `get_file_contents` call that returned a valid blob sha plus full markdown
        was flagged `timeout` because the DOCUMENT contained `"timeout": 100000`.

    QUOTED keys only, deliberately. An unquoted `word:` rule would also match the
    common `Timeout: <cause>` error-message shape and silence a genuine report.
    Residual, disclosed INLINE: a bare YAML key (`timeout: 30`) in a result body is
    therefore still scanned; the settling experiment is a labelled sweep of fires on
    YAML-returning tools.
    """
    if start >= end or any(not _KEY_CHAR.match(c) for c in text[start:end]):
        return False  # a multi-word phrase is not a bare field name
    lo = start
    while lo > 0 and _KEY_CHAR.match(text[lo - 1]):
        lo -= 1
    if lo == 0 or text[lo - 1] not in "\"'":
        return False
    hi = end
    while hi < len(text) and _KEY_CHAR.match(text[hi]):
        hi += 1
    tail = text[hi:]
    if not tail or tail[0] != text[lo - 1]:
        # Unterminated, or the quote style does not match the opener. Pinned in BOTH
        # pair directions by test_a_MISMATCHED_quote_pair_is_NOT_a_key -- dropping the
        # match requirement SURVIVED an independent mutation harness before that test.
        return False
    rest = tail[1:]
    # `not rest` = the payload was truncated EXACTLY at the key's closing quote. A key
    # that lost its colon to truncation is still a key. Deliberately tight: any
    # trailing character other than the colon means this is a VALUE, not a key.
    #
    # RESIDUAL FALSE NEGATIVE, disclosed: at that ONE byte a truncated real VALUE is
    # indistinguishable from a truncated key, so this arm silences it too. Measured
    # 2026-07-25:
    #   [SILENT] '{"data": {"user_cancelled_or_timedout"'   <- a key, correct
    #   [SILENT] '{"error": "ETIMEDOUT"'                    <- a real VALUE, silenced
    #   [FIRE  ] '{"error": "ETIMEDOUT'    truncated ONE byte earlier
    #   [FIRE  ] '{"error": "ETIMEDOUT"}'  complete
    # The payload itself lost the disambiguator, so this is a CHOSEN DIRECTION, not an
    # oracle: chosen toward the mention (FP-averse), and narrow because the caller's
    # size cap has to land on exactly that byte. No probe can settle it from the
    # truncated surface -- raising the caller's cap is what removes the case.
    return not rest or bool(_KEY_COLON.match(rest))


def _closed_fenced_spans(text: str) -> list[tuple[int, int]]:
    """Content ranges of CLOSED ``` / ~~~ fenced blocks ONLY.

    Unlike `_fenced_spans`, an UNCLOSED fence is ignored rather than run to EOF. A
    result payload is routinely truncated by the caller's size cap, which leaves a
    dangling fence; treating that as a span to EOF would silence every real error
    after it -- the same "an unbalanced delimiter swallows the rest of the document"
    hazard `_inline_code_spans` is line-scoped to avoid.
    """
    spans: list[tuple[int, int]] = []
    open_at = None
    for m in _FENCE.finditer(text):
        if open_at is None:
            open_at = m.end() + 1
        else:
            spans.append((open_at, m.start()))
            open_at = None
    return spans


def _result_negation_window(text: str, start: int) -> int:
    """Offset from which to scan for a negation cue, for `kind="result"`."""
    lo = 0
    for m in _SENTENCE_END.finditer(text, max(0, start - 4000), start):
        lo = m.end()
    return max(lo, start - _RESULT_NEG_LOOKBACK, 0)


def is_real_occurrence(text: str, span, context: Context, kind: str = "marker") -> bool:
    """True if the match at `span` is a real OCCURRENCE, False if a MENTION.

    Fail-open: returns True on any malformed input or internal error.
    """
    try:
        start, end = int(span[0]), int(span[1])
        if not text or not (0 <= start < end <= len(text)):
            return True  # fail-open: cannot judge -> treat as real

        if kind == "command":
            tool = str(context.tool_name or "").strip().lower()
            if tool in _DATA_TOOLS:
                return False  # the verb writes a file; the body cannot execute
            if tool and tool not in _SHELL_TOOLS:
                return True  # unknown verb -> fail-open
            return not _within(_quoted_spans(text), start, end)

        if kind == "result":
            # A TOOL RESULT is judged on whether the payload REPORTS the condition or
            # merely CONTAINS the word. Every mention form below is a MEASURED fire:
            #   a field NAME  -> `"user_cancelled_or_timedout": false` on a live job;
            #   a config key inside a FETCHED document -> `"timeout": 100000`;
            #   a CLOSED fenced console transcript in a fetched runbook;
            #   an inline `code span`, and a negated sentence.
            # NOT routed through `marker`: marker polarity requires a match to sit
            # INSIDE a fence to count, which is exactly backwards for a result -- a
            # genuine transport error is USUALLY unfenced prose (usually, not always;
            # see the residual on the closed-fence rule below). Measured: forcing
            # prose-marker mode silenced ALL FOUR positive controls plus the existing
            # suite's "could not connect" case, trading false alarms for blindness.
            if _in_json_key(text, start, end):
                return False
            # RESIDUAL FALSE NEGATIVE, disclosed. The line above once asserted as FACT
            # that a genuine transport error is unfenced prose; that was an ASSUMPTION
            # with no measurement behind it, and this rule is what it justified. A
            # server that formats its OWN error text inside a CLOSED fence is now
            # silent on this lexical path. Measured BOTH states 2026-07-25:
            #   "Tool failed:\n```\nMCP error -32000: server is not responding\n```"
            #     -> FAILED on origin/main, SUCCESS here;
            #   the same text UNFENCED -> FAILED on both.
            # Bounded, and measured so: an MCP failure normally arrives in an envelope
            # that stage 1 catches before this function is reached (fenced +
            # isError:true -> `isError=true`; fenced + an `error` field -> `error field
            # set`). How often a server fences its own error body is UNVERIFIED
            # (uncertain 30-55%) -- settling experiment is a sweep of recorded MCP
            # failure bodies for fenced error text.
            if _within(_closed_fenced_spans(text), start, end):
                return False
            if _within(_inline_code_spans(text, start), start, end):
                return False
            return not _NEGATION.search(
                text[_result_negation_window(text, start) : start]
            )

        if kind in ("doclink", "claim"):
            # Inverted polarity (see the module docstring): a link is real UNLESS it
            # is being shown as an example. Applies in prose and in source files
            # alike -- a link inside a fence in a .py docstring is still an example.
            #
            # "claim" shares this polarity and is NOT a marker. A completion claim
            # ("the feature is now complete") is REAL precisely when it appears in
            # ordinary prose -- that is what an assistant asserting completion looks
            # like. It is a MENTION when quoted or fenced, i.e. when the text is
            # discussing the phrase rather than asserting it. Routing a claim through
            # kind="marker" inverts this and suppresses every genuine claim, because
            # marker polarity treats prose as mention.
            if _within(_fenced_spans(text), start, end):
                return False
            return not _within(_inline_code_spans(text, start), start, end)

        if kind == "stub":
            # STRICTER THAN "marker", and deliberately so. The stub-ledger's contract is
            # "built-but-incomplete CODE must not be silently forgotten" -- so the evidence bar
            # is a marker in CODE, not a marker anywhere.
            #
            # (1) A PROSE document is documentation. `marker` treats a fenced block in a .md as
            #     real code being shown; 12 of 20 live false positives measured 2026-07-24 were
            #     exactly that -- a fenced corpus listing in INPUT-ADDENDUM-live-fires.md:81-95
            #     enumerating detector inputs, one row of which reads literally
            #     `# TODO: handle the empty-list case`.
            #     Nothing structural separates that row from a real one,
            #     so the earlier "a fenced block in a doc is code being shown" assertion is
            #     REFUTED and inverted here. Residual, disclosed: a design doc whose fenced
            #     snippet really is pending work is now missed; the settling experiment is a
            #     labelled sweep of prose-origin fires across sessions, which so far shows
            #     0 true positives out of 12.
            # (2) A markdown TABLE CELL, a BLOCKQUOTE and STRUCK-THROUGH text are mentions even
            #     inside a source file -- a docstring can hold a compliance table about another
            #     product's gaps, and `~~...~~` marks an ABANDONED idea, not pending work.
            if _is_prose(context):
                return False
            if _within(_inline_code_spans(text, start), start, end):
                return False
            if (
                _in_table_cell(text, start, end)
                or _in_blockquote(text, start)
                or _within(_strike_spans(text, start), start, end)
            ):
                return False
            return not _NEGATION.search(
                text[_stub_negation_window(text, start) : start]
            )

        # kind == "marker"
        if _is_prose(context):
            if not _within(_fenced_spans(text), start, end):
                return False  # paragraph / table cell / blockquote / inline span
            return not _is_negated(text, start)

        if _within(_inline_code_spans(text, start), start, end):
            return False  # named in backticks even inside a source file
        return not _is_negated(text, start)
    except Exception:
        return True  # fail-open: never silently disarm a guard


def json_value_text(text: str, _depth: int = 0):
    """The RESULT-SCANNER half of the rule: a JSON payload's string VALUES only.

    A JSON *field name* MENTIONS a condition; it never reports one. Scanning a
    serialized payload as flat text conflates the two.

    Measured 2026-07-20: a Databricks run payload carrying
    ``"user_cancelled_or_timedout": false`` -- a field whose value is False, on a job
    that was RUNNING and later TERMINATED SUCCESS -- was classified FAILED because the
    KEY matched /tim(ed|e)-?out/. Seven false fires in one session, including one on the
    memory note documenting this very defect (the guard suppresses its own bug report).

    Returns None when `text` is not JSON, so the caller falls back to raw text and a
    non-JSON payload keeps its previous behaviour. Nested JSON-in-string values are
    parsed recursively: MCP results routinely wrap a JSON document inside a string field,
    which is exactly how the key leaked into the scan surface.
    """
    import json as _json

    stripped = (text or "").strip()
    if not stripped or stripped[0] not in "{[":
        return None
    try:
        doc = _json.loads(stripped)
    except (ValueError, TypeError):
        return None

    out: list[str] = []

    def _walk(node, depth: int = 0) -> None:
        if depth > 8 or len(out) > 400:
            return
        if isinstance(node, str):
            nested = json_value_text(node, _depth + 1) if _depth < 3 else None
            out.append(node if nested is None else nested)
        elif isinstance(node, dict):
            for value in node.values():  # VALUES only -- keys are mentions
                _walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node:
                _walk(value, depth + 1)
        # numbers / booleans / null carry no scannable text at all

    _walk(doc)
    return "\n".join(out)


def find_real(text: str, pattern, context: Context, kind: str = "marker") -> list:
    """Every match of `pattern` in `text` that is a real occurrence, in order."""
    try:
        if not text:
            return []
        return [
            m
            for m in pattern.finditer(text)
            if is_real_occurrence(text, m.span(), context, kind=kind)
        ]
    except Exception:
        try:
            return list(pattern.finditer(text or ""))  # fail-open: keep everything
        except Exception:
            return []
