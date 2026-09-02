#!/usr/bin/env python3
"""Probe 2: perfectly calibrated fixture scores at its optimum; Brier recomputed."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from bands import POINT_P, WRITTEN_INTERVALS  # noqa: E402
from fixtures import CALIBRATED_COUNTS  # noqa: E402

UNIT = "SYN-0035"
ART = REPO / "command-center/synthesis/SYN-0035.calibration-report.json"
SENTINEL = (
    "SUCCESS:SYN-0035 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every band row states n "
    "and the unadjudicated count is reported separately. Any other terminal "
    "state is FAILED:SYN-0035 <classification> with the diagnostic tail attached."
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def independent_brier(rows: list[dict]) -> float | None:
    total = 0.0
    n = 0
    for r in rows:
        v = str(r.get("confirmer_verdict") or "").upper()
        if v not in {"CONFIRMED", "REFUTED"}:
            continue
        band = r.get("band")
        if band not in POINT_P:
            return None
        y = 1.0 if v == "CONFIRMED" else 0.0
        total += (POINT_P[band] - y) ** 2
        n += 1
    if n < 1:
        return None
    return total / n


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    planted = list(doc.get("planted_items") or [])
    if len(planted) < 20:
        return fail(f"planted_items={len(planted)}")

    perfect = [r for r in planted if r.get("set_id") == "synthetic-perfect"]
    una = [r for r in planted if str(r.get("confirmer_verdict")).upper() == "NOT-CHECKED"]
    if not una:
        return fail("no NOT-CHECKED plants")
    for r in una:
        if r.get("set_id") != "synthetic-unadjudicated":
            return fail(f"unadjudicated set_id={r.get('set_id')}")

    for band, (n_hit, n_miss) in CALIBRATED_COUNTS.items():
        hits = [
            r
            for r in perfect
            if r.get("band") == band and r.get("confirmer_verdict") == "CONFIRMED"
        ]
        misses = [
            r
            for r in perfect
            if r.get("band") == band and r.get("confirmer_verdict") == "REFUTED"
        ]
        if len(hits) != n_hit or len(misses) != n_miss:
            return fail(f"{band} hits={len(hits)} misses={len(misses)}")
        rate = len(hits) / (len(hits) + len(misses))
        lo, hi = WRITTEN_INTERVALS[band]
        if not (lo <= rate <= hi):
            return fail(f"{band} rate={rate} outside {lo}-{hi}")

    recomputed = independent_brier(perfect)
    published = (doc.get("proper_score") or {}).get("synthetic_perfect") or {}
    pub_val = published.get("value")
    if recomputed is None or pub_val is None:
        return fail("brier missing")
    if abs(float(pub_val) - float(recomputed)) > 1e-12:
        return fail(f"brier published={pub_val} independent={recomputed}")

    # Optimum: every synthetic band inside its written interval, and Brier
    # matches the independent sum. A scorer that always returns 0 fails
    # unless the fixture is degenerate; CALIBRATED_COUNTS is not degenerate.
    if float(recomputed) <= 0:
        return fail("brier is zero; fixture is not a mixed-outcome control")

    syn_bands = doc.get("bands") or []
    for row in syn_bands:
        band = row.get("band")
        if band not in CALIBRATED_COUNTS:
            return fail(f"unknown band {band}")
        if not row.get("inside_nominal_interval"):
            return fail(f"{band} not inside written interval")
        if list(row.get("nominal_interval")) != list(WRITTEN_INTERVALS[band]):
            return fail(f"{band} interval drifted from written definition")
        if row.get("n") != sum(CALIBRATED_COUNTS[band]):
            return fail(f"{band} n folded unadjudicated or dropped hits")

    tests = {t["id"]: t.get("result") for t in (doc.get("tests") or [])}
    want = "synthetic_control_perfectly_calibrated_scores_at_optimum"
    if tests.get(want) != "PASS":
        return fail(f"artifact test {want}={tests.get(want)}")

    matrix = doc.get("confusion_matrix") or {}
    tp = int(matrix.get("true_positive") or 0)
    tn = int(matrix.get("true_negative") or 0)
    fp = int(matrix.get("false_positive") or 0)
    fn = int(matrix.get("false_negative") or 0)
    want_tp = sum(h for h, _ in CALIBRATED_COUNTS.values())
    want_tn = sum(m for _, m in CALIBRATED_COUNTS.values())
    if (tp, tn, fp, fn) != (want_tp, want_tn, 0, 0):
        return fail(f"matrix {(tp, fp, fn, tn)} want tp={want_tp} tn={want_tn} fp=0 fn=0")

    fpr = doc.get("false_pass_rate") or {}
    if fpr.get("numerator") != 0 or fpr.get("denominator") != want_tn:
        return fail(f"false_pass_rate {fpr}")

    print(
        json.dumps(
            {
                "independent_brier": recomputed,
                "published_brier": pub_val,
                "unadjudicated_plants": len(una),
                "perfect_n": len(perfect),
                "all_bands_inside": True,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT}-probe2 synthetic control at optimum; brier recomputed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
