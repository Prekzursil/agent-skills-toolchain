#!/usr/bin/env python3
"""Probe 2: partitioned reviewers + baseline-required promotion (both-states).

Mechanically independent of probe1: does not re-parse arXiv XML. Reads the
excerpt tables and the checker mutants. A promoted row with its baseline
stripped must go red; collapsed same-vendor partitions must go red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from check_record import (  # noqa: E402
    check_record,
    mutant_collapse_partitions,
    mutant_strip_baseline,
    mutant_strip_negative_queries,
)

ART = REPO / "command-center/research/RES-0076.json"
EXCERPTS = HERE / "fixtures" / "excerpts.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0076-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = check_record(doc)
    print(f"good_ok={ok} {why}")
    if not ok:
        return fail(f"good record rejected: {why}")

    excerpts = json.loads(EXCERPTS.read_text(encoding="utf-8"))
    wang = excerpts["tables"]["wang_2024_table2"]["rows"]
    sa = next(r for r in wang if r["method"] == "Single Agent")
    mad = next(r for r in wang if r["method"] == "MAD (3 Agents)")
    live_delta = round(mad["avg_demo"] - sa["avg_demo"], 4)
    rec = next(
        r
        for r in (doc.get("negative_result_register") or [])
        if r.get("id") == "NR-WANG-MAD-DEMO-AVG"
    )
    if rec.get("delta") != live_delta:
        return fail(f"Wang avg_demo delta artifact={rec.get('delta')} live={live_delta}")
    if rec.get("baseline") != sa["avg_demo"] or rec.get("effect_size") != mad["avg_demo"]:
        return fail("Wang Table 2 numbers do not match excerpts")

    zhang = excerpts["tables"]["zhang_2025_table3"]["rows"]
    z_cot = next(r for r in zhang if r["method"] == "CoT")
    z_som = next(r for r in zhang if r["method"] == "SoM")
    zrec = next(
        r
        for r in doc["negative_result_register"]
        if r.get("id") == "NR-ZHANG-COT-WINRATE"
    )
    zdelta = round(z_som["MMLU"] - z_cot["MMLU"], 4)
    if zrec.get("delta") != zdelta:
        return fail(f"Zhang MMLU delta artifact={zrec.get('delta')} live={zdelta}")

    m1 = mutant_strip_baseline(doc)
    b1, w1 = check_record(m1)
    print(f"mutant_baseline_ok={b1} {w1}")
    if b1:
        return fail("promoted row without baseline was accepted")

    m2 = mutant_collapse_partitions(doc)
    b2, w2 = check_record(m2)
    print(f"mutant_partition_ok={b2} {w2}")
    if b2:
        return fail("overlapped same-vendor reviewers were accepted")

    m3 = mutant_strip_negative_queries(doc)
    b3, w3 = check_record(m3)
    print(f"mutant_queries_ok={b3} {w3}")
    if b3:
        return fail("query set without negative phrasings was accepted")

    revs = doc.get("reviewers") or []
    print(
        f"reviewers={[r.get('vendor') for r in revs]} "
        f"partitions={[r.get('paper_ids') for r in revs]}"
    )
    print("SUCCESS:RES-0076-probe2 partition-and-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
