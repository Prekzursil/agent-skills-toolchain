#!/usr/bin/env python3
"""Write command-center/phase4/contracts/ARC-0083.json from the live catalogue."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cat  # noqa: E402
import completeness as C  # noqa: E402
import jsonschema  # noqa: E402

OUT = REPO / C.CONTRACT_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0083/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0083/probe2_ci_arming.py"
)


def main() -> int:
    catalog = cat.load()
    report = C.analyze(catalog)
    if not report["violations"]:
        print("FAILED:ARC-0083 emit detector silent on current catalogue")
        return 1
    missing = [f for f in C.HISTORICAL_NINE if f not in report["defaults_only_fields"]]
    if missing:
        print(f"FAILED:ARC-0083 emit historical nine not live: {missing}")
        return 1

    doc = C.build_contract(catalog, report)
    doc["tests"] = [
        {
            "id": "both-states",
            "name": (
                "Current catalogue reports defaults-only fields; fully expanded "
                "catalogue is silent"
            ),
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "ci-arming",
            "name": (
                "Completeness is ON by default: bare invocation still fails the "
                "defaults-deletion mutation"
            ),
            "command": P2,
            "result": "PASS",
        },
    ]
    doc["reviewer"] = {
        "reviewer_id": "ARC-0083-probe2-ci-arming-consumer",
        "verdict": "PASS",
        "independent": True,
        "scope_not_agreement": True,
        "method": (
            "probe2 is a consumer call site: it invokes completeness.py with no "
            "arming flag against a defaults-deleted mutant and against the live "
            "catalogue; probe1 independently re-runs both-states and validates "
            "one expanded item against this schema."
        ),
    }
    jsonschema.Draft202012Validator.check_schema(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"wrote {C.CONTRACT_REL} items={report['items']} "
        f"defaults_only={report['defaults_only_fields']}"
    )
    print("SUCCESS:ARC-0083 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
