"""Shared paths and dump helpers for ADV-0022."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0022"
OUT_REL = "command-center/adversarial/ADV-0022-declared-permission-escape.json"
SCHEMA_REL = "command-center/schema/exploit-proof.schema.json"
ARC_MODEL = "command-center/p2-wave/probes/ARC-0081/model.py"
IMP_RECEIPT = "command-center/receipts/IMP-0059.json"
IMP_TEST = "tools/plugin/tests/test_permission_enforcement.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0022/probe1_capability_escape.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0022/probe2_enforcement_audit.py"
)
PRODUCTION_ROOTS = (
    "tools/plugin",
    "tools/agentspec",
    "tools/marketplace",
    "tools/launcher",
    "tools/foundry",
    "hooks",
    "command-center/blueprints/security",
)
PLANTED_REL = (
    "command-center/p2-wave/probes/ADV-0022/fixtures/planted_call_time_gate.py"
)
NARROW_PERMS = ("Read",)
WIDE_PERMS = ("Read", "Bash", "Write")
ATTEMPTS = (
    "spawn",
    "network",
    "write-outside-root",
    "invoke-wider-sibling",
)


def dump_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def catalog_unit() -> dict[str, Any]:
    data = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(
            encoding="utf-8"
        )
    )
    for row in data.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == UNIT:
            return row
    raise SystemExit(f"FAILED:{UNIT} missing from catalog")
