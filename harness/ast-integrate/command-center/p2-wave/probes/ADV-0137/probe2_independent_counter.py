#!/usr/bin/env python3
"""Probe 2: independent counter reproduces the artifact histogram.

Uses harvest_scan.py (string-aware work_units scan). Does not import
harvest_json.py — that is counter A, used by emit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from counting_rule import gini  # noqa: E402
from harvest_scan import harvest as harvest_scan  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0137-premise-concentration.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:ADV-0137-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    scanned = harvest_scan(REPO)
    art_hist = {
        row["source"]: row["direct_units"]
        for row in (doc.get("histogram") or [])
        if isinstance(row, dict)
    }
    live = scanned["histogram"]
    if art_hist != live:
        only_art = sorted(set(art_hist) - set(live))[:8]
        only_live = sorted(set(live) - set(art_hist))[:8]
        mismatched = [
            k
            for k in sorted(set(art_hist) & set(live))
            if art_hist[k] != live[k]
        ][:8]
        print(
            "FAILED:ADV-0137-probe2 histogram mismatch "
            f"only_art={only_art} only_live={only_live} mismatched={mismatched}"
        )
        return 1
    ic = doc.get("independent_counter") or {}
    if ic.get("histograms_identical") is not True:
        print("FAILED:ADV-0137-probe2 artifact did not record identical histograms")
        return 1
    if ic.get("family_a") == ic.get("family_b"):
        print("FAILED:ADV-0137-probe2 families not distinct")
        return 1
    if ic.get("family_b") != scanned["family"]:
        print(f"FAILED:ADV-0137-probe2 family_b={ic.get('family_b')}")
        return 1
    if ic.get("mechanical_families_differ") is not True:
        print("FAILED:ADV-0137-probe2 mechanical_families_differ")
        return 1
    live_g = gini(live.values())
    art_g = (doc.get("gini") or {}).get("value")
    if art_g is None or abs(float(art_g) - live_g) > 1e-6:
        print(f"FAILED:ADV-0137-probe2 gini art={art_g} live={live_g}")
        return 1
    if scanned["n_units"] != (doc.get("catalog_inputs") or {}).get("n_work_units"):
        print("FAILED:ADV-0137-probe2 n_units mismatch")
        return 1
    if "SUCCESS:ADV-0137" not in json.dumps(doc):
        print("FAILED:ADV-0137-probe2 sentinel absent")
        return 1
    top = (doc.get("premises_top5") or [])[:5]
    if len(top) != 5:
        print("FAILED:ADV-0137-probe2 top5 missing")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe2-independent-counter",
                "unit_id": "ADV-0137",
                "family": scanned["family"],
                "n_units": scanned["n_units"],
                "n_sources": len(live),
                "gini": round(live_g, 8),
                "top_source": top[0].get("source"),
                "top_direct": top[0].get("direct_units"),
                "histograms_identical": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:ADV-0137-probe2 independent scan reproduced histogram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
