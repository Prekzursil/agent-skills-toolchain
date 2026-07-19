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

TWO RULES, matching the D1 fix direction:
  (a) `kind="command"` — a match counts only when the tool_use VERB is a shell
      that could execute it, and the match sits in command position rather than
      inside a quoted literal or here-string. Never the payload body.
  (b) `kind="marker"`  — in prose (a .md target or an assistant message) a match
      counts only inside a fenced code block; a paragraph, table cell,
      blockquote or inline `code span` is a MENTION. In a real source file a
      match counts unless the enclosing sentence negates it.

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


def _is_negated(text: str, start: int) -> bool:
    """True when the sentence up to the match carries a negation cue."""
    lo = 0
    for m in _SENTENCE_END.finditer(text, 0, start):
        lo = m.end()
    return bool(_NEGATION.search(text[lo:start]))


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

        # kind == "marker"
        if _is_prose(context):
            if not _within(_fenced_spans(text), start, end):
                return False  # paragraph / table cell / blockquote / inline span
            return not _is_negated(text, start)

        line_lo, line_hi = _line_bounds(text, start)
        line = text[line_lo:line_hi]
        if _within(
            [
                (line_lo + m.start(), line_lo + m.end())
                for m in _INLINE_CODE.finditer(line)
            ],
            start,
            end,
        ):
            return False  # named in backticks even inside a source file
        return not _is_negated(text, start)
    except Exception:
        return True  # fail-open: never silently disarm a guard


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
