"""Ten extraction dimensions and the kappa floor, frozen before labelling.

The floor is a protocol constant, not a number fitted after seeing scores.
A dimension whose Cohen kappa falls below KAPPA_FLOOR is UNMEASURABLE and
must not be averaged into a single agreement figure.
"""
from __future__ import annotations

from typing import Any

UNIT_ID = "WFA-0042"
SENTINEL = "SUCCESS:WFA-0042"
OUT_REL = "command-center/wfa/WFA-0042-extraction-gold-set.json"
SCHEMA_REL = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/ExtractionReport"

# Recorded before any labeller ran and before any extractor was scored.
KAPPA_FLOOR = 0.4
GOLD_VERSION = 1
N_GOLD = 20
THIRD_READER_N = 5

CELL_STATES = ("EVIDENCED", "HONEST-NULL", "EMPTY")

DIMENSIONS = (
    "license",
    "maintenance",
    "provenance",
    "roles",
    "stages",
    "stop_rules",
    "tools",
    "task_fit",
    "failure_behaviour",
    "benchmark_evidence",
)

FAMILIES = (
    "A-saved-workflow",
    "B-repo-workflow",
    "C-repo-tool",
    "D-harness-runtime",
    "E-agent",
    "F-plugin",
    "G-skill",
    "H-executed-corpus",
    "I-command",
)

# Catalog WFA-0032..WFA-0041 mapping (scored against this gold, not this unit).
DIMENSION_OWNERS = {
    "provenance": "WFA-0032",
    "license": "WFA-0033",
    "maintenance": "WFA-0034",
    "task_fit": "WFA-0035",
    "stages": "WFA-0036",
    "roles": "WFA-0037",
    "tools": "WFA-0038",
    "stop_rules": "WFA-0039",
    "failure_behaviour": "WFA-0040",
    "benchmark_evidence": "WFA-0041",
}


def empty_cell(*, note: str = "") -> dict[str, Any]:
    return {
        "cell_state": "EMPTY",
        "value": "",
        "anchor": "",
        "note": note,
    }


def honest_null(*, note: str = "") -> dict[str, Any]:
    return {
        "cell_state": "HONEST-NULL",
        "value": "HONEST-NULL",
        "anchor": "",
        "note": note,
    }


def evidenced(value: str, *, anchor: str = "", note: str = "") -> dict[str, Any]:
    return {
        "cell_state": "EVIDENCED",
        "value": value,
        "anchor": anchor,
        "note": note,
    }


def label_key(cell: dict[str, Any]) -> str:
    state = str(cell.get("cell_state") or "EMPTY")
    value = str(cell.get("value") or "")
    return f"{state}|{value}"
