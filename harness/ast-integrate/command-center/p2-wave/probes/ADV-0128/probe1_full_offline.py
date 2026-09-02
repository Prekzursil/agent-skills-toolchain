#!/usr/bin/env python3
"""Probe 1: classify each remote path fully offline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.ARTIFACT_REL
LEGAL = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0128-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if H.SENTINEL not in text or H.COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0128-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0128-probe1 self-declared {st}")
        return 1

    live = H.run_offline_campaign()
    c = live["controls"]
    if not c["online_paths_succeed"]:
        print("FAILED:ADV-0128-probe1 online control failed")
        return 1
    silent = set(c["naive_offline_silent_success_paths"])
    labelled = set(c["contract_offline_labelled_paths"])
    if silent != set(H.PATHS):
        print("FAILED:ADV-0128-probe1 expected silent success on all naive paths", silent)
        return 1
    if labelled != set(H.PATHS):
        print("FAILED:ADV-0128-probe1 expected labelled cache on contract paths", labelled)
        return 1
    if not c["unlabelled_cache_detector_fires"]:
        print("FAILED:ADV-0128-probe1 unlabelled-cache detector did not fire")
        return 1
    if not c["labelled_cache_not_presented_as_live"]:
        print("FAILED:ADV-0128-probe1 labelled cache presented as live")
        return 1
    if not c["empty_contract_explicit"]:
        print("FAILED:ADV-0128-probe1 empty contract was not explicit")
        return 1
    if not c["fixture_loopback_only"]:
        print("FAILED:ADV-0128-probe1 fixture was not loopback-only")
        return 1

    art_rows = {
        t["id"]: t["verdict"]
        for t in (doc.get("enumerated_targets") or doc.get("enumerated_targets") or [])
        if t.get("id") in H.PATHS
    }
    live_class = {
        r.get("path_id") or r.get("path_id"): H.classify(r)
        for r in live["offline_naive"]
    }
    for path_id in H.PATHS:
        if live_class.get(path_id) != "silent-success":
            print(f"FAILED:ADV-0128-probe1 {path_id} class {live_class.get(path_id)}")
            return 1
        verdict = art_rows.get(path_id)
        if verdict not in LEGAL:
            print(f"FAILED:ADV-0128-probe1 illegal verdict {path_id} {verdict}")
            return 1
        if verdict not in {"CONFIRMED", "PARTIAL"}:
            print(f"FAILED:ADV-0128-probe1 {path_id} verdict {verdict} want CONFIRMED/PARTIAL")
            return 1

    summary = {
        "probe": "probe1-full-offline",
        "unit_id": H.UNIT,
        "paths": list(H.PATHS),
        "online_ok": True,
        "naive_silent": sorted(silent),
        "contract_labelled": sorted(labelled),
        "detector_fires": True,
        "target_verdicts": art_rows,
        "live_classifications": live_class,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:ADV-0128-probe1 full-offline silent unlabelled cache on all paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
