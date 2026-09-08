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
  (e) `kind="secret"` / `kind="pathword"` — the AUDIT-SUBJECT ALLOWLIST, the fourth
      rule of the original design and the last one to be built. A file whose JOB is
      to test or to guard a thing legitimately carries that thing's shape: a fixture
      holds secret-shaped literals, and a hook named `deny-credential-reads` holds
      the word `credential` in its own path. Both are MENTIONS. Closes the corpus
      GAPs recorded as SEC-FP-faketoken / SEC-FP-declared / PATH-FP-guardfile.
  (f) THE RECURSION TERMINATOR (`stub` + `marker`) — a marker spelled inside a
      STRING LITERAL is data, not pending work. Measured live 2026-08-08: a script
      that ENUMERATES the needles it wants deferred necessarily CONTAINS them, so
      per-needle deferral produced 13 NEW fires and a script deferring THOSE would
      produce more. Only a rule about ROLE terminates it, and this one does so
      structurally at depth 1. See `_string_literal_spans` for why `ast` and not
      the quote scanner.

FAIL-OPEN BY DESIGN: any malformed input or internal error yields UNKNOWN, and
`is_real_occurrence` maps UNKNOWN to True ("treat as real"). A crashing or
over-eager discriminator would silently disarm a guard, which is strictly worse
than the false positives it replaces.

TYPED VERDICT (P2-01). `classify()` is the primary API and returns a `Judgement`
carrying one of three verdicts — USE / MENTION / UNKNOWN. The third is the point:
a detector that cannot tell must be able to SAY so and surface, rather than
silently picking a side. That is the closing principle of the design note this
module implements: *"When a detector cannot distinguish use from mention, it must
surface, not block."* A bare bool cannot express it, so a bare bool was the wrong
return type. `is_real_occurrence` is retained as a thin bool wrapper so every
existing caller keeps its exact prior behaviour (UNKNOWN -> True).

Stdlib only. No I/O. Pure functions — safe to call from any hook event.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

