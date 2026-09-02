#!/usr/bin/env python3
"""Probe 1: runtime-string partition vs guard; disagreements listed.

Both-states: planting a LangGraph import on an ADOPT-AS-IS candidate whose
runtime string is claude-code MUST appear as a disagreement; clearing the
plant MUST remove it. A jsonschema import MUST stay silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import PLANT_ID, load_candidates, overlay_plant  # noqa: E402
from engine import analyse, both_states_plant  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0072-translate-backlog.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0072-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0072":
        print("FAILED:WFA-0072-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0072-probe1 self-declared", doc.get("state"))
        return 1
    text = json.dumps(doc)
    if "SUCCESS:WFA-0072" not in text:
        print("FAILED:WFA-0072-probe1 sentinel absent")
        return 1

    rows, meta = load_candidates()
    if len(rows) != 284:
        print(f"FAILED:WFA-0072-probe1 n={len(rows)}")
        return 1
    live = analyse(rows)
    if live["n"] != 284:
        print("FAILED:WFA-0072-probe1 analyse n")
        return 1
    art_ids = {d["id"] for d in (doc.get("disagreements") or [])}
    live_ids = {d["id"] for d in live["disagreements"]}
    if art_ids != live_ids:
        print("FAILED:WFA-0072-probe1 disagreement drift", sorted(art_ids), sorted(live_ids))
        return 1
    if doc.get("translate_n") != live["translate_n"]:
        print(
            "FAILED:WFA-0072-probe1 translate_n drift",
            doc.get("translate_n"),
            live["translate_n"],
        )
        return 1
    if live["translate_n"] == 0 and not live["zero_reclassification_ok"]:
        print("FAILED:WFA-0072-probe1 zero TRANSLATE with disagreements")
        return 1

    ctl = both_states_plant(rows)
    planted = analyse(overlay_plant(rows, True))
    plant_dis = [d for d in planted["disagreements"] if d["id"] == PLANT_ID]
    if not plant_dis:
        print("FAILED:WFA-0072-probe1 plant did not produce disagreement")
        return 1
    if plant_dis[0]["signal_a"] != "KEEP" or plant_dis[0]["signal_b"] != "TRANSLATE":
        print("FAILED:WFA-0072-probe1 plant polarity", plant_dis[0])
        return 1
    if not ctl.get("ok"):
        print("FAILED:WFA-0072-probe1 both-states", json.dumps(ctl, sort_keys=True))
        return 1
    if not (doc.get("both_states") or {}).get("ok"):
        print("FAILED:WFA-0072-probe1 artifact both_states not ok")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-partition-vs-guard",
        "unit_id": "WFA-0072",
        "n": live["n"],
        "corpus_kind": meta["kind"],
        "disagreement_n": len(live["disagreements"]),
        "translate_n": live["translate_n"],
        "plant_appeared": ctl["plant_appeared"],
        "plant_cleared": ctl["plant_cleared"],
        "benign_lib_silent": ctl["benign_lib_silent"],
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"n=284 disagreements={payload['disagreement_n']} "
        f"translate={payload['translate_n']} plant={ctl['plant_appeared']}/cleared={ctl['plant_cleared']}"
    )
    print("SUCCESS:WFA-0072-probe1 partition vs guard both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
