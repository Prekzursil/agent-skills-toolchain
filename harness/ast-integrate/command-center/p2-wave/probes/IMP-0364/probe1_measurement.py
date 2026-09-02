#!/usr/bin/env python3
"""Named probe 1: per-preset stability rates published, including unflattering ones.

Recomputes rates from the recorded runs (independent of the summary fields) and
refuses a pack that only publishes 100 percent stability.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "council"))

import stability as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0364.json"
UNIT = "IMP-0364"


def _recompute(row: dict) -> dict:
    keys = [str(r["decision"]) for r in row["runs"]]
    n = len(keys)
    counts = Counter(keys)
    modal_n = counts.most_common(1)[0][1]
    return {
        "n": n,
        "stability_rate": modal_n / n,
        "decision_change_rate": 1.0 - (modal_n / n),
        "decision_counts": dict(counts),
    }


def main() -> int:
    report = S.measure_pack(n=S.MIN_N)
    rows = {r["preset_id"]: r for r in report["presets"]}
    if len(rows) < 3:
        print(f"FAILED:{UNIT}-probe1 preset_count={len(rows)} want>=3")
        return 1
    if report["n"] < S.MIN_N:
        print(f"FAILED:{UNIT}-probe1 n={report['n']} want>={S.MIN_N}")
        return 1

    published = []
    for pid, row in rows.items():
        if int(row["n"]) < S.MIN_N:
            print(f"FAILED:{UNIT}-probe1 {pid} n={row['n']} want>={S.MIN_N}")
            return 1
        live = _recompute(row)
        if abs(live["stability_rate"] - float(row["stability_rate"])) > 1e-12:
            print(f"FAILED:{UNIT}-probe1 {pid} summary/stability mismatch")
            return 1
        if abs(live["decision_change_rate"] - float(row["decision_change_rate"])) > 1e-12:
            print(f"FAILED:{UNIT}-probe1 {pid} change-rate mismatch")
            return 1
        published.append(
            {
                "preset_id": pid,
                "n": row["n"],
                "stability_rate": row["stability_rate"],
                "decision_change_rate": row["decision_change_rate"],
                "mean_reported_confidence": row["mean_reported_confidence"],
                "majority_re_runs_differ": row["majority_re_runs_differ"],
            }
        )

    rates = [r["stability_rate"] for r in published]
    if min(rates) >= 1.0:
        print(f"FAILED:{UNIT}-probe1 unflattering rates hidden; all stability_rate=1.0")
        return 1
    if not report["unflattering_published"]:
        print(f"FAILED:{UNIT}-probe1 unflattering_published is false")
        return 1

    unstable = rows.get(S.UNSTABLE_PRESET_ID)
    if unstable is None:
        print(f"FAILED:{UNIT}-probe1 missing {S.UNSTABLE_PRESET_ID}")
        return 1
    if not unstable["majority_re_runs_differ"]:
        print(f"FAILED:{UNIT}-probe1 overclaim preset is not majority-unstable")
        return 1
    if float(unstable["mean_reported_confidence"]) < S.HIGH_CONFIDENCE:
        print(f"FAILED:{UNIT}-probe1 overclaim preset is not high-confidence")
        return 1
    kinds = {d["kind"] for d in report["disagreements"] if d.get("preset_id") == S.UNSTABLE_PRESET_ID}
    if "high-confidence-majority-change" not in kinds:
        print(f"FAILED:{UNIT}-probe1 disagreement not listed for {S.UNSTABLE_PRESET_ID}")
        print(json.dumps(report["disagreements"], indent=2, sort_keys=True)[:2000])
        return 1

    unflat = rows.get(S.UNFLATTERING_PRESET_ID)
    if unflat is None or float(unflat["stability_rate"]) >= 1.0:
        print(f"FAILED:{UNIT}-probe1 {S.UNFLATTERING_PRESET_ID} not published unflattering")
        return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("unit_id") != UNIT:
            print(f"FAILED:{UNIT}-probe1 receipt unit_id {doc.get('unit_id')}")
            return 1
        if "SUCCESS:IMP-0364" not in json.dumps(doc):
            print(f"FAILED:{UNIT}-probe1 sentinel absent")
            return 1
        recorded = (doc.get("measurement") or {}).get("stability_rates") or {}
        for pid, rate in report["stability_rates"].items():
            if pid not in recorded:
                print(f"FAILED:{UNIT}-probe1 receipt missing rate for {pid}")
                return 1
            if abs(float(recorded[pid]) - float(rate)) > 1e-12:
                print(f"FAILED:{UNIT}-probe1 receipt rate drift {pid}")
                return 1

    out = {
        "probe": "probe1-measurement",
        "unit_id": UNIT,
        "n": report["n"],
        "preset_count": report["preset_count"],
        "stability_rates": report["stability_rates"],
        "decision_change_rates": report["decision_change_rates"],
        "disagreement_count": len(report["disagreements"]),
        "high_confidence_majority_change": report["high_confidence_majority_change"],
        "unflattering_published": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    for row in published:
        print(
            f"preset {row['preset_id']} n={row['n']} "
            f"stability={row['stability_rate']:.3f} "
            f"change={row['decision_change_rate']:.3f} "
            f"confidence={row['mean_reported_confidence']:.3f}"
        )
    print("SUCCESS:IMP-0364-probe1 per-preset stability rates including unflattering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