__all__ = [
    "Context",
    "Judgement",
    "Verdict",
    "audit_subject_rule",
    "classify",
    "is_real_occurrence",
    "find_real",
]

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
    r"\b(?:no|not|never|nothing|none|zero|without|cannot|can't|won't|don't|doesn't|"
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
    source:    "tool_input" | "assistant_message" | "message_text" | "file".
               `message_text` is an alias of `assistant_message` (assistant final
               prose that is not a tool_input write). Recorded as STUB-FP-negated-
               absence in use-vs-mention-corpus.jsonl: a sentence asserting the
               ABSENCE of TODO/FIXME was flagged because the source was recorded
               as `message_text` and the prose rule only recognized
               `assistant_message`.
    """

    tool_name: str = ""
    file_path: str = ""
    source: str = "file"


class Verdict(str, Enum):
    """The three answers a use-vs-mention judge can honestly give (P2-01).

    USE      the match is a real occurrence -- the guard may act on it.
    MENTION  the text talks ABOUT the thing -- the guard must stay silent.
    UNKNOWN  the judge could not tell. NOT a synonym for either other value: it is
             the state a caller is expected to SURFACE (emit NOT-CHECKED, log,
             degrade to advisory) rather than resolve by guessing. Every caller
             that maps UNKNOWN onto an action must map it to the FAIL-OPEN side,
             because a missed hard-ban action is worse than a false alarm.

    `str` mixin so an UNKNOWN can be written straight into a JSON receipt.
    """

    USE = "USE"
    MENTION = "MENTION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Judgement:
    """A typed verdict plus the identity of the rule that produced it.

    `rule` is what makes a verdict auditable after the fact -- "MENTION" alone does
    not tell a reader whether the text was fenced, negated, or sitting in a fixture,
    and those are very different reasons to have stayed silent.
    """

    verdict: Verdict
    rule: str = ""
    kind: str = ""

    @property
    def is_real(self) -> bool:
        """Fail-open projection onto a bool: UNKNOWN counts as real."""
        return self.verdict is not Verdict.MENTION

    def __bool__(self) -> bool:  # so `if classify(...)` reads naturally
        return self.is_real


def _use(rule: str, kind: str) -> Judgement:
    return Judgement(Verdict.USE, rule, kind)


def _mention(rule: str, kind: str) -> Judgement:
    return Judgement(Verdict.MENTION, rule, kind)


def _unknown(rule: str, kind: str) -> Judgement:
    return Judgement(Verdict.UNKNOWN, rule, kind)


_PROSE_SOURCES = frozenset({"assistant_message", "message_text"})


def _is_prose(ctx: Context) -> bool:
    if ctx.source in _PROSE_SOURCES:
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


# ------------------------------------- kind="secret" / kind="pathword" support
# THE AUDIT-SUBJECT ALLOWLIST -- design rule 4, and the only one of the original four
# that was never built. Measured 2026-08-07: with no implementation, `kind="secret"` and
# `kind="pathword"` fell THROUGH to the marker branch and silently inherited marker
# semantics, which is why SEC-FP-faketoken, SEC-FP-declared and PATH-FP-guardfile were the
# three corpus cases still failing against the live module.
#
# The principle: a file whose JOB is to test or to guard a thing legitimately carries that
# thing's shape. A fixture holds secret-shaped literals BECAUSE it proves the redactor
# works; a hook directory named `deny-credential-reads` holds the word `credential`
# BECAUSE that is what it denies. Flagging either is the guard reading a NAME as a VALUE.
_TEST_SEGMENT = re.compile(
    r"^(?:tests?|testing|__tests__|spec|specs|fixtures?|testdata|test-data|mocks?|"
    r"stubs?|examples?|samples?|corpus|FAILURE-REPLAY-CORPUS)$",
    re.IGNORECASE,
)
_TEST_BASENAME = re.compile(
    r"^(?:test[_-].+|.+[_-]test|.+\.test|.+\.spec|conftest|.+_fixtures?)\.[A-Za-z0-9]+$",
    re.IGNORECASE,
)
# A path segment that names a DETECTOR rather than the thing detected. Anchored to a
# leading verb + hyphen so it cannot swallow an ordinary directory: `deny-credential-reads`
# matches, `credentials` does not, and neither does `no_sql` (hyphen required).
_GUARD_SEGMENT = re.compile(
    r"^(?:deny|allow|block|check|guard|scan|scanner|detect|detector|redact|reject|"
    r"forbid|no|anti)-",
    re.IGNORECASE,
)
# DELIBERATELY ABSENT: a "the material declares itself fake" heuristic.
#
# One was written here first (matching `fake` / `EXAMPLE` / a zero-run inside the literal,
# plus a `# synthetic, non-functional` comment above it) and then REMOVED, because a
# mutation test refuted it. Neutering it left the corpus fully GREEN at 35/35: every
# recorded secret fire on this box -- the 5 bundle-verifier fixtures and the two SEC-FP
# corpus rows -- is already silenced by the audit-subject PATH rule, so the heuristic
# decided nothing that the path did not already decide.
#
# Unpinned code on a security-relevant judge is not free. The rule is SUBTRACTIVE and
# trivially spoofable: a genuinely leaked key with `# synthetic, for tests` written above
# it would have been silenced at a production path. Keeping it would have meant either
# shipping untested subtraction or inventing a corpus case to justify code that no
# measured fire needs. Both are worse than deleting it.
#
# If a real fire ever appears that ONLY a fake-declaration rule can silence -- a fixture
# literal at a non-test, non-guard path -- that fire is the evidence to add it back, and
# it must arrive with a case that goes red without it.


def _path_segments(path: str) -> list[str]:
    return [seg for seg in re.split(r"[\\/]+", str(path or "")) if seg]


def _is_audit_subject_path(path: str) -> str:
    """Name the audit-subject rule matching `path`, or "" when none does.

    Returns the RULE NAME rather than a bool so the Judgement can say WHY it stayed
    silent -- "this is a fixture" and "this is a guard's own source" are different
    exemptions and a reader auditing a silence needs to tell them apart.
    """
    segments = _path_segments(path)
    if not segments:
        return ""
    for seg in segments[:-1]:
        if _TEST_SEGMENT.match(seg):
            return "audit-subject:test-dir"
    basename = segments[-1]
    if _TEST_SEGMENT.match(basename) or _TEST_BASENAME.match(basename):
        return "audit-subject:test-file"
    for seg in segments[:-1]:
        if _GUARD_SEGMENT.match(seg):
            return "audit-subject:guard-dir"
    return ""


# ------------------------------- a marker inside a STRING LITERAL is data, not a marker
# THE RECURSION TERMINATOR. Measured live 2026-08-08: `_defer_stub_fixtures.py` -- a one-shot
# script whose only job is to list the needles that should stop firing -- produced 13 NEW stub
# fires, because a file that ENUMERATES needles necessarily CONTAINS them. Deferring those would
# produce a third file containing them again. Per-needle deferral cannot terminate; only a rule
# about ROLE can.
#
# The role distinction is exact: `raise NotImplementedError` is a raise, `# TODO: x` is a comment,
# but `"_stubscan_proof.py::# todo: wire this up"` is a STRING whose CONTENTS happen to spell a
# comment. Data, not pending work.
#
# Implemented with `ast`, NOT with the quote-scanner `_quoted_spans` used by kind="command".
# That was tried first and REFUTED by measurement: `_quoted_spans` is apostrophe-naive, so one
# unbalanced `'` swallows the rest of the file, and it blinded ALL FIVE genuine
# `raise NotImplementedError` sites in `fb-messenger-mcp/fbmcp/dm_e2ee.py:155-167`. A rule that
# silences real pending work to silence a fixture is the failure mode, not the fix.
#
# FAIL-OPEN in three ways, each deliberate: a non-Python path, a file that does not parse, and an
# oversized file all yield NO spans and therefore NO filtering. The rule can only ever REMOVE a
# false positive from a file whose structure it fully understands.
_PY_EXT = {".py", ".pyi"}
# Above this, skip parsing rather than pay for it in a per-keystroke hook. A file this large is
# vanishingly unlikely to be a needle-enumerating script.
_AST_MAX_BYTES = 400_000


def _line_start_offsets(text: str) -> list[int]:
    offsets, pos = [0], 0
    for line in text.splitlines(keepends=True):
        pos += len(line)
        offsets.append(pos)
    return offsets


@lru_cache(maxsize=16)
def _string_literal_spans(text: str, file_path: str) -> tuple[tuple[int, int], ...]:
    """Exact absolute spans of every str/bytes literal in `text`, or () when not judgeable.

    Cached because `find_real` judges one match at a time and would otherwise re-parse the
    whole file per match.
    """
    if os.path.splitext(str(file_path or ""))[1].lower() not in _PY_EXT:
        return ()
    if not text or len(text) > _AST_MAX_BYTES:
        return ()
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return ()  # a fragment or broken source -> judge nothing
    starts = _line_start_offsets(text)
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes))
        ):
            continue
        if node.end_lineno is None:
            continue
        try:
            lo = starts[node.lineno - 1] + node.col_offset
            hi = starts[node.end_lineno - 1] + node.end_col_offset
        except IndexError:
            continue
        if 0 <= lo < hi <= len(text):
            spans.append((lo, hi))
    return tuple(spans)


def _in_string_literal(text: str, start: int, end: int, ctx: Context) -> bool:
    try:
        return _within(
            _string_literal_spans(text, str(ctx.file_path or "")), start, end
        )
    except Exception:
        return False  # fail-open: never silence on an internal error


def audit_subject_rule(path: str) -> str:
    """PUBLIC: name the audit-subject exemption matching `path`, or "" when none does.

    Exported so a guard that needs design rule 4 outside `classify()` calls the ONE
    implementation instead of growing a fifth private copy -- the whole point of a
    shared discriminator.

    NOT a drop-in for `stubscan.py`'s own `_TEST_FILE` (`stubscan.py:264-275`), which
    is applied caller-side and already covers the stub scanner correctly. The two sets
    DIVERGE and that is deliberate, not drift: stubscan additionally exempts
    `scratchpad/` and `stub-ledger/`, which are specific to that guard, while this one
    additionally covers spec/testdata/mocks/examples/samples and guard-named directories.
    Unifying them would mean editing a live, working guard for no measured defect, so it
    is deliberately NOT done here.
    """
    return _is_audit_subject_path(path)


def _result_negation_window(text: str, start: int) -> int:
    """Offset from which to scan for a negation cue, for `kind="result"`."""
    lo = 0
    for m in _SENTENCE_END.finditer(text, max(0, start - 4000), start):
        lo = m.end()
    return max(lo, start - _RESULT_NEG_LOOKBACK, 0)


_KNOWN_KINDS = frozenset(
    {"command", "result", "doclink", "claim", "stub", "secret", "pathword", "marker"}
)


def classify(text: str, span, context: Context, kind: str = "marker") -> Judgement:
    """Judge the match at `span`: USE, MENTION, or UNKNOWN (P2-01 typed verdict).

    This is the primary API. `is_real_occurrence` is the bool projection of it.
    Fail-open: any malformed input, unrecognised kind, or internal error yields
    UNKNOWN, which `.is_real` reports as True so no guard is ever silently disarmed.
    """
    try:
        start, end = int(span[0]), int(span[1])
        if not text or not (0 <= start < end <= len(text)):
            return _unknown("bad-span", kind)  # cannot judge -> surface
        if kind not in _KNOWN_KINDS:
            # An unrecognised kind used to fall THROUGH to the marker branch and get
            # marker semantics in silence -- which could return MENTION and disarm a
            # guard that had merely misspelled its kind. Surfacing UNKNOWN instead can
            # only make a caller fire MORE, never less: the safe direction.
            return _unknown("unknown-kind", kind)

        if kind == "command":
            tool = str(context.tool_name or "").strip().lower()
            if tool in _DATA_TOOLS:
                # the verb writes a file; the body cannot execute
                return _mention("command:data-tool-verb", kind)
            if tool and tool not in _SHELL_TOOLS:
                return _unknown("command:unrecognised-verb", kind)
            if _within(_quoted_spans(text), start, end):
                return _mention("command:quoted-literal", kind)
            return _use("command:executable-position", kind)

        if kind == "secret":
            # A secret-SHAPED literal in a file whose job is to test or guard secrets is
            # a fixture, not a leak. Two independent exemptions, either sufficient:
            # the audit-subject PATH, and material that declares its own fakeness.
            #
            # NOT WIRED TO ANY LIVE BLOCKING GUARD -- deliberately. This kind adds a
            # capability; adopting it anywhere that currently BLOCKS would subtract
            # restriction from a security guard, which is out of scope by owner
            # constraint. (Both live secret paths -- `contains_secret` and
            # `_CREDENTIAL_READ` in the harness SecretGuardModule -- are opt-in and OFF
            # by default, so nothing today is weakened or strengthened by its presence.)
            rule = _is_audit_subject_path(context.file_path)
            if rule:
                return _mention(rule, kind)
            if _within(_inline_code_spans(text, start), start, end) and _is_prose(
                context
            ):
                return _mention("secret:prose-code-span", kind)
            return _use("secret:live-shaped-literal", kind)

        if kind == "pathword":
            # The TEXT here IS a path, and the question is whether the matched word
            # describes the file's SUBJECT or its own NAME. `deny-credential-reads/deny.py`
            # contains `credential` because it denies credential reads -- the guard is
            # reading its own name as its own violation.
            rule = _is_audit_subject_path(text)
            if rule:
                return _mention(rule, kind)
            segments = _path_segments(text)
            # Locate the segment holding the match by walking the same separators.
            offset, holder = 0, ""
            for seg in segments:
                idx = text.find(seg, offset)
                if idx < 0:
                    break
                if idx <= start and end <= idx + len(seg):
                    holder = seg
                    break
                offset = idx + len(seg)
            if holder and _GUARD_SEGMENT.match(holder):
                return _mention("pathword:guard-named-segment", kind)
            return _use("pathword:subject-path", kind)

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
                return _mention("result:json-field-name", kind)
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
                return _mention("result:closed-fence", kind)
            if _within(_inline_code_spans(text, start), start, end):
                return _mention("result:inline-code-span", kind)
            if _NEGATION.search(text[_result_negation_window(text, start) : start]):
                return _mention("result:negated", kind)
            return _use("result:reported-value", kind)

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
                return _mention("doclink:fenced-example", kind)
            if _within(_inline_code_spans(text, start), start, end):
                return _mention("doclink:inline-code-span", kind)
            return _use("doclink:asserted-in-prose", kind)

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
                return _mention("stub:prose-document", kind)
            if _in_string_literal(text, start, end, context):
                return _mention("stub:string-literal", kind)
            if _within(_inline_code_spans(text, start), start, end):
                return _mention("stub:inline-code-span", kind)
            if _in_table_cell(text, start, end):
                return _mention("stub:table-cell", kind)
            if _in_blockquote(text, start):
                return _mention("stub:blockquote", kind)
            if _within(_strike_spans(text, start), start, end):
                return _mention("stub:struck-through", kind)
            if _NEGATION.search(text[_stub_negation_window(text, start) : start]):
                return _mention("stub:negated", kind)
            return _use("stub:pending-work-in-code", kind)

        # kind == "marker"
        if _is_prose(context):
            if not _within(_fenced_spans(text), start, end):
                # paragraph / table cell / blockquote / inline span
                return _mention("marker:unfenced-prose", kind)
            if _is_negated(text, start):
                return _mention("marker:negated", kind)
            return _use("marker:fenced-code-in-prose", kind)

        if _in_string_literal(text, start, end, context):
            # a marker spelled inside a string literal is data, not pending work
            return _mention("marker:string-literal", kind)
        if _within(_inline_code_spans(text, start), start, end):
            # named in backticks even inside a source file
            return _mention("marker:inline-code-span", kind)
        if _is_negated(text, start):
            return _mention("marker:negated", kind)
        return _use("marker:source-file", kind)
    except Exception:
        # fail-open: never silently disarm a guard. UNKNOWN, not USE, so a caller that
        # keeps receipts can tell a judged verdict apart from a crash.
        return _unknown("internal-error", kind)


def is_real_occurrence(text: str, span, context: Context, kind: str = "marker") -> bool:
    """True if the match at `span` is a real OCCURRENCE, False if a MENTION.

    The bool projection of `classify()`, kept as the stable API for the four guards
    already wired to it. UNKNOWN projects to True, preserving fail-open exactly.
    Prefer `classify()` in new callers: it can report "I could not tell", which this
    signature structurally cannot.
    """
    return classify(text, span, context, kind=kind).is_real


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
