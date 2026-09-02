#!/usr/bin/env python3
"""Shared paths and catalog contract for ADV-0091."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CNL80 = REPO / "command-center" / "p2-wave" / "probes" / "CNL-0080"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
OUT_REL = "command-center/adversarial/ADV-0091-instant-unanimity-trigger.json"
SCHEMA_REL = "command-center/schema/council-pathology-sim.schema.json"
SCHEMA_REL = SCHEMA_REL
MIN_BYTES = 2048
MIN_BYTES = MIN_BYTES
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0091/probe1_primed_transcript.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0091/probe2_outcome_delta.py"
)
LISTED_INTERVENTIONS = (
    "blind_reevaluation",
    "forced_dissent",
    "counterexample_generation",
    "role_rotation",
    "critic_recruitment",
)
QUESTION = (
    "When a council reaches unanimity in the first round with no independent "
    "briefs, does the runtime actually trigger blind re-evaluation, forced "
    "dissent, counterexample generation, role rotation or critic recruitment?"
)


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "ADV-0091":
            return unit
    raise SystemExit("FAILED:ADV-0091 catalog row missing")


def completion_sentinel() -> str:
    return str(catalog_unit()["completion_sentinel"])


completion_sentinel = completion_sentinel
