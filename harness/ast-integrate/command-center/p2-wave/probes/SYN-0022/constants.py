"""SYN-0022 contract constants. Sentinel text is the catalog completion_sentinel."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OUTPUT_REL = "command-center/synthesis/SYN-0022.premise-reprobe.json"
SCHEMA_REL = "command-center/schema/reprobe-record.schema.json"
UNIT_ID = "SYN-0022"
MNN_FACT_ID = "F-MNN-COLLISION-LIVE-31"

P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0022/probe1_fingerprint_independence.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0022/probe2_controls_and_mnn.py"
)


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT_ID:
            return unit
    raise SystemExit("FAILED:SYN-0022 catalog unit missing")


def catalog_sentinel() -> str:
    return str(catalog_unit().get("completion_sentinel") or "")


def catalog_question() -> str:
    return str(catalog_unit().get("question_or_target") or "")
