"""SYN-0040 contract constants. Sentinel text is the catalog completion_sentinel."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "SYN-0040"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OUTPUT_REL = "command-center/synthesis/SYN-0040.gate-control-matrix.json"
SCHEMA_REL = "command-center/schema/detector-control.schema.json"
FIXTURES_REL = "command-center/p2-wave/probes/SYN-0040/fixtures"

# Inputs: every gate/detector from SYN-0002, SYN-0013, SYN-0016..SYN-0021, SYN-0030.
BUCKET_UNITS = [
    "SYN-0002",
    "SYN-0013",
    "SYN-0016",
    "SYN-0017",
    "SYN-0018",
    "SYN-0019",
    "SYN-0020",
    "SYN-0021",
    "SYN-0030",
]
CALIBRATION_ID = "CAL-SILENT-BOTH"

P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0040/probe1_every_row.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0040/probe2_silent_and_mutation.py"
)

PRODUCTION_RECEIPT_HINTS = {
    "SYN-0002": ["command-center/receipts/SYN-0002.json"],
    "SYN-0013": ["command-center/receipts/SYN-0013.json"],
    "SYN-0016": ["command-center/receipts/SYN-0016.json"],
    "SYN-0017": ["command-center/synthesis/SYN-0017.mechanism-dedup.json"],
    "SYN-0018": ["command-center/receipts/SYN-0018.json"],
    "SYN-0019": ["command-center/receipts/SYN-0019.json"],
    "SYN-0020": ["command-center/synthesis/SYN-0020.docs-code-parity.json"],
    "SYN-0021": ["command-center/synthesis/SYN-0021.completion-census.json"],
    "SYN-0030": ["command-center/receipts/SYN-0030.json"],
}


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT_ID:
            return unit
    raise SystemExit("FAILED:SYN-0040 catalog unit missing")


def catalog_sentinel() -> str:
    return str(catalog_unit().get("completion_sentinel") or "")


def catalog_question() -> str:
    return str(catalog_unit().get("question_or_target") or "")
