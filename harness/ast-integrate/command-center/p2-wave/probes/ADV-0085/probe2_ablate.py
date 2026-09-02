#!/usr/bin/env python3
"""Probe 2: per-term ablation — mechanically different from ranking."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402

ART = C.ART


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0085-probe2 {msg}")
    return 1


def main() -> int:
    live = C.ablation_bundle()
    loc = live["control_length_mutant"]
    summary = {
        "probe": live["probe"],
        "unit_id": live["unit_id"],
        "independent_of_probe1_verdicts": live["independent_of_probe1_verdicts"],
        "baseline_zero_vector_check": live["baseline_zero_vector_check"],
        "baseline_inversion_pairs": live["baseline_inversion_pairs"],
        "localised_exploits": live["localised_exploits"],
        "clears_all_inversions_terms": live["clears_all_inversions_terms"],
        "from_term_drop": [
            {
                "term": r["term"],
                "weight": r["weight"],
                "remaining_exploits": r["remaining_exploits"],
                "exploits_restored": r["exploits_restored"],
                "clears_all_inversions": r["clears_all_inversions"],
            }
            for r in live["from_term_drop"]
        ],
        "length_control": loc,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if C.CATALOG_SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "ADV-0085":
        return fail(f"unit_id={doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    rec = doc.get("probe2_ablation") or {}
    rec_rows = {row["term"]: row for row in rec.get("from_term_drop") or [] if isinstance(row, dict)}
    if len(rec_rows) != len(C.TERM_IDS):
        return fail(f"artifact missing ablation rows n={len(rec_rows)}")
    for row in live["from_term_drop"]:
        got = rec_rows.get(row["term"]) or {}
        if abs(float(got.get("weight", -1)) - row["weight"]) > 1e-6:
            return fail(f"weight drifted for {row['term']}")
        if list(got.get("remaining_exploits") or []) != list(row["remaining_exploits"]):
            return fail(f"remaining_exploits drifted for {row['term']}")
        rec_ranked = {item["label"]: item for item in got.get("ranked") or [] if isinstance(item, dict)}
        for item in row["ranked"]:
            rec_total = float((rec_ranked.get(item["label"]) or {}).get("total", -1))
            if abs(rec_total - float(item["total"])) > 1e-6:
                return fail(f"ablated total drifted {row['term']}/{item['label']}")

    rec_loc = rec.get("localised_exploits") or []
    if len(rec_loc) != len(live["localised_exploits"]):
        return fail("localised_exploits drifted")
    if rec.get("clears_all_inversions_terms") != live["clears_all_inversions_terms"]:
        return fail("clears_all_inversions_terms drifted")
    if not loc["silent_on_good_state"]:
        return fail("length control not silent on good")
    if not loc["fired_on_bad_state"]:
        return fail("length mutant did not fire")
    if live["baseline_zero_vector_check"] != 0.0:
        return fail(f"zero vector scored {live['baseline_zero_vector_check']}")

    top = live["localised_exploits"]
    print(
        f"zero_baseline={live['baseline_zero_vector_check']} "
        f"localised={[(r['degenerate'], r.get('unique_term') or r.get('depends_on_terms')) for r in top]}"
    )
    print("SUCCESS:ADV-0085-probe2 per-term ablation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
