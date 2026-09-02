#!/usr/bin/env python3
"""Probe 1: submit each abuse variant to the marketplace linter; record accept/reject."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    ABUSE_TARGETS,
    UNIT,
    build_all,
    dumps,
    submit_to_linter,
    with_work,
)


def measure(work: Path) -> dict:
    variants = build_all(work)
    rows = []
    discovery = None
    linter_present = False
    for vid, spec in variants.items():
        result = submit_to_linter(
            Path(spec["blob"]), variant_id=vid, work=work
        )
        discovery = result.get("discovery")
        linter_present = bool(result.get("linter_present"))
        rows.append(
            {
                "variant_id": vid,
                "abuse": spec.get("abuse"),
                "accepted": bool(result["accepted"]),
                "rejected": bool(result["rejected"]),
                "rule_ids": list(result.get("rule_ids") or []),
                "reason": result.get("reason"),
                "invoked": result.get("invoked"),
                "has_dotdot_member": spec.get("has_dotdot_member"),
                "tar_members": spec.get("tar_members"),
            }
        )
    by_id = {r["variant_id"]: r for r in rows}
    control = by_id["C-BENIGN"]
    control_accepted = bool(control["accepted"]) and not control["rejected"]
    submitted = {r["variant_id"] for r in rows}
    expected = {"C-BENIGN", *ABUSE_TARGETS}
    pass_ok = submitted == expected and control_accepted
    return {
        "probe": "probe1-linter-accept-reject",
        "unit_id": UNIT,
        "linter_present": linter_present,
        "discovery": discovery,
        "control_accepted": control_accepted,
        "rows": rows,
        "fail_open": (not linter_present)
        and all(r["accepted"] and not r["rejected"] for r in rows),
        "pass": pass_ok,
    }


def main() -> int:
    doc = with_work(measure)
    print(dumps(doc))
    print(
        "linter_present={linter_present} control_accepted={control_accepted} "
        "fail_open={fail_open} rows={n}".format(
            linter_present=doc["linter_present"],
            control_accepted=doc["control_accepted"],
            fail_open=doc["fail_open"],
            n=len(doc["rows"]),
        )
    )
    if not doc.get("pass"):
        print(
            "FAILED:ADV-0025-probe1 linter matrix did not complete with a passing control"
        )
        return 1
    print("SUCCESS:ADV-0025-probe1 submitted each variant to the marketplace linter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
