#!/usr/bin/env python3
"""Probe 1: both shells consulted; they disagree on bash; first-wins is wrong."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0461.json"
SENTINEL = "SENTINEL:IMP-0461:INTERPRETER-EXPLICIT"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    run = S.run_scenario()
    print(json.dumps(
        {
            "shells_disagree": run["table"]["shells_disagree"],
            "both_consulted": run["table"]["both_consulted"],
            "msys_path": run["msys_path"],
            "system_path": run["system_path"],
            "msys_family": run["msys_family"],
            "system_family": run["system_family"],
            "first_wins_hides_the_other": run["first_wins_control"][
                "first_wins_hides_the_other"
            ],
            "bare_refused": run["bare_refused"],
            "family_required_when_disagree": run["family_required_when_disagree"],
        },
        sort_keys=True,
    ))
    if not run["ok"]:
        print("FAILED:IMP-0461-probe1 scenario did not pass")
        return 1
    if run["msys_path"] == run["system_path"]:
        print("FAILED:IMP-0461-probe1 shells reported the same bash path")
        return 1
    if run["msys_family"] != "msys" or run["system_family"] != "wsl-system":
        print("FAILED:IMP-0461-probe1 classification collapsed the two bashes")
        return 1
    if not run["first_wins_control"]["first_wins_hides_the_other"]:
        print("FAILED:IMP-0461-probe1 concatenated PATH control did not hide one bash")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0461-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:IMP-0461-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0461-probe1 sentinel-absent")
        return 1
    meas = doc.get("measurement") or {}
    if meas.get("msys_path") != run["msys_path"]:
        print("FAILED:IMP-0461-probe1 receipt msys_path != live")
        return 1
    if meas.get("system_path") != run["system_path"]:
        print("FAILED:IMP-0461-probe1 receipt system_path != live")
        return 1
    if meas.get("shells_disagree") is not True:
        print("FAILED:IMP-0461-probe1 receipt did not record shells_disagree")
        return 1
    print(
        f"disagree={run['table']['shells_disagree']} "
        f"first_wins_hides={run['first_wins_control']['first_wins_hides_the_other']}"
    )
    print("SUCCESS:IMP-0461-probe1 both-shell bash disagreement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
