#!/usr/bin/env python3
"""Probe 2: unknown fields are rejected with a closed-set id, not ignored."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.import_generic_dag import GenericDeclarativeDagAdapter  # noqa: E402
from agentspec.validate import CLOSED_VIOLATION_IDS  # noqa: E402

FX = HERE / "fixtures"
ADAPTER = GenericDeclarativeDagAdapter()


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0162-probe2 {msg}")
    return 1


def main() -> int:
    good = ADAPTER.import_path(FX / "valid_minimal.json")
    if not good.ok or good.workflow is None:
        return _fail(f"valid twin rejected {good.to_dict()}")
    if any(v.id == "AS-DAG-UNKNOWN-FIELD" for v in good.violations):
        return _fail("unknown-field id fired on the good twin")
    print("valid_minimal imported ok=True unknown_field_silent_on_good=True")

    for name in ("unknown_field.json", "unknown_field.yaml"):
        result = ADAPTER.import_path(FX / name)
        ids = [v.id for v in result.violations]
        details = [v.detail for v in result.violations]
        if result.ok:
            return _fail(f"{name} imported despite mystery_field")
        if "AS-DAG-UNKNOWN-FIELD" not in ids:
            return _fail(f"{name} missing rejection id: {result.to_dict()}")
        if "AS-DAG-UNKNOWN-FIELD" not in CLOSED_VIOLATION_IDS:
            return _fail("AS-DAG-UNKNOWN-FIELD escaped the closed set")
        if "mystery_field" not in details:
            return _fail(f"{name} rejection did not name the field: {details}")
        print(
            f"{name} rejected id=AS-DAG-UNKNOWN-FIELD field=mystery_field "
            f"closed=True"
        )

    payload = {
        "probe": "probe2-unknown-field",
        "unit_id": "IMP-0162",
        "pass": True,
        "rejection_id": "AS-DAG-UNKNOWN-FIELD",
        "in_closed_set": True,
        "good_twin_imported": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0162-probe2 unknown field rejected with named id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
