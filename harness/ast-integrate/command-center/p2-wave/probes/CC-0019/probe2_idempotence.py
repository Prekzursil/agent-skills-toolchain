#!/usr/bin/env python3
"""Probe 2: idempotent ids on a second in-memory run; disjoint 20-record sample."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from anchors import check_record, sample_ids  # noqa: E402
from normalize import OUT_REL, build_run  # noqa: E402
from schema import domain, validate_run  # noqa: E402


def main() -> int:
    path = REPO / OUT_REL
    if not path.is_file():
        print("FAILED:CC-0019-probe2 missing receipt")
        return 1
    disk = json.loads(path.read_text(encoding="utf-8"))
    try:
        validate_run(disk)
    except ValueError as exc:
        print(f"FAILED:CC-0019-probe2 {exc}")
        return 1
    body = domain(disk)
    second = build_run(REPO)
    ids_disk = [r["claim_id"] for r in body["records"]]
    ids_run = [r["claim_id"] for r in second["records"]]
    if ids_disk != ids_run:
        print(
            "FAILED:idempotence "
            f"disk={len(ids_disk)} rerun={len(ids_run)} "
            f"only_disk={sorted(set(ids_disk) - set(ids_run))[:5]} "
            f"only_rerun={sorted(set(ids_run) - set(ids_disk))[:5]}"
        )
        return 1
    records = list(body["records"])
    author = sample_ids(records, 0, 20, 19)
    reviewer = sample_ids(records, 20, 20, 19)
    if len(reviewer) < 20:
        print(f"FAILED:reviewer-sample-short n={len(reviewer)}")
        return 1
    if set(author) & set(reviewer):
        print("FAILED:sample-overlap")
        return 1
    by_id = {r["claim_id"]: r for r in records}
    resolved = 0
    misses: list[str] = []
    for cid in reviewer:
        rec = by_id[cid]
        ok, n, miss = check_record(REPO, rec)
        if n < 1 or ok != n:
            misses.extend(miss or [f"{cid}:empty-lineage"])
        else:
            resolved += 1
    rate = f"{resolved}/20"
    print(
        json.dumps(
            {
                "probe": "probe2-idempotence",
                "ids_equal": True,
                "record_count": len(ids_disk),
                "reviewer_sample": reviewer,
                "resolve_rate": rate,
                "disjoint_from_author": True,
            },
            sort_keys=True,
        )
    )
    if resolved != 20:
        print("FAILED:CC-0019-probe2 anchors " + ";".join(misses[:8]))
        return 1
    print(f"ids_equal=True reviewer_resolve_rate={rate}")
    print("SUCCESS:CC-0019-probe2 idempotence reviewer-sample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
