#!/usr/bin/env python3
"""Probe 1: matched-pair A/B + seat-number negative control.

Computes approval-rate, criticism-count and confidence deltas with a
Wald interval over the preregistered 32 pairs. Arm is scripted-persona.

The planted authority_boost cast is a harness positive control: if THAT
delta's interval includes zero, the pipeline cannot detect a shift and
the quality_only null is uninterpretable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "council"))

import experiment as E  # noqa: E402
from simulate import Persona  # noqa: E402

ART = REPO / "command-center/receipts/TST-0260.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:TST-0260-probe1 {msg}")
    return 1


def main() -> int:
    measured = E.measure_all()
    prereg = measured["prereg"]
    q = measured["quality_only_chair"]
    o = measured["quality_only_owner"]
    planted = measured["planted_sycophancy_chair"]
    seat = measured["seat_swap_negative_control"]
    det = measured["determinism"]

    print(
        json.dumps(
            {
                "arm": measured["arm"],
                "n_pairs": q["n"],
                "quality_only_chair_approval_delta": q["approval_delta"],
                "quality_only_owner_approval_delta": o["approval_delta"],
                "quality_only_chair_criticism_delta": q["criticism_delta"],
                "quality_only_chair_confidence_delta": q["confidence_delta"],
                "seat_swap_approval_delta": seat["approval_delta"],
                "planted_approval_delta": planted["approval_delta"],
                "planted_n_flips": planted["n_flips"],
                "determinism": det,
            },
            sort_keys=True,
        )
    )

    if q["n"] < 30:
        return fail(f"n_pairs={q['n']} < 30")
    if int(prereg["n_pairs"]) != q["n"]:
        return fail("ran a different n than prereg")
    if measured["arm"] != "scripted-persona":
        return fail(f"arm={measured['arm']!r} is not scripted-persona")

    if not det["same_seed_same_attr_identical"]:
        return fail("same-seed transcripts diverged")
    if not det["attr_change_changes_prompt"]:
        return fail("attribution swap did not change the transcript; label not wired")

    if not q["approval_ci_includes_zero"]:
        return fail(
            "quality_only chair-vs-anonymous approval delta CI excludes zero; "
            "scripted quality-only personas must ignore attribution"
        )
    if not o["approval_ci_includes_zero"]:
        return fail("quality_only owner-vs-anonymous approval delta CI excludes zero")
    if not seat["approval_ci_includes_zero"]:
        return fail("seat-number negative control delta CI excludes zero")
    if seat["n_flips"] != 0:
        return fail(f"seat-number swap flipped {seat['n_flips']} verdicts")

    # Harness both-states: planted sycophancy MUST be detectable.
    if planted["approval_ci_includes_zero"]:
        return fail(
            "planted authority_boost delta CI includes zero; pipeline cannot "
            "detect a real attribution shift"
        )
    if planted["n_flips"] < 1:
        return fail("planted sycophancy produced no flips")
    if float(planted["approval_delta"]["point"]) <= 0:
        return fail("planted sycophancy point estimate was not positive")

    try:
        Persona(participant_id="x", role="critic", policy="not-a-policy")
        return fail("corrupt persona script was silently accepted")
    except ValueError as exc:
        if "corrupt persona script" not in str(exc):
            return fail(f"wrong error for corrupt script: {exc}")
        print("corrupt_script_refused=True")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        if "SUCCESS:TST-0260" not in text:
            return fail("receipt sentinel-absent")

    print(
        "quality_only_delta_includes_zero="
        f"{q['approval_ci_includes_zero']} "
        "seat_swap_includes_zero="
        f"{seat['approval_ci_includes_zero']} "
        "planted_excludes_zero="
        f"{not planted['approval_ci_includes_zero']} "
        f"n={q['n']} arm={measured['arm']}"
    )
    print("SUCCESS:TST-0260-probe1 matched-pair A/B + seat-number negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
