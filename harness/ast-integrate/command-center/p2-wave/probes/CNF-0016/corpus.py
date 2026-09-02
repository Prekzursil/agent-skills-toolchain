#!/usr/bin/env python3
"""Load the P0 defect corpus and strip implementer/reporter fields (CNF-0005 spirit)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CORPUS = HERE / "fixtures" / "defect-corpus.json"
RISK_REGISTER = REPO / "command-center" / "RISK-REGISTER.md"
CNF0005 = REPO / "command-center" / "confirmation" / "CNF-0005-blind-brief-builder.json"

STRIP_KEYS = frozenset(
    {
        "reporter_notes",
        "implementer_conclusion",
        "known_missing_step",
        "analysis",
        "confidence",
        "summary_table",
        "conclusion",
    }
)
LEAK_MARKERS = ("STRIP ME", "implementer_conclusion", "PASS expected")


def load_raw_corpus() -> dict:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def p0_records(raw: dict | None = None) -> list[dict]:
    data = raw if raw is not None else load_raw_corpus()
    rows = []
    for item in data.get("defects") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("severity") or "") != "P0":
            continue
        ident = str(item.get("id") or "").strip()
        if ident:
            rows.append(item)
    return rows


def strip_brief(defect: dict) -> dict:
    """Hand a confirmer the claim, raw source pointers, and tests — not the conclusion."""
    steps = defect.get("repro_steps") or []
    if not isinstance(steps, list):
        steps = []
    commands = [str(s) for s in steps if str(s).strip()]
    return {
        "id": str(defect.get("id") or ""),
        "severity": str(defect.get("severity") or ""),
        "title": str(defect.get("title") or ""),
        "repro_steps": commands,
        "expected_failure": str(defect.get("expected_failure") or ""),
    }


def leak_hits(brief: dict) -> list[str]:
    blob = json.dumps(brief, sort_keys=True)
    return [m for m in LEAK_MARKERS if m in blob]


def sampling_frame() -> dict:
    raw = load_raw_corpus()
    p0 = p0_records(raw)
    return {
        "source": str(CORPUS.relative_to(REPO).as_posix()),
        "p0_count": len(p0),
        "catalog_inputs": {
            "command-center/RISK-REGISTER.md": RISK_REGISTER.is_file(),
            "command-center/confirmation/CNF-0005-blind-brief-builder.json": CNF0005.is_file(),
            "defect_corpus_with_recorded_repro_steps": CORPUS.is_file(),
        },
        "catalog_input_p0_with_repro_steps": {
            "command-center/RISK-REGISTER.md": 0,
            "command-center/confirmation/CNF-0005-blind-brief-builder.json": 0,
        },
        "blind_brief": (
            "CNF-0005 artifact"
            if CNF0005.is_file()
            else "local-stripper (CNF-0005 artifact absent)"
        ),
        "note": raw.get("note"),
    }
