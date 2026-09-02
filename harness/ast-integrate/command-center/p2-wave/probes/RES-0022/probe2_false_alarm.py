#!/usr/bin/env python3
"""Probe 2: schema discrimination, >=3 CONSISTENT, overclaim, partitioned reviewers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from overclaim import check_overclaim, hunt_view  # noqa: E402
from schema_local import error_messages, garbage_rejected, make_validator  # noqa: E402

ART = REPO / "command-center/research/RES-0022.json"
SCHEMA = REPO / "command-center/schema/research-claim-record.schema.json"


def _mutate_table(doc: dict) -> dict:
    mutant = json.loads(json.dumps(doc))
    view = mutant["report"] if isinstance(mutant.get("report"), dict) else mutant
    if not isinstance(view.get("contradiction_table"), list):
        view = mutant
    counts = view.get("counts")
    if isinstance(counts, dict):
        counts["consistent_count"] = 0
        counts["contradicted_count"] = int(counts.get("contradicted_count") or 0) + sum(
            1
            for r in view.get("contradiction_table") or []
            if isinstance(r, dict) and r.get("verdict") == "CONSISTENT"
        )
    view["contradiction_table"] = [
        {**r, "verdict": "CONTRADICTED", "classification": "doc_stale"}
        if isinstance(r, dict) and r.get("verdict") == "CONSISTENT"
        else r
        for r in view.get("contradiction_table") or []
    ]
    view["verdict"] = "REFUTED"
    return mutant


def main() -> int:
    if not ART.is_file() or not SCHEMA.is_file():
        print("FAILED:RES-0022-probe2 missing artifact or schema")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    validator = make_validator()

    rejected = garbage_rejected(validator)
    print(f"schema_garbage_rejected={rejected}/3")
    if rejected != 3:
        print("FAILED:RES-0022-probe2 schema accepts garbage")
        return 1

    errors = error_messages(doc)
    if errors:
        print("FAILED:RES-0022-probe2 artifact fails schema", errors[0])
        for err in errors[:12]:
            print(" ", err)
        return 1
    print("schema_accepts_artifact=True")

    ok, why = check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0022-probe2 overclaim")
        return 1

    view = hunt_view(doc)
    consistent = [
        r
        for r in view.get("contradiction_table") or []
        if isinstance(r, dict) and r.get("verdict") == "CONSISTENT"
    ]
    print(f"consistent_rows={len(consistent)}")
    if len(consistent) < 3:
        print("FAILED:RES-0022-probe2 fewer than 3 CONSISTENT rows")
        return 1

    mutant = _mutate_table(doc)
    fake_ok, fake_why = check_overclaim(mutant)
    print(f"false_alarm_mutant_rejected={not fake_ok} {fake_why}")
    if fake_ok:
        print("FAILED:RES-0022-probe2 overclaim accepted all-contradicted mutant")
        return 1

    reviewers = view.get("reviewers") or []
    parts = [set(r.get("partition") or []) for r in reviewers if isinstance(r, dict)]
    print(f"reviewer_partitions={[len(p) for p in parts]}")
    if len(parts) < 2 or parts[0] & parts[1]:
        print("FAILED:RES-0022-probe2 reviewer partitions not disjoint")
        return 1

    if "SUCCESS:RES-0022" not in ART.read_text(encoding="utf-8"):
        print("FAILED:RES-0022-probe2 sentinel absent")
        return 1
    print("SUCCESS:RES-0022-probe2 false-alarm schema partitioned-reviewers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
