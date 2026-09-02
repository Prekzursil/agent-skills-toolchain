#!/usr/bin/env python3
"""Probe 1: both-states control for the progress predicate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import progress as P  # noqa: E402

ART = REPO / (
    "command-center/research/deep-research-design/"
    "RES-0167-fix-review-repair-loop-limits.json"
)
SENTINEL = "SUCCESS:RES-0167"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0167-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if doc.get("unit_id") != "RES-0167":
        return fail(f"unit_id {doc.get('unit_id')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")

    live = P.both_states()
    prod = P.classify_attempts(P.PRODUCTIVE_SEQUENCE)
    grind = P.classify_attempts(P.GRIND_SEQUENCE)
    broken = P.always_progress(P.GRIND_SEQUENCE)
    if prod != P.PROGRESS:
        return fail(f"productive classified {prod}")
    if grind != P.NO_PROGRESS:
        return fail(f"grind classified {grind}")
    if prod == grind:
        return fail("detector silent in both states")
    if broken != P.PROGRESS:
        return fail("broken classifier did not stay PROGRESS")
    if broken == grind:
        return fail("broken classifier accidentally matched the good grind verdict")
    if live.get("good_discriminator") is not True:
        return fail("live discriminator false")

    both = doc.get("both_states") or {}
    if both.get("productive_verdict") != P.PROGRESS:
        return fail("artifact productive_verdict drift")
    if both.get("grind_verdict") != P.NO_PROGRESS:
        return fail("artifact grind_verdict drift")
    if both.get("good_discriminator") is not True:
        return fail("artifact discriminator false")
    if both.get("broken_silent_on_grind") is not True:
        return fail("artifact missing broken-silent-on-grind control")
    printed = str(doc.get("printed_both_states") or both.get("printed") or "")
    if "PROGRESS" not in printed or "NO-PROGRESS" not in printed:
        return fail("printed both-states missing PROGRESS/NO-PROGRESS")

    payload = {
        "probe": "probe1-both-states",
        "unit_id": "RES-0167",
        "productive_verdict": prod,
        "grind_verdict": grind,
        "broken_always_progress_on_grind": broken,
        "discriminator": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "NEGATIVE CONTROL (always-PROGRESS classifier): silent on grind; "
        "good classifier PROGRESS vs NO-PROGRESS."
    )
    print(
        "BOTH-STATES: productive retry sequence=PROGRESS; "
        "same-fingerprint grind=NO-PROGRESS"
    )
    print("SUCCESS:RES-0167-probe1 both-states productive vs grind")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
