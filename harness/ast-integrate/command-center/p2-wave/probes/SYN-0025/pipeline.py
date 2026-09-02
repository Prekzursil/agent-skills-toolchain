"""Correct (sanitise-then-split) vs naive (split-then-per-field-scrub) pipelines."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sanitiser import DELIMITER, format_log_line, sanitise_raw, strip_field
from synthesizer import (
    TRUSTED_INSTRUCTION,
    assemble_prompt,
    fence_data,
    synthesize,
)

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

COLUMNS = {
    "council": ["turn", "role", "text"],
    "receipt": ["id", "state", "evidence"],
}


def read_fixture(kind: str, planted: bool) -> str:
    folder = "planted" if planted else "clean"
    return (FIX / folder / f"{kind}.records").read_text(encoding="utf-8")


def parse_records(text: str, columns: list[str], source: str) -> list[dict[str, str]]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    header = lines[0].split(DELIMITER)
    if header != columns:
        raise ValueError(f"{source}: header {header!r} != {columns!r}")
    rows: list[dict[str, str]] = []
    n = len(columns)
    for ln in lines[1:]:
        parts = ln.split(DELIMITER)
        if len(parts) != n:
            raise ValueError(
                f"{source}: column-shift want={n} got={len(parts)} line={ln!r}"
            )
        rec = dict(zip(columns, parts))
        rec["_source"] = source
        rows.append(rec)
    return rows


def split_then_scrub(
    raw: str, columns: list[str], source: str
) -> tuple[list[dict[str, str]], list[str]]:
    """Naive: field-split first, scrub only the expected columns, extras leak."""
    n = len(columns)
    leaked: list[str] = []
    rows: list[dict[str, str]] = []
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return [], []
    header = lines[0].split(DELIMITER)
    if header != columns:
        raise ValueError(f"{source}: header {header!r} != {columns!r}")
    for ln in lines[1:]:
        parts = ln.split(DELIMITER)
        cleaned = [strip_field(p) for p in parts[:n]]
        if len(cleaned) < n:
            cleaned += [""] * (n - len(cleaned))
        leaked.extend(parts[n:])
        rec = dict(zip(columns, cleaned[:n]))
        rec["_source"] = source
        rows.append(rec)
    return rows, leaked


def run_correct(planted: bool) -> dict[str, Any]:
    logs: list[dict[str, Any]] = []
    fenced: list[str] = []
    records: list[dict[str, str]] = []
    sanitised: dict[str, str] = {}
    for kind in ("council", "receipt"):
        raw = read_fixture(kind, planted)
        source = f"{kind}.records"
        cleaned, kind_logs = sanitise_raw(raw, source, expected_fields=3)
        logs.extend(kind_logs)
        sanitised[kind] = cleaned
        recs = parse_records(cleaned, COLUMNS[kind], source)
        records.extend(recs)
        fenced.append(fence_data(source, cleaned))
    instruction = TRUSTED_INSTRUCTION
    prompt = assemble_prompt(instruction, fenced)
    synthesis = synthesize(instruction, records)
    return {
        "mode": "sanitise-before-split",
        "planted": planted,
        "sanitised": sanitised,
        "logs": logs,
        "log_lines": [format_log_line(e) for e in logs],
        "records": records,
        "instruction": instruction,
        "prompt": prompt,
        "synthesis": synthesis,
        "leaked_extras": [],
    }


def run_naive(planted: bool) -> dict[str, Any]:
    leaked_all: list[str] = []
    records: list[dict[str, str]] = []
    fenced: list[str] = []
    for kind in ("council", "receipt"):
        raw = read_fixture(kind, planted)
        source = f"{kind}.records"
        recs, leaked = split_then_scrub(raw, COLUMNS[kind], source)
        leaked_all.extend(leaked)
        records.extend(recs)
        fenced.append(fence_data(source, raw))
    instruction = TRUSTED_INSTRUCTION
    if leaked_all:
        instruction = TRUSTED_INSTRUCTION + "\n" + "\n".join(leaked_all)
    prompt = assemble_prompt(instruction, fenced)
    synthesis = synthesize(instruction, records)
    return {
        "mode": "sanitise-after-split",
        "planted": planted,
        "logs": [],
        "log_lines": [],
        "records": records,
        "instruction": instruction,
        "prompt": prompt,
        "synthesis": synthesis,
        "leaked_extras": leaked_all,
    }
