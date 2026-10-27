#!/usr/bin/env python3
"""Probe 1: every REPAIR candidate and REPAIRED-route blueprint is reproduced red.

Re-runs intake live. Does not repair any subject. Requires the artifact to
carry command, expected, observed, verbatim output, and red_test_kept.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import intake as I  # noqa: E402
import subjects as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0086-repair-intake-baselines.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0086-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0086" not in text:
        print("FAILED:WFA-0086-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0086-probe1 self-declared {doc.get('state')}")
        return 1
    if doc.get("unit_id") != "WFA-0086" or doc.get("record_type") != "RepairRecord":
        print("FAILED:WFA-0086-probe1 identity")
        return 1

    live = I.run_intake()
    if not live["controls"].get("all_passed"):
        print("FAILED:WFA-0086-probe1 live intake controls")
        print(json.dumps(live["controls"], indent=2, sort_keys=True))
        return 1

    art_rows = [r for r in (doc.get("records") or []) if isinstance(r, dict)]
    live_rows = live["records"]
    if len(art_rows) != 28 or len(live_rows) != 28:
        print(f"FAILED:WFA-0086-probe1 count art={len(art_rows)} live={len(live_rows)}")
        return 1

    art_by = {r["id"]: r for r in art_rows}
    live_by = {r["id"]: r for r in live_rows}
    if set(art_by) != set(live_by):
        print("FAILED:WFA-0086-probe1 id set drift")
        print(" missing", sorted(set(live_by) - set(art_by)))
        print(" extra", sorted(set(art_by) - set(live_by)))
        return 1

    repair_ids = [s[0] for s in S.REPAIR_CANDIDATES]
    blueprint_ids = [s[0] for s in S.REPAIRED_ROUTE]
    if len(repair_ids) != 15 or len(blueprint_ids) != 13:
        print("FAILED:WFA-0086-probe1 catalog cardinality")
        return 1

    for sid in repair_ids + blueprint_ids:
        a = art_by[sid]
        lv = live_by[sid]
        if not a.get("red_reproduced") or not lv.get("red_reproduced"):
            print(f"FAILED:WFA-0086-probe1 not red {sid}")
            return 1
        if not a.get("red_test_kept") or not lv.get("red_test_kept"):
            print(f"FAILED:WFA-0086-probe1 red not kept {sid}")
            return 1
        if not a.get("command") or a.get("command") != lv.get("command"):
            print(f"FAILED:WFA-0086-probe1 command drift {sid}")
            return 1
        if not a.get("expected") or not a.get("observed"):
            print(f"FAILED:WFA-0086-probe1 expected/observed missing {sid}")
            return 1
        if not str(a.get("verbatim_output") or "").strip():
            print(f"FAILED:WFA-0086-probe1 verbatim empty {sid}")
            return 1
        if a.get("repair_may_begin") is not True or lv.get("repair_may_begin") is not True:
            print(f"FAILED:WFA-0086-probe1 repair_may_begin {sid}")
            return 1
        if a.get("classification") != "REPAIR":
            print(f"FAILED:WFA-0086-probe1 classification {sid}={a.get('classification')}")
            return 1

    nored = live["control_records"]["no_red"]
    if nored.get("repair_may_begin") or nored.get("red_reproduced"):
        print("FAILED:WFA-0086-probe1 no-red control leaked")
        return 1

    sm = doc.get("summary") or {}
    if sm.get("repair_candidates") != 15 or sm.get("repaired_route_blueprints") != 13:
        print("FAILED:WFA-0086-probe1 summary cardinality", sm)
        return 1
    if sm.get("red_reproduced") != 28 or sm.get("repair_may_begin_true") != 28:
        print("FAILED:WFA-0086-probe1 summary red", sm)
        return 1

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    blocker = tests.get("T-WINDOWS-REGISTRY-BLOCKER") or {}
    if blocker.get("kept_as_regression") is not True:
        print("FAILED:WFA-0086-probe1 windows blocker not kept")
        return 1
    if not live["windows_source"]["registry_present"] and blocker.get("result") != "RED":
        print("FAILED:WFA-0086-probe1 absent registry not captured red")
        return 1

    out = {
        "probe": "probe1-red-per-candidate",
        "unit_id": "WFA-0086",
        "repair_n": 15,
        "blueprint_n": 13,
        "red_reproduced": 28,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("red=28/28 repair_may_begin=28 no-red refused")
    print("SUCCESS:WFA-0086-probe1 each candidate reproduced red before repair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
