#!/usr/bin/env python3
"""Probe 1: 100 no-op iterations, distribution, per-stage attribution."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    CATALOG_SENTINEL,
    OUT_REL,
    REPO,
    STAGES,
    compact,
    run_campaign,
)


def main() -> int:
    art = REPO / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        print("FAILED:TST-0305-probe1 artifact missing")
        return 1
    text = art.read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in text:
        print("FAILED:TST-0305-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0305":
        print("FAILED:TST-0305-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0305-probe1 self-declared", doc.get("state"))
        return 1

    live = run_campaign()
    print(json.dumps(compact(live), sort_keys=True, default=str))

    if not live.get("ok"):
        print("FAILED:TST-0305-probe1 live campaign ok=false")
        return 1
    noop = live["noop"]
    if noop["n"] != 100:
        print("FAILED:TST-0305-probe1 noop n", noop["n"])
        return 1
    if len(live["noop_totals_ms"]) != 100:
        print("FAILED:TST-0305-probe1 totals length", len(live["noop_totals_ms"]))
        return 1
    missing = [s for s in STAGES if s not in noop["stages"]]
    if missing:
        print("FAILED:TST-0305-probe1 stages missing", missing)
        return 1
    for name in STAGES:
        n = noop["stages"][name]["n"]
        if n != 100:
            print("FAILED:TST-0305-probe1 stage n", name, n)
            return 1
    if float(live["overhead_ms"]) <= 0:
        print("FAILED:TST-0305-probe1 overhead_ms not positive", live["overhead_ms"])
        return 1
    if not (0 < float(live["fraction_of_p50_real"]) < 1):
        print("FAILED:TST-0305-probe1 fraction", live["fraction_of_p50_real"])
        return 1
    dom = (live.get("dominating_stage") or {}).get("stage")
    if dom not in STAGES:
        print("FAILED:TST-0305-probe1 dominating stage", dom)
        return 1

    art_over = doc.get("overhead") or {}
    if int((art_over.get("noop") or {}).get("n") or 0) != 100:
        print("FAILED:TST-0305-probe1 artifact noop n", art_over.get("noop"))
        return 1
    art_stages = ((art_over.get("noop") or {}).get("stages") or {})
    if any(s not in art_stages for s in STAGES):
        print("FAILED:TST-0305-probe1 artifact stages", sorted(art_stages))
        return 1
    art_total = (art_over.get("noop") or {}).get("total") or {}
    if "p50_ms" not in art_total:
        print("FAILED:TST-0305-probe1 artifact missing total p50")
        return 1

    print(
        f"noop_n=100 overhead_ms={live['overhead_ms']} "
        f"fraction={live['fraction_of_p50_real']:.6f} "
        f"dominating={dom}"
    )
    print("SUCCESS:TST-0305-probe1 noop distribution + stage attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
