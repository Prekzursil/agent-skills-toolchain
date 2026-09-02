"""Synthesis intake sanitiser: scrub untrusted artifact bytes BEFORE field split.

A delimiter inside an injection payload shifts later columns if split happens
first. Per-field scrub then never sees the shifted tail, so the payload can
land in the instruction channel. This module scans raw text, truncates or
drops injection spans (including their delimiter-bearing tails), logs each
hit, then returns bytes that are safe to split.
"""
from __future__ import annotations

import re
from typing import Any

DELIMITER = "|"

# Earliest-match wins. Patterns are instruction-shaped, not ordinary prose.
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_previous_instructions",
        re.compile(r"(?i)ignore\s+previous\s+instructions"),
    ),
    ("you_are_now", re.compile(r"(?i)\byou\s+are\s+now\b")),
    ("emit_marker", re.compile(r"EMIT_MARKER=")),
)


def first_injection(text: str) -> tuple[str, re.Match[str]] | None:
    found: tuple[str, re.Match[str]] | None = None
    for name, cre in PATTERNS:
        m = cre.search(text)
        if m is None:
            continue
        if found is None or m.start() < found[1].start():
            found = (name, m)
    return found


def _payload_survives(kept: str, expected_fields: int) -> bool:
    parts = kept.split(DELIMITER)
    if len(parts) < expected_fields:
        return False
    return bool(parts[expected_fields - 1].strip())


def sanitise_raw(
    raw: str,
    source: str,
    expected_fields: int = 3,
) -> tuple[str, list[dict[str, Any]]]:
    """Return (sanitised_text, log_entries). Newline-split is not a field split."""
    ends_nl = raw.endswith("\n")
    logs: list[dict[str, Any]] = []
    kept_lines: list[str] = []
    for lineno, line in enumerate(raw.splitlines(), start=1):
        hit = first_injection(line)
        if hit is None:
            kept_lines.append(line)
            continue
        name, match = hit
        kept = line[: match.start()].rstrip(" \t")
        if kept.endswith(DELIMITER):
            kept = kept.rstrip(DELIMITER + " \t")
        if _payload_survives(kept, expected_fields):
            action = "truncate-at-match"
            kept_lines.append(kept)
        else:
            action = "drop-line"
        logs.append(
            {
                "source": source,
                "line": lineno,
                "pattern": name,
                "action": action,
                "span": [match.start(), match.end()],
                "match_text": match.group(0),
                "kept_prefix": kept,
            }
        )
    out = "\n".join(kept_lines)
    if ends_nl and kept_lines:
        out += "\n"
    return out, logs


def format_log_line(entry: dict[str, Any]) -> str:
    return (
        "SANITISER"
        f" source={entry['source']}"
        f" line={entry['line']}"
        f" pattern={entry['pattern']}"
        f" action={entry['action']}"
        f" kept_prefix={entry['kept_prefix']!r}"
    )


def strip_field(field: str) -> str:
    """Naive per-field scrub (the sanitise-after-split control)."""
    hit = first_injection(field)
    if hit is None:
        return field
    return field[: hit[1].start()].rstrip(" \t")
