#!/usr/bin/env python3
"""Probe 2: field census of production interpolators (unmeasured ≠ safe)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import FIELD_IDS, LEGAL_VERDICTS, UNIT_ID  # noqa: E402
from measure import measure  # noqa: E402


def main() -> int:
    doc = measure()
    p2 = doc["probe2"]
    planted = set(p2["planted_fields"])
    benign = set(p2["benign_fields"])
    if planted != set(FIELD_IDS):
        print("FAILED:ADV-0074-probe2 planted census missed fields", sorted(set(FIELD_IDS) - planted))
        return 1
    if benign:
        print("FAILED:ADV-0074-probe2 benign census false-positive", sorted(benign))
        return 1
    if not doc["controls_ok"]:
        print("FAILED:ADV-0074-probe2 controls did not pass")
        return 1
    unmeasured = set(p2["unmeasured_fields"])
    for t in doc["targets"]:
        if not str(t["id"]).startswith("reach:"):
            continue
        field = t["field"]
        if field in unmeasured and t["verdict"] not in {"NOT-CHECKED", "BLOCKED"}:
            print("FAILED:ADV-0074-probe2 unmeasured field marked safe", t)
            return 1
        if t["verdict"] not in LEGAL_VERDICTS:
            print("FAILED:ADV-0074-probe2 illegal verdict", t)
            return 1
    out = {
        "probe": "probe2-field-census",
        "unit_id": UNIT_ID,
        "pass": True,
        "fields_in_templates": p2["fields_in_templates"],
        "unmeasured_fields": p2["unmeasured_fields"],
        "planted_fields": sorted(planted),
        "benign_fields": sorted(benign),
        "unmeasured_not_treated_as_safe": True,
        "overall_verdict": doc["overall_verdict"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "in_templates={0} unmeasured={1}".format(
            p2["fields_in_templates"], p2["unmeasured_fields"]
        )
    )
    print("SUCCESS:ADV-0074-probe2 production field census (unmeasured ≠ safe)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
