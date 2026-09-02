#!/usr/bin/env python3
"""Named probe 2: revert each fix; every mutant must go red (evidence B)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from suite import (  # noqa: E402
    ARTIFACT_REL,
    REPO,
    SENTINEL,
    load_artifact,
    platform_stable_verdicts,
    run_campaign,
    verdict_fingerprint,
)


def main() -> int:
    art = REPO / ARTIFACT_REL
    if not art.is_file() or art.stat().st_size < 200:
        print("FAILED:WFA-0092-probe2 artifact missing")
        return 1
    doc = load_artifact(REPO)
    if SENTINEL not in art.read_text(encoding="utf-8"):
        print("FAILED:WFA-0092-probe2 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="wfa0092-p2-") as td:
        live = run_campaign(Path(td))

    if not live["ok"]:
        print("FAILED:WFA-0092-probe2 campaign not ok")
        print(json.dumps({
            "baseline_green": live["baseline_green"],
            "surviving_mutants": live["surviving_mutants"],
            "independent": live["independent"],
        }, indent=2))
        return 1
    if live["surviving_mutant_count"] != 0:
        print("FAILED:WFA-0092-probe2 surviving mutants", live["surviving_mutants"])
        return 1
    if not live["independent"]:
        extras = [m for m in live["mutations"] if m["extra_red"]]
        print("FAILED:WFA-0092-probe2 mutations not independent")
        print(json.dumps(extras, indent=2)[:3000])
        return 1

    live_fp = verdict_fingerprint(live)
    art_fp = doc.get("verdict_fingerprint")
    if art_fp != live_fp:
        print("FAILED:WFA-0092-probe2 fingerprint mismatch")
        print(json.dumps({"artifact": art_fp, "live": live_fp}, indent=2))
        return 1

    art_surv = list(doc.get("surviving_mutants") or [])
    if art_surv != live["surviving_mutants"]:
        print("FAILED:WFA-0092-probe2 surviving list mismatch")
        return 1

    plat = platform_stable_verdicts(live, repeats=3)
    if not plat["same_verdicts"]:
        print("FAILED:WFA-0092-probe2 verdicts not stable across reruns")
        print(json.dumps(plat, indent=2))
        return 1

    print(json.dumps({
        "probe": "probe2-mutation-campaign",
        "unit_id": "WFA-0092",
        "mutations": len(live["mutations"]),
        "surviving_mutant_count": live["surviving_mutant_count"],
        "independent": live["independent"],
        "same_verdicts": plat["same_verdicts"],
        "verdict_fingerprint": live_fp,
        "pass": True,
    }, sort_keys=True))
    print(
        f"killed={len(live['mutations'])} survivors=0 independent={live['independent']} "
        f"same_verdicts={plat['same_verdicts']}"
    )
    print("SUCCESS:WFA-0092-probe2 mutation campaign no survivors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
