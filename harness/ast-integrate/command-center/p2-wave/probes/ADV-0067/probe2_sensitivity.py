#!/usr/bin/env python3
"""Probe 2: per-term sensitivity — mechanically different from package compare."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402

ART = C.ART


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0067-probe2 {msg}")
    return 1


def main() -> int:
    live = C.sensitivity_analysis()
    pop = live["control_popularity_silent_on_good"]
    summary = {
        "probe": live["probe"],
        "unit_id": live["unit_id"],
        "baseline_zero_score": live["baseline_zero_score"],
        "from_zero": [
            {"term": r["term"], "marginal_from_zero": r["marginal_from_zero"]}
            for r in live["from_zero"]
        ],
        "gamed_ablation": [
            {"term": r["term"], "marginal_on_gamed": r["marginal_on_gamed"]}
            for r in live["gamed_ablation"]
        ],
        "highest_marginal_term": live["highest_marginal_term"],
        "gamed_highest_ablation_term": live["gamed_highest_ablation_term"],
        "popularity_control": pop,
        "independent_of_probe1_packages": live["independent_of_probe1_packages"],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if C.CATALOG_SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "ADV-0067":
        return fail(f"unit_id={doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    rec = doc.get("probe2_sensitivity") or {}
    rec_rows = {row["term"]: row for row in rec.get("from_zero") or [] if isinstance(row, dict)}
    if len(rec_rows) != len(C.TERM_IDS):
        return fail(f"artifact missing sensitivity rows n={len(rec_rows)}")
    for row in live["from_zero"]:
        got = rec_rows.get(row["term"]) or {}
        if abs(float(got.get("marginal_from_zero", -1)) - row["marginal_from_zero"]) > 1e-6:
            return fail(f"marginal drifted for {row['term']}")
        if abs(float(got.get("weight", -1)) - row["weight"]) > 1e-6:
            return fail(f"weight drifted for {row['term']}")

    if rec.get("highest_marginal_term") != live["highest_marginal_term"]:
        return fail("highest_marginal_term drifted")
    if not pop["silent_on_good_state"]:
        return fail("popularity control not silent on good")
    if not pop["fired_on_bad_state"]:
        return fail("popularity mutant did not fire")
    if live["baseline_zero_score"] != 0.0:
        return fail(f"zero vector scored {live['baseline_zero_score']}")

    # Independent re-derivation: cheapest gamed term from ablation, not probe1 prose.
    drop = live["gamed_ablation"]
    if not drop:
        return fail("no ablation rows")
    top = drop[0]["term"]
    if drop[0]["marginal_on_gamed"] <= 0:
        return fail("no positive gamed ablation")
    rec_drop_top = rec.get("gamed_highest_ablation_term")
    if rec_drop_top != top:
        return fail(f"ablation top drifted rec={rec_drop_top} live={top}")

    print(
        f"zero_baseline={live['baseline_zero_score']} "
        f"top_from_zero={live['highest_marginal_term']} "
        f"gamed_ablation_top={top}"
    )
    print("SUCCESS:ADV-0067-probe2 per-term sensitivity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
