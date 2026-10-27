"""Digest-boundary loss accounting (SYN-0013).

Counts USES of loss-prone reference classes (UNVERIFIED tags, file:line
anchors, URLs) separately from MENTIONS (the same token inside double quotes —
vocabulary, not a live reference), publishes retention PER CLASS (a blended
rate hides a class that was dropped entirely), and gates synthesis candidates
on a surviving EVIDENCE block whose anchors are exempt from word caps.
"""
from __future__ import annotations

import re
from typing import Any

CLASSES = ("UNVERIFIED", "file_line", "URL")

_PATTERNS = {
    "UNVERIFIED": re.compile(r"UNVERIFIED"),
    "file_line": re.compile(r"[\w./-]+\.(?:py|json|md|txt|sh|mjs)\:\d+"),
    "URL": re.compile(r"https?://[^\s\"'\)\]]+"),
}

EVIDENCE_HEADER = re.compile(r"^##\s*EVIDENCE\s*$", re.MULTILINE)
MIN_ANCHORS = 3
MAX_ANCHORS = 5


def _is_mention(text: str, start: int, end: int) -> bool:
    return start > 0 and text[start - 1] == '"' and end < len(text) and text[end] == '"'


def count_body(text: str) -> dict[str, dict[str, int]]:
    """Per-class USE and MENTION counts. Quoted occurrences are mentions."""
    use = {cls: 0 for cls in CLASSES}
    mention = {cls: 0 for cls in CLASSES}
    for cls in CLASSES:
        for m in _PATTERNS[cls].finditer(text):
            if _is_mention(text, m.start(), m.end()):
                mention[cls] += 1
            else:
                use[cls] += 1
    return {"use": use, "mention": mention}


def use_vs_mention_control(text: str) -> dict[str, Any]:
    """Control fixture: exactly 1 real use + 1 quoted mention per class."""
    counted = count_body(text)
    per_class = {
        cls: {"use": counted["use"][cls], "mention": counted["mention"][cls]}
        for cls in CLASSES
    }
    ok = all(
        counted["use"][cls] == 1 and counted["mention"][cls] == 1 for cls in CLASSES
    )
    return {"pass": ok, "per_class": per_class}


def retention_rates(
    source_use: dict[str, int], synthesis_use: dict[str, int]
) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for cls in CLASSES:
        src = int(source_use.get(cls) or 0)
        syn = int(synthesis_use.get(cls) or 0)
        rate = (syn / src) if src else 0.0
        rows[cls] = {"source": src, "synthesis": syn, "retention_rate": rate}
    return rows


def rates_are_per_class(rows: Any) -> bool:
    if not isinstance(rows, dict):
        return False
    for cls in CLASSES:
        row = rows.get(cls)
        if not isinstance(row, dict) or "retention_rate" not in row:
            return False
    return True


def aggregate_would_hide(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The blended (all-classes) rate vs the per-class truth."""
    total_src = sum(int(rows[cls]["source"]) for cls in CLASSES)
    total_syn = sum(int(rows[cls]["synthesis"]) for cls in CLASSES)
    blended = (total_syn / total_src) if total_src else 0.0
    zero_classes = [cls for cls in CLASSES if rows[cls]["retention_rate"] == 0.0]
    return {
        "blended_rate": blended,
        "zero_retention_classes": zero_classes,
        "aggregate_hides_class_loss": bool(zero_classes) and blended > 0.0,
    }


def _split_evidence(text: str) -> tuple[str, list[str], str]:
    """(before, anchor_lines, after) around the ## EVIDENCE block."""
    m = EVIDENCE_HEADER.search(text)
    if not m:
        return text, [], ""
    before = text[: m.start()]
    rest = text[m.end():]
    anchors: list[str] = []
    tail_lines: list[str] = []
    in_block = True
    for line in rest.splitlines():
        stripped = line.strip()
        if in_block and stripped.startswith("- "):
            anchors.append(stripped[2:].strip())
        elif in_block and stripped.startswith("#"):
            in_block = False
            tail_lines.append(line)
        elif in_block and not stripped:
            continue
        else:
            in_block = False
            tail_lines.append(line)
    return before, anchors, "\n".join(tail_lines)


def evidence_gate(text: str) -> dict[str, Any]:
    """Candidate gate: an EVIDENCE block with 3..5 surviving anchors."""
    m = EVIDENCE_HEADER.search(text)
    if not m:
        return {"pass": False, "reason": "no-EVIDENCE-block", "anchor_count": 0}
    _, anchors, _ = _split_evidence(text)
    n = len(anchors)
    if n < MIN_ANCHORS:
        return {"pass": False, "reason": f"too-few-anchors:{n}<{MIN_ANCHORS}", "anchor_count": n}
    if n > MAX_ANCHORS:
        return {"pass": False, "reason": f"too-many-anchors:{n}>{MAX_ANCHORS}", "anchor_count": n}
    return {"pass": True, "reason": "ok", "anchor_count": n}


def apply_word_cap_exempt_evidence(text: str, cap: int = 8) -> str:
    """Word-cap the prose while the EVIDENCE block survives verbatim."""
    m = EVIDENCE_HEADER.search(text)
    if not m:
        words = text.split()
        return " ".join(words[:cap])
    before, anchors, after = _split_evidence(text)
    before_capped = " ".join(before.split()[:cap])
    after_capped = " ".join(after.split()[:cap])
    block = "## EVIDENCE\n" + "\n".join(f"- {a}" for a in anchors)
    parts = [p for p in (before_capped, block, after_capped) if p]
    return "\n\n".join(parts) + "\n"


__all__ = [
    "CLASSES",
    "MAX_ANCHORS",
    "MIN_ANCHORS",
    "aggregate_would_hide",
    "apply_word_cap_exempt_evidence",
    "count_body",
    "evidence_gate",
    "rates_are_per_class",
    "retention_rates",
    "use_vs_mention_control",
]
