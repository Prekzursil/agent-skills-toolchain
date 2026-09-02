#!/usr/bin/env python3
"""Probe 1: conservation, planted detector control, author 20-record anchor sample."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from anchors import check_record, sample_ids  # noqa: E402
from normalize import OUT_REL, PLANTED_TOKEN  # noqa: E402
from rank import prove_anti_repetition  # noqa: E402
from schema import domain, validate_run  # noqa: E402


def main() -> int:
    path = REPO / OUT_REL
    if not path.is_file():
        print("FAILED:CC-0019-probe1 missing receipt")
        return 1
    doc = json.loads(path.read_text(encoding="utf-8"))
    try:
        validate_run(doc)
    except ValueError as exc:
        print(f"FAILED:CC-0019-probe1 {exc}")
        return 1
    body = domain(doc)
    cons = body["conservation"]
    inputs = cons["inputs"]
    emitted = cons["emitted"]
    merged = cons["merged"]
    dropped = cons["dropped"]
    if inputs != emitted + merged + dropped:
        print(f"FAILED:conservation {inputs} != {emitted}+{merged}+{dropped}")
        return 1
    if dropped < 1 or not body.get("dropped"):
        print("FAILED:zero-drops-unmeasured")
        return 1
    if len(body["dropped"]) != dropped:
        print("FAILED:dropped-set-len")
        return 1
    records = list(body.get("records") or [])
    if len(records) < 20:
        print(f"FAILED:too-few-records n={len(records)}")
        return 1
    planted = body.get("planted_control") or doc.get("planted_control") or {}
    if not planted.get("found") or PLANTED_TOKEN not in json.dumps(doc):
        print("FAILED:planted-missing")
        return 1
    ranking = prove_anti_repetition()
    if not (
        ranking["repetition_does_not_raise_rank"]
        and ranking["strong_independent_outranks_echoes"]
        and ranking["same_document_collapses_to_one_signal"]
        and ranking["monotonicity_independent_probe_raises_rank"]
    ):
        print(f"FAILED:ranking {ranking}")
        return 1
    sample = sample_ids(records, 0, 20, 19)
    by_id = {r["claim_id"]: r for r in records}
    resolved = 0
    misses: list[str] = []
    for cid in sample:
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
                "probe": "probe1-sample",
                "conservation": cons,
                "planted": True,
                "author_sample": sample,
                "resolve_rate": rate,
                "ranking_ok": True,
            },
            sort_keys=True,
        )
    )
    if resolved != 20:
        print("FAILED:CC-0019-probe1 anchors " + ";".join(misses[:8]))
        return 1
    print(f"resolve_rate={rate} planted=True dropped={dropped} merged={merged}")
    print("SUCCESS:CC-0019-probe1 conservation planted author-sample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
