"""Classify a cited span by structural ROLE, not by substring presence.

USE: the speaker's own unquoted voice.
MENTION: the span sits inside quotation marks, a markdown blockquote, or a
fenced example. A document that describes a defect necessarily contains that
defect's text; wrapping is how this estate tells USE from MENTION.

The known-broken matcher is substring_classify: any found span is USE. That
is the trap this unit exists to catch.
"""
from __future__ import annotations

import re
from pathlib import Path


def read_lf(path: Path) -> str:
    """Read text with CRLF folded to LF so offsets match live probes."""
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")

TURN_RE = re.compile(r"^-----TURN\s+\d+\s+speaker=\w+-----\s*$", re.M)

CONTEXT_CHANGE_CUES = (
    "changes that meaning",
    "that is false",
    "it is not reliable",
    "this turn does not assert",
    "not asserted as our finding",
    "do not harvest as an assertion",
    "quoted, not asserted",
)


def _fence_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    i = 0
    while True:
        a = text.find("```", i)
        if a < 0:
            break
        b = text.find("```", a + 3)
        if b < 0:
            ranges.append((a, len(text)))
            break
        ranges.append((a, b + 3))
        i = b + 3
    return ranges


def _quote_ranges(text: str) -> list[tuple[int, int]]:
    """ASCII double-quoted spans. Quotes are wrappers, not the cited bytes."""
    ranges: list[tuple[int, int]] = []
    i = 0
    while True:
        a = text.find('"', i)
        if a < 0:
            break
        b = text.find('"', a + 1)
        if b < 0:
            break
        ranges.append((a + 1, b))
        i = b + 1
    return ranges


def _inside(ranges: list[tuple[int, int]], start: int, end: int) -> bool:
    for a, b in ranges:
        if a <= start and end <= b:
            return True
    return False


def _line_at(text: str, pos: int) -> str:
    a = text.rfind("\n", 0, pos) + 1
    b = text.find("\n", pos)
    if b < 0:
        b = len(text)
    return text[a:b]


def classify_role(
    text: str,
    start: int,
    end: int,
    *,
    ignore_wrappers: bool = False,
) -> str:
    """Return USE, MENTION, or ABSENT for text[start:end].

    ignore_wrappers=True is the known-broken mutant: any located span is USE.
    """
    if start < 0 or end > len(text) or start >= end:
        return "ABSENT"
    if ignore_wrappers:
        return "USE"
    if _inside(_fence_ranges(text), start, end):
        return "MENTION"
    line = _line_at(text, start)
    if line.lstrip().startswith(">"):
        return "MENTION"
    if _inside(_quote_ranges(text), start, end):
        return "MENTION"
    return "USE"


def substring_classify(text: str, span: str) -> str:
    """Known-broken detector: presence of the bytes is treated as an assertion."""
    if not span:
        return "ABSENT"
    return "USE" if span in text else "ABSENT"


def surrounding_turn(text: str, char_start: int) -> str:
    starts = list(TURN_RE.finditer(text))
    if not starts:
        return text.strip()
    chosen_i = 0
    for i, m in enumerate(starts):
        if m.start() <= char_start:
            chosen_i = i
        else:
            break
    begin = starts[chosen_i].start()
    end = starts[chosen_i + 1].start() if chosen_i + 1 < len(starts) else len(text)
    return text[begin:end].strip()


def context_changes_meaning(turn: str, start_in_file: int, end_in_file: int, file_text: str) -> bool:
    """True when the surrounding turn retracts or warns about the cited span.

    Cues inside the cited span itself do not count (that would be substring
    matching the claim). Cues must sit in the turn but outside the span.
    """
    turn_start = file_text.find(turn)
    if turn_start < 0:
        hay = turn.lower()
        rel_start, rel_end = 0, 0
    else:
        hay = file_text.lower()
        rel_start, rel_end = start_in_file, end_in_file
    low = hay
    for cue in CONTEXT_CHANGE_CUES:
        pos = 0
        cl = cue.lower()
        while True:
            j = low.find(cl, pos)
            if j < 0:
                break
            k = j + len(cl)
            if turn_start >= 0:
                in_turn = turn_start <= j and k <= turn_start + len(turn)
                in_span = rel_start <= j and k <= rel_end
                if in_turn and not in_span:
                    return True
            else:
                if not (rel_start <= j < rel_end):
                    return True
            pos = k
    return False
