#!/usr/bin/env python3
"""Probe 1: planted-defect must FIRE; detector-control before any absence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import scenario as S  # noqa: E402

OUT = HERE / "probe1-planted.raw.json"
EXPECTED_LOST = "d-rollback-required"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0097-probe1 {msg}")
    return 1


def main() -> int:
    S.write_all()
    D.reset_control()

    planted = S.planted_bad()
    control = D.detector_control_known_present(planted)
    if not control["fired"]:
        return fail("detector-control known-present did not FIRE; fixture is broken")
    if EXPECTED_LOST not in control["lost_ids"]:
        return fail(f"lost_ids={control['lost_ids']} missing {EXPECTED_LOST}")
    if control.get("synthesizer_self_attestation_healthy") is True and not control["fired"]:
        return fail("self-attestation suppressed the fire")

    negative = (
        "negative control (state the check is meant to reject): fixture "
        "planted-bad-dropped-dissent has transcript dissent d-rollback-required "
        f"({S.SKEPTIC_DISSENT!r}) absent from the synthesis body; "
        f"detector fired={control['fired']} lost_ids={control['lost_ids']} "
        "synthesizer self_attestation.all_dissent_preserved=true was ignored."
    )
    print(negative)

    voided = D.detect(S.planted_void_id_only())
    if not voided["fired"] or EXPECTED_LOST not in voided["lost_ids"]:
        return fail("id-only void preservation did not FIRE")
    generic = D.detect(S.planted_generic_mention())
    if not generic["fired"] or EXPECTED_LOST not in generic["lost_ids"]:
        return fail("generic mention did not FIRE")

    doc = {
        "pass": True,
        "detector_control_first": True,
        "known_present_fired": True,
        "planted_bad": control,
        "void_id_only_fired": True,
        "generic_mention_fired": True,
        "negative_control_verbatim": negative,
        "expected_lost_id": EXPECTED_LOST,
        "ignored_self_attestation": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"fired_on_planted_bad=True lost_ids={control['lost_ids']} "
        f"void_id_only=True generic_mention=True detector_control_first=True"
    )
    print("SUCCESS:CNL-0097-probe1 planted-defect fires; detector-control first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
