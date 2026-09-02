#!/usr/bin/env python3
"""Probe 1: uncancelled publish + 200 cancelled atomic renders.

Signal (a): dest parse is COMPLETE old after every cancel; never PARTIAL.
Signal (b): scavenge leaves zero tmp files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

ART = REPO / H.OUT_REL
SENTINEL = "SUCCESS:TST-0156"


def main() -> int:
    live = H.run_campaign(include_direct=False)
    atomic = live["atomic"]
    print(
        json.dumps(
            {
                "probe": "probe1-cancel-atomic",
                "unit_id": H.UNIT,
                "pass": live["pass"],
                "uncancelled_ok": live["uncancelled_ok"],
                "atomic_ok": live["atomic_ok"],
                "cancel_n": live["cancel_n"],
                "after_partial": atomic["after_partial"],
                "after_complete_still_old": atomic["after_complete_still_old"],
                "orphans_remaining": atomic["orphans_remaining"],
                "orphans_seen_before_scavenge": atomic["orphans_seen_before_scavenge"],
            },
            sort_keys=True,
        )
    )
    if not live["uncancelled_ok"]:
        print("FAILED:TST-0156-probe1 uncancelled atomic render did not publish")
        return 1
    if atomic["after_partial"] != 0:
        print(
            f"FAILED:TST-0156-probe1 partial reads after atomic cancel "
            f"n={atomic['after_partial']}"
        )
        return 1
    if atomic["after_complete_still_old"] != live["cancel_n"]:
        print("FAILED:TST-0156-probe1 dest did not remain the complete old cache")
        return 1
    if atomic["orphans_remaining"] != 0:
        print("FAILED:TST-0156-probe1 leftover tmp files after scavenge")
        return 1
    if atomic["orphans_seen_before_scavenge"] < 1:
        print("FAILED:TST-0156-probe1 never observed a tmp to scavenge; cancel missed mid-write")
        return 1
    if not live["atomic_ok"]:
        print("FAILED:TST-0156-probe1 atomic campaign not ok")
        return 1
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:TST-0156-probe1 receipt self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:TST-0156-probe1 sentinel absent from receipt")
            return 1
        recorded = ((doc.get("campaign") or {}).get("atomic") or {})
        if recorded:
            rec_partial = recorded.get("after_partial")
            if rec_partial is None or int(rec_partial) != 0:
                print("FAILED:TST-0156-probe1 receipt atomic.after_partial drift")
                return 1
    print(
        f"uncancelled_ok={live['uncancelled_ok']} "
        f"partial={atomic['after_partial']} "
        f"old_complete={atomic['after_complete_still_old']}/{live['cancel_n']} "
        f"orphans_left={atomic['orphans_remaining']} "
        f"tmps_seen={atomic['orphans_seen_before_scavenge']}"
    )
    print("SUCCESS:TST-0156-probe1 cancel-atomic 200 zero partials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
