#!/usr/bin/env python3
"""Named probe 1: refusal path on 10 no-procedure skills (both-states).

Evidence B: every hand-picked no-procedure skill must return NOT-EXTRACTABLE.
A mutant that never refuses must go red on the same set.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adapter import NOT_EXTRACTABLE, extract_skill  # noqa: E402
from gold import REFUSE, skill_path  # noqa: E402
from mutants import mutant_never_refuse  # noqa: E402

ART = REPO / "command-center" / "wfa" / "WFA-0047-adapter-skill-markdown.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0047-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0047":
        print("FAILED:WFA-0047-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:WFA-0047" not in ART.read_text(encoding="utf-8"):
        print("FAILED:WFA-0047-probe1 sentinel absent")
        return 1
    if len(REFUSE) != 10:
        print(f"FAILED:WFA-0047-probe1 refuse-set size {len(REFUSE)} want 10")
        return 1

    good = []
    for rec in REFUSE:
        path = skill_path(rec["id"])
        if not path.is_file():
            print(f"FAILED:WFA-0047-probe1 missing fixture {path}")
            return 1
        got = extract_skill(path)
        if got.get("verdict") != NOT_EXTRACTABLE:
            print(f"FAILED:WFA-0047-probe1 {rec['id']} verdict={got.get('verdict')}")
            print(json.dumps(got, indent=2)[:1500])
            return 1
        if got.get("stages"):
            print(f"FAILED:WFA-0047-probe1 {rec['id']} invented stages")
            return 1
        good.append(rec["id"])

    mutant_red = []
    for rec in REFUSE:
        got = mutant_never_refuse(skill_path(rec["id"]))
        if got.get("verdict") == NOT_EXTRACTABLE:
            print(f"FAILED:WFA-0047-probe1 mutant still refused {rec['id']}")
            return 1
        mutant_red.append(rec["id"])

    if len(mutant_red) != 10:
        print("FAILED:WFA-0047-probe1 mutant both-states did not go red on all 10")
        return 1

    out = {
        "probe": "probe1-refusal",
        "unit_id": "WFA-0047",
        "refuse_n": 10,
        "adapter_all_not_extractable": True,
        "ids": good,
        "mutant_never_refuse_extracted": mutant_red,
        "both_states_control": True,
        "pass": True,
    }
    print(json.dumps(out, indent=2))
    print("SUCCESS:WFA-0047-probe1 refusal path 10/10 NOT-EXTRACTABLE; mutant went red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
