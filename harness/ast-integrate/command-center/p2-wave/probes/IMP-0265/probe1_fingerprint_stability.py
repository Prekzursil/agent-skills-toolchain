#!/usr/bin/env python3
"""Probe 1: fingerprint computation stability + 12-seat collision report.

Recomputes voice fingerprints many times, permutes non-voice fields and tool
order, and requires the 12-seat roster collision report to fire on the planted
duplicate while keeping same-vendor/model different-prompt seats distinct.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

ART = S.RECEIPT_PATH


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0265-probe1 {msg}")
    return 1


def main() -> int:
    R = S.load_registry()
    if not S.REGISTRY_PATH.is_file():
        return fail("registry.py missing")

    base = dict(S.twelve_seat_specs()[0])
    person = R.Participant(**base)
    fps = [R.voice_fingerprint(person.vendor, person.model, person.prompt, person.tool_grants) for _ in range(50)]
    if len(set(fps)) != 1 or fps[0] != person.fingerprint:
        return fail(f"fingerprint unstable set_size={len(set(fps))}")

    shuffled_tools = list(reversed(list(person.tool_grants))) + list(person.tool_grants)
    again = R.Participant(
        participant_id="perm-id",
        display_name="Other Name",
        vendor="  " + person.vendor + " ",
        model=person.model,
        prompt="\n" + person.prompt + "\n",
        declared_expertise=("unrelated-claim",),
        calibration_history_pointer="calibration://other",
        tool_grants=tuple(shuffled_tools),
    )
    if again.fingerprint != person.fingerprint:
        return fail("identity/tool-order leaked into fingerprint")

    mutated = R.Participant(
        participant_id="mut-prompt",
        display_name=person.display_name,
        vendor=person.vendor,
        model=person.model,
        prompt=person.prompt + " extra clause",
        declared_expertise=person.declared_expertise,
        calibration_history_pointer=person.calibration_history_pointer,
        tool_grants=person.tool_grants,
    )
    if mutated.fingerprint == person.fingerprint:
        return fail("prompt change did not move fingerprint")

    reg = S.twelve_seat_registry()
    roster = reg.roster()
    if len(roster) != 12:
        return fail(f"roster size {len(roster)} want=12")
    report = reg.collision_report()
    if not report["fired"]:
        return fail("12-seat collision report did not fire")
    if report["seat_count"] != 12:
        return fail(f"seat_count={report['seat_count']}")
    if report["effective_voice_count"] != 11:
        return fail(f"effective_voice_count={report['effective_voice_count']} want=11")
    if report["collision_count"] != 1:
        return fail(f"collision_count={report['collision_count']} want=1")
    coll = report["collisions"][0]
    seats = set(coll["seat_ids"])
    if seats != {S.CLONE_OF, S.CLONE_ID}:
        return fail(f"unexpected collision seats {sorted(seats)}")

    same_model = S.same_model_different_prompt_registry().collision_report()
    if same_model["fired"] or same_model["effective_voice_count"] != 2:
        return fail("same vendor+model different prompt must stay two voices")

    audit = reg.independence_audit()
    if audit["pair_count"] != 1 or not audit["all_flagged_pairs_non_independent"]:
        return fail(f"independence audit {audit}")
    pair = audit["pairs"][0]
    if not pair["first_round_identical"] or pair["independent"]:
        return fail(f"flagged pair still treated independent {pair}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:IMP-0265" not in blob:
        return fail("sentinel absent")
    if doc.get("unit_id") != "IMP-0265":
        return fail(f"unit_id={doc.get('unit_id')}")
    live_fp = person.fingerprint
    receipt_fp = (
        ((doc.get("collision_report") or {}).get("collisions") or [{}])[0].get("fingerprint")
    )
    if receipt_fp != live_fp:
        return fail(f"receipt collision fingerprint {receipt_fp} != live {live_fp}")

    out = {
        "probe": "probe1-fingerprint-stability",
        "unit_id": "IMP-0265",
        "pass": True,
        "recompute_n": 50,
        "stable": True,
        "identity_fields_ignored": True,
        "prompt_mutation_moves_fingerprint": True,
        "twelve_seat": {
            "seat_count": report["seat_count"],
            "effective_voice_count": report["effective_voice_count"],
            "fired": report["fired"],
            "collision_seats": sorted(seats),
        },
        "independence_rejected": pair["independence_rejected"],
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0265-probe1 fingerprint stability and 12-seat collision report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
