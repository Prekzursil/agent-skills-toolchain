#!/usr/bin/env python3
"""Probe 2: deliberate-leak control.

Inject the implementer conclusion into exactly one brief. The detector must
flag that brief and no other. Silence in both the clean and injected states
fails this unit outright (detector-failure).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0005-blind-brief-builder.json"
OUT = HERE / "probe2-deliberate-leak.raw.json"


def main() -> int:
    result = H.run_harness()
    clean = result["clean_scan"]
    control = result["deliberate_leak_control"]
    payload = {
        "injected_brief_id": control["injected_brief_id"],
        "flagged_ids": control["flagged_ids"],
        "fired_on_injected": control["fired_on_injected"],
        "silent_on_others": control["silent_on_others"],
        "silent_in_both_states": control["silent_in_both_states"],
        "clean_leaks_found": clean["leaks_found"],
        "injected_needle_count": control["injected_needle_count"],
        "pass": False,
    }
    if control["injected_needle_count"] < 1:
        print("FAILED:CNF-0005-probe2 vacuous needles on injected receipt")
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    if control["silent_in_both_states"]:
        print("FAILED:CNF-0005-probe2 detector silent in both states")
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    if clean["leaks_found"] != 0:
        print(f"FAILED:CNF-0005-probe2 clean state not silent leaks={clean['leaks_found']}")
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    if not control["fired_on_injected"]:
        print(
            "FAILED:CNF-0005-probe2 detector did not fire on injected brief "
            f"id={control['injected_brief_id']}"
        )
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    if not control["silent_on_others"] or len(control["flagged_ids"]) != 1:
        print(
            "FAILED:CNF-0005-probe2 flagged others "
            f"flagged={control['flagged_ids']}"
        )
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec = H.from_artifact(doc, "deliberate_leak_control")
        if rec.get("injected_brief_id") != control["injected_brief_id"]:
            print("FAILED:CNF-0005-probe2 artifact injected_brief_id mismatch")
            return 1
        if rec.get("fired_on_injected") is not True or rec.get("silent_on_others") is not True:
            print("FAILED:CNF-0005-probe2 artifact control not matching live run")
            return 1
        if list(rec.get("flagged_ids") or []) != [control["injected_brief_id"]]:
            print("FAILED:CNF-0005-probe2 artifact flagged_ids mismatch")
            return 1
    payload["pass"] = True
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"injected={control['injected_brief_id']} fired_on_injected=True "
        f"silent_on_others=True flagged={control['flagged_ids']} "
        f"fragments={control['injected_fragments'][:3]}"
    )
    print("SUCCESS:CNF-0005-probe2 deliberate-leak control fired on injected brief only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
