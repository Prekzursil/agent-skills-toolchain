#!/usr/bin/env python3
"""SYN-0011 divergence panel: planted split plus live-tree facts.

Live SYN-0008 / SYN-0009 / SYN-0010 artifacts are absent. This panel is the
honest stand-in: two planted/live disagreements whose raw sources exist on
this worktree, plus two non-exclusive pairs that exercise the other
dispositions. Candidate count is recorded so probes can prove the engine
did not use it.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

PLANTED_REL = (
    "command-center/p2-wave/probes/SYN-0011/fixtures/planted/detector-status.txt"
)
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
MEASURE_REL = "command-center/p2-wave/_measure_one_delivered.py"
DISPATCH_REL = "command-center/p2-wave/seed-stage/dispatch_cursor.py"
SYN0008_REL = "command-center/synthesis/SYN-0008.candidate-syntheses.json"
SYN0009_REL = "command-center/synthesis/SYN-0009.raw-source-control.json"
SYN0010_REL = "command-center/receipts/SYN-0010.json"
OUT_REL = "command-center/synthesis/SYN-0011.adjudications.json"
SCHEMA_REL = "command-center/schema/adjudication-record.schema.json"

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0011/probe1_lexical_and_anchor.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0011/probe2_planted_split.py"
)

VOTE_RE_PATTERN = (
    r"(?i)(agent[ -]?count|majority([ -]?vote)?|\bvote\b|agents agree|"
    r"2 of 3|two of three|consensus of agents)"
)


def live_upstream(repo: Path | None = None) -> dict:
    root = repo or REPO
    rows = {
        "SYN-0008": {"path": SYN0008_REL, "present": (root / SYN0008_REL).is_file()},
        "SYN-0009": {"path": SYN0009_REL, "present": (root / SYN0009_REL).is_file()},
        "SYN-0010": {"path": SYN0010_REL, "present": (root / SYN0010_REL).is_file()},
    }
    return rows


def divergences() -> list[dict]:
    """Four divergences. Planted split is majority-wrong on purpose."""
    return [
        {
            "id": "D-PLANTED-DETECTOR",
            "topic": "planted split: detector status in the fixture raw file",
            "kind": "file-token",
            "raw_path": PLANTED_REL,
            "statements": [
                {
                    "id": "S-MAJ-HEALTHY",
                    "candidate_ids": ["C-ANTHROPIC-A", "C-OPENAI-B"],
                    "verbatim": (
                        "The planted detector is HEALTHY "
                        "(DETECTOR_STATUS=HEALTHY)."
                    ),
                    "token": "DETECTOR_STATUS=HEALTHY",
                },
                {
                    "id": "S-MIN-BROKEN",
                    "candidate_ids": ["C-RAW-CTRL"],
                    "verbatim": (
                        "The planted detector is BROKEN "
                        "(DETECTOR_STATUS=BROKEN)."
                    ),
                    "token": "DETECTOR_STATUS=BROKEN",
                },
            ],
        },
        {
            "id": "D-LIVE-DEPENDENCIES",
            "topic": "SYN-0011 catalog dependencies array",
            "kind": "catalog-field",
            "raw_path": CATALOG_REL,
            "unit_id": "SYN-0011",
            "field": "dependencies",
            "statements": [
                {
                    "id": "S-MAJ-THREE-DEPS",
                    "candidate_ids": ["C-ANTHROPIC-A", "C-OPENAI-B"],
                    "verbatim": (
                        "The catalog dependencies array for SYN-0011 is "
                        "[SYN-0008, SYN-0009, SYN-0010]."
                    ),
                    "equals": ["SYN-0008", "SYN-0009", "SYN-0010"],
                },
                {
                    "id": "S-MIN-ONE-DEP",
                    "candidate_ids": ["C-RAW-CTRL"],
                    "verbatim": (
                        "The catalog dependencies array for SYN-0011 is "
                        "exactly [SYN-0010]."
                    ),
                    "equals": ["SYN-0010"],
                },
            ],
        },
        {
            "id": "D-CLOUD-OK-SCOPE",
            "topic": "whether cloud ok=true counts as G-1 delivery",
            "kind": "multi-file-token",
            "statements": [
                {
                    "id": "S-MEASURE-NOT-CONSULTED",
                    "candidate_ids": ["C-ANTHROPIC-A"],
                    "verbatim": (
                        "The G-1 measure script states that cloud ok=true "
                        "is not consulted."
                    ),
                    "raw_path": MEASURE_REL,
                    "token": "cloud ok=true is not consulted",
                },
                {
                    "id": "S-DISPATCH-NOT-DELIVERY",
                    "candidate_ids": ["C-OPENAI-B"],
                    "verbatim": (
                        "The dispatch prompt states that cloud ok=true "
                        "is not delivery."
                    ),
                    "raw_path": DISPATCH_REL,
                    "token": "cloud ok=true is not delivery",
                },
            ],
        },
        {
            "id": "D-SENTINEL-SHAPE",
            "topic": "completion_sentinel shape is unit-scoped, not global",
            "kind": "catalog-field-pair",
            "raw_path": CATALOG_REL,
            "statements": [
                {
                    "id": "S-SYN-LONG",
                    "candidate_ids": ["C-ANTHROPIC-A"],
                    "verbatim": (
                        "SYN-0011's completion_sentinel begins "
                        "'SUCCESS:SYN-0011 emitted only when'."
                    ),
                    "unit_id": "SYN-0011",
                    "field": "completion_sentinel",
                    "startswith": "SUCCESS:SYN-0011 emitted only when",
                },
                {
                    "id": "S-ARC-SHORT",
                    "candidate_ids": ["C-OPENAI-B"],
                    "verbatim": (
                        "ARC-0014's completion_sentinel is the short token "
                        "SUCCESS:ARC-0014."
                    ),
                    "unit_id": "ARC-0014",
                    "field": "completion_sentinel",
                    "equals": "SUCCESS:ARC-0014",
                },
            ],
        },
    ]


def vote_pick(div: dict) -> str:
    """Negative control: the statement with the larger candidate roster."""
    best = max(div["statements"], key=lambda s: (len(s["candidate_ids"]), s["id"]))
    return str(best["id"])
