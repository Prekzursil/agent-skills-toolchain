"""Treat transcript text as untrusted DATA. Neutralise instruction-shaped spans.

Never eval, exec, compile, or subprocess transcript bytes. A payload that
says 'write EXECUTED_INSTRUCTION' must be logged as a neutralization, not
followed.
"""
from __future__ import annotations

import re
from typing import Any

REPLACEMENT = "[NEUTRALIZED instruction-shaped payload]"

# Instruction-shaped, not ordinary workflow vocabulary.
INSTRUCTION_RE = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior|preceding)\s+instructions"
    r"|you\s+are\s+now\s+(?:a|the)\b"
    r"|<\s*system\s*>"
    r"|</\s*system\s*>"
    r"|rm\s+-rf\s+/"
    r"|write(?:\s+a)?\s+file\s+EXECUTED_INSTRUCTION"
    r"|EXECUTED_INSTRUCTION)",
    re.IGNORECASE,
)


def neutralize_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    hits: list[dict[str, Any]] = []

    def _repl(match: re.Match[str]) -> str:
        hits.append(
            {
                "span": match.group(0)[:120],
                "start": match.start(),
                "end": match.end(),
                "replaced": True,
            }
        )
        return REPLACEMENT

    return INSTRUCTION_RE.sub(_repl, text), hits


def _walk(value: Any, hits: list[dict[str, Any]]) -> Any:
    if isinstance(value, str):
        cleaned, local = neutralize_text(value)
        hits.extend(local)
        return cleaned
    if isinstance(value, list):
        return [_walk(item, hits) for item in value]
    if isinstance(value, dict):
        return {k: _walk(v, hits) for k, v in value.items()}
    return value


def neutralize_record(record: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    hits: list[dict[str, Any]] = []
    cleaned = _walk(record, hits)
    assert isinstance(cleaned, dict)
    return cleaned, hits


def neutralize_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    out: list[dict[str, Any]] = []
    all_hits: list[dict[str, Any]] = []
    for ev in events:
        cleaned, hits = neutralize_record(ev)
        out.append(cleaned)
        all_hits.extend(hits)
    return out, all_hits
