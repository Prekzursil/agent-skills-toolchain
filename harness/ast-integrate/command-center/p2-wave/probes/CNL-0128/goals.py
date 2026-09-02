#!/usr/bin/env python3
"""The five owner goal phrasings (spec line 11198, quoted in the catalog).

_USER-PROMPTS.md is not on this Linux worktree. The catalog unit question
for CNL-0128 quotes the five phrases in order; that quote is the live
source. Round-trip encodings are local A10 stopping expressions plus
any required CouncilSpec fields the phrase names.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
SPEC_LINE = 11198

# Exact phrases from the catalog parenthetical, in spec order.
PHRASES: tuple[str, ...] = (
    "brainstorm until 100 unique ideas",
    "argue until all agree or 12 rounds",
    "90 percent consensus with a mandatory minority report",
    "continue until no new counterexample for two rounds",
    "stop only after an executable test settles it",
)

GOALS: list[dict[str, Any]] = [
    {
        "id": "G1",
        "phrase": PHRASES[0],
        "stopping_expr": "unique_ideas >= 100",
        "minority_report": "optional",
        "protocol": "brainstorm",
        "required_tokens": ("100", "unique", "ideas"),
        "restatement": (
            "Stop when unique ideas reach at least 100 "
            "(stopping_expr unique_ideas >= 100)."
        ),
    },
    {
        "id": "G2",
        "phrase": PHRASES[1],
        "stopping_expr": "unanimity == true OR max_rounds == 12",
        "minority_report": "optional",
        "protocol": "argument",
        "required_tokens": ("agree", "12", "rounds"),
        "restatement": (
            "Stop when all seats agree, or after 12 rounds "
            "(unanimity == true OR max_rounds == 12)."
        ),
    },
    {
        "id": "G3",
        "phrase": PHRASES[2],
        "stopping_expr": "consensus >= 0.90",
        "minority_report": "mandatory",
        "protocol": "consensus",
        "required_tokens": ("90", "consensus", "minority"),
        "restatement": (
            "Stop when consensus is at least 90 percent. "
            "A minority report is mandatory."
        ),
    },
    {
        "id": "G4",
        "phrase": PHRASES[3],
        "stopping_expr": "no_new_counterexample_rounds >= 2",
        "minority_report": "optional",
        "protocol": "counterexample-search",
        "required_tokens": ("counterexample", "two", "rounds"),
        "restatement": (
            "Stop after two consecutive rounds with no new counterexample "
            "(no_new_counterexample_rounds >= 2)."
        ),
    },
    {
        "id": "G5",
        "phrase": PHRASES[4],
        "stopping_expr": "quality_gate == PASS",
        "minority_report": "optional",
        "protocol": "test-settlement",
        "required_tokens": ("test", "settles"),
        "restatement": (
            "Stop only after an executable test settles it "
            "(quality_gate == PASS). No round-count OR-escape."
        ),
    },
]

BY_ID = {g["id"]: g for g in GOALS}


def catalog_quote(repo: Path | None = None) -> dict[str, Any]:
    """Cite the live catalog line that quotes the five goals."""
    root = repo or REPO
    path = root / CATALOG_REL
    text = path.read_text(encoding="utf-8")
    needle = PHRASES[0]
    idx = text.find(needle)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0128 catalog missing phrase {needle!r}")
    line = text[:idx].count("\n") + 1
    # Confirm all five sit on that same unit question.
    missing = [p for p in PHRASES if p not in text]
    return {
        "path": CATALOG_REL,
        "line": line,
        "spec_line_claimed": SPEC_LINE,
        "source_file_on_tree": False,
        "source_file": "_USER-PROMPTS.md",
        "phrases": list(PHRASES),
        "missing_on_catalog": missing,
        "snippet": needle,
    }


def dump_fixture(repo: Path | None = None) -> Path:
    root = repo or REPO
    quote = catalog_quote(root)
    payload = {
        "spec_line": SPEC_LINE,
        "catalog_anchor": f"{quote['path']}:{quote['line']}",
        "note": (
            "_USER-PROMPTS.md:11198 is not on this Linux worktree; "
            "phrases are the catalog quote of that line."
        ),
        "goals": GOALS,
        "catalog_quote": quote,
    }
    out = HERE / "fixtures" / "goals-11198.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
