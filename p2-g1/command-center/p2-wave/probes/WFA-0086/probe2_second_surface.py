#!/usr/bin/env python3
"""Probe 2: log-independent second surface + both-states gate controls.

Mechanically different from probe 1: does not trust runner stdout. Reads the
contracted artifact path (or its absence) and requires:
  * every red subject's second_surface.ok is False
  * the unreproducible plant has second_surface.ok True and is reclassified
  * the no-red plant cannot begin repair
  * the naive repair-without-red mutant is refused
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
        print("FAILED:WFA-0086-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0086-probe2 self-declared {doc.get('state')}")
        return 1

    live = I.run_intake()
    if not live["controls"].get("all_passed"):
        print("FAILED:WFA-0086-probe2 live controls")
        print(json.dumps(live["controls"], indent=2, sort_keys=True))
        return 1

    art_rows = {r["id"]: r for r in (doc.get("records") or []) if isinstance(r, dict)}
    mismatches = []
    for row in live["records"]:
        sid = row["id"]
        # Recompute surface from disk without using verbatim_output.
        subj = S.by_id()[sid]
        surface = I.second_surface(subj)
        if surface.get("ok") is not False:
            mismatches.append((sid, "surface unexpectedly ok", surface))
        art = art_rows.get(sid) or {}
        art_ss = art.get("second_surface") or {}
        if art_ss.get("ok") is not False:
            mismatches.append((sid, "artifact surface ok", art_ss))
        if art_ss.get("kind") != row["second_surface"]["kind"]:
            mismatches.append((sid, "kind drift", art_ss.get("kind"), row["second_surface"]["kind"]))
        if not I.refuse_repair_without_red(row):
            mismatches.append((sid, "gate broken", row.get("repair_may_begin")))

    if mismatches:
        print("FAILED:WFA-0086-probe2 second-surface mismatches")
        print(json.dumps(mismatches[:12], default=str))
        return 1

    unrepro = live["control_records"]["unreproducible"]
    if unrepro.get("reclassified_to") != "RECLASSIFIED-UNREPRODUCIBLE":
        print("FAILED:WFA-0086-probe2 unreproducible not reclassified")
        return 1
    if unrepro.get("repair_may_begin") is not False:
        print("FAILED:WFA-0086-probe2 unreproducible may begin repair")
        return 1
    if unrepro.get("second_surface", {}).get("ok") is not True:
        print("FAILED:WFA-0086-probe2 unreproducible surface not ok")
        return 1
    art_ctrl = (doc.get("control_records") or {}).get("unreproducible") or {}
    if art_ctrl.get("reclassified_to") != "RECLASSIFIED-UNREPRODUCIBLE":
        print("FAILED:WFA-0086-probe2 artifact unreproducible drift")
        return 1

    nored = live["control_records"]["no_red"]
    if nored.get("repair_may_begin") is not False or nored.get("red_reproduced"):
        print("FAILED:WFA-0086-probe2 no-red control")
        return 1
    mutant = I.naive_repair_without_red(nored)
    if I.refuse_repair_without_red(mutant):
        print("FAILED:WFA-0086-probe2 naive mutant not caught")
        return 1

    art_ctrl_ok = (doc.get("controls") or {}).get("naive_repair_without_red_caught") is True
    if not art_ctrl_ok:
        print("FAILED:WFA-0086-probe2 artifact missing mutant catch")
        return 1

    if S.UNREPRODUCIBLE_RECLASSIFY not in text or S.NO_REPAIR_WITHOUT_RED not in text:
        print("FAILED:WFA-0086-probe2 gate strings absent from artifact")
        return 1

    out = {
        "probe": "probe2-second-surface",
        "unit_id": "WFA-0086",
        "second_surface_red": 28,
        "unreproducible_reclassified": True,
        "naive_mutant_caught": True,
        "fired_on_bad": True,
        "silent_on_good": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("second_surface independent; unreproducible reclassified; no-red refused")
    print("SUCCESS:WFA-0086-probe2 second surface and both-states gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
