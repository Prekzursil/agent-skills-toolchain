#!/usr/bin/env python3
"""Probe 2: both-states mutation — destructive rollback must turn the test red.

Mechanically different from probe 1 (inventory equality on additive restore):
this probe runs the SAME preservation assertion against (a) additive restore
and (b) a mutated wholesale snapshot restore. Additive must stay green;
wholesale must fire (planted user-data gone, set difference nonempty).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import rehearse  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0474.json"
SENTINEL = "SENTINEL:IMP-0474:ROLLBACK-NON-DESTRUCTIVE"


def _run(mode: str) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"imp0474-p2-{mode[:3]}-") as tmp:
        return rehearse(Path(tmp), mode=mode)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0474-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0474-probe2 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0474-probe2 sentinel-absent")
        return 1

    good = _run("additive")
    bad = _run("wholesale-destructive")

    good_holds = bool(good.get("preservation_holds"))
    bad_holds = bool(bad.get("preservation_holds"))
    good_empty = bool((good.get("rollback") or {}).get("set_difference", {}).get("empty"))
    bad_empty = bool((bad.get("rollback") or {}).get("set_difference", {}).get("empty"))
    bad_planted = bool((bad.get("planted") or {}).get("survived"))
    bad_cmd_missing = list(
        ((bad.get("rollback") or {}).get("set_difference") or {}).get(
            "commands_present_before_absent_after"
        )
        or []
    )
    bad_data_missing = list(
        ((bad.get("rollback") or {}).get("set_difference") or {}).get(
            "user_data_present_before_absent_after"
        )
        or []
    )

    silent_on_good = good_holds and good_empty
    fired_on_bad = (not bad_holds) and (not bad_empty) and (not bad_planted)
    both_states = silent_on_good and fired_on_bad

    out = {
        "probe": "probe2-mutation",
        "unit_id": "IMP-0474",
        "good_mode": "additive",
        "bad_mode": "wholesale-destructive",
        "good_rehearsal_executed": good.get("rehearsal_executed") is True,
        "bad_rehearsal_executed": bad.get("rehearsal_executed") is True,
        "silent_on_good": silent_on_good,
        "fired_on_bad": fired_on_bad,
        "both_states": both_states,
        "good_preservation_holds": good_holds,
        "bad_preservation_holds": bad_holds,
        "bad_planted_survived": bad_planted,
        "bad_commands_absent_after": bad_cmd_missing,
        "bad_user_data_absent_after": bad_data_missing,
        "pass": False,
    }

    recorded = ((doc.get("negative_controls") or [{}])[0]) if doc.get("negative_controls") else {}
    if isinstance(doc.get("negative_controls"), list) and doc["negative_controls"]:
        recorded = doc["negative_controls"][0]

    if not out["good_rehearsal_executed"] or not out["bad_rehearsal_executed"]:
        print("FAILED:IMP-0474-probe2 mutation rehearsal not executed")
        print(json.dumps(out, indent=2, default=str)[:3000])
        return 1
    if not silent_on_good:
        print("FAILED:IMP-0474-probe2 additive restore did not stay green")
        print(json.dumps(out, indent=2, default=str)[:4000])
        return 1
    if not fired_on_bad:
        print("FAILED:IMP-0474-probe2 wholesale mutation did not turn red")
        print(json.dumps(out, indent=2, default=str)[:4000])
        return 1
    if "user-authored.md" not in " ".join(bad_cmd_missing) and not any(
        "user-authored" in p for p in bad_cmd_missing
    ):
        print("FAILED:IMP-0474-probe2 mutation did not drop user-authored command")
        print(json.dumps(out, indent=2, default=str)[:3000])
        return 1
    if not any("planted-IMP-0474" in p for p in bad_data_missing):
        print("FAILED:IMP-0474-probe2 mutation did not drop planted user-data")
        print(json.dumps(out, indent=2, default=str)[:3000])
        return 1
    if recorded.get("fired_on_bad_state") is not True:
        print("FAILED:IMP-0474-probe2 artifact missing fired_on_bad_state")
        return 1
    if recorded.get("silent_on_good_state") is not True:
        print("FAILED:IMP-0474-probe2 artifact missing silent_on_good_state")
        return 1

    out["pass"] = True
    print(json.dumps(out, sort_keys=True))
    print(
        "silent_on_good=True fired_on_bad=True both_states=True "
        f"bad_cmd_missing={len(bad_cmd_missing)} "
        f"bad_data_missing={len(bad_data_missing)}"
    )
    print("SUCCESS:IMP-0474-probe2 destructive mutation turns preservation red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
