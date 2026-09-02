#!/usr/bin/env python3
"""Probe 2: independent resolution pass. Starts from the tests, not probe 1.

Adversarial brief: the invariant is 'VERIFIED requires a resolvable anchor'.
The negative control marks an unanchored claim VERIFIED and asserts the
resolution pass FIRES. The both-states arm is the same pass silent on the
known-good anchored VERIFIED records.

This script does not read probe1 output or the author's receipt narrative.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.artifacts.claims import (  # noqa: E402
    emit,
    mark_verified_unanchored,
    resolution_pass,
    validate_record,
)

COUNCIL = HERE / "fixtures" / "council.json"
GHOST = "command-center/p2-wave/probes/IMP-0259/fixtures/anchors/does-not-exist.md:1"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0259-probe2 {msg}")
    return 1


def main() -> int:
    council = json.loads(COUNCIL.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="imp0259-p2-") as tmp:
        registry_path = Path(tmp) / "CLAIM-REGISTRY.json"
        emitted = emit(council, registry_path=registry_path, root=REPO)
    claims = emitted["claims"]
    verified = [c for c in claims if c.get("verification_status") == "VERIFIED"]
    if len(verified) < 2:
        return fail(f"need >=2 VERIFIED fixture claims, got {len(verified)}")

    good = resolution_pass(claims, root=REPO)
    if good["fired"]:
        return fail(f"resolution pass fired on known-good registry: {good['failures']}")
    if good["checked"] != len(verified):
        return fail(f"checked={good['checked']} verified={len(verified)}")

    # Negative control 1: strip anchors, keep VERIFIED.
    mutant = mark_verified_unanchored(verified[0])
    schema_errs = validate_record(mutant, root=REPO)
    if "verified-without-anchor" not in schema_errs:
        return fail(f"schema did not reject unanchored VERIFIED: {schema_errs}")
    bad = resolution_pass([mutant], root=REPO)
    if not bad["fired"]:
        return fail("resolution pass silent on unanchored VERIFIED mutant")

    # Negative control 2: VERIFIED pointing at a missing file (different
    # failure mode than empty-list, so the detector is not only checking len).
    missing = dict(verified[0])
    missing["evidence_anchors"] = [GHOST]
    missing_walk = resolution_pass([missing], root=REPO)
    if not missing_walk["fired"]:
        return fail("resolution pass silent on missing-file VERIFIED mutant")
    reason = (missing_walk["failures"][0]["anchors"][0]["reason"] if missing_walk["failures"] else "")
    if reason != "missing-file":
        return fail(f"missing-file mutant reason={reason!r} want=missing-file")

    # Line-past-eof: cite line 999 of a 3-line file.
    eof = dict(verified[1] if len(verified) > 1 else verified[0])
    eof["evidence_anchors"] = [
        "command-center/p2-wave/probes/IMP-0259/fixtures/anchors/anchor-rule.md:999"
    ]
    eof_walk = resolution_pass([eof], root=REPO)
    if not eof_walk["fired"]:
        return fail("resolution pass silent on line-past-eof VERIFIED mutant")
    eof_reason = eof_walk["failures"][0]["anchors"][0]["reason"]
    if eof_reason != "line-past-eof":
        return fail(f"line-past-eof reason={eof_reason!r}")

    payload = {
        "probe": "probe2-anchor-resolution",
        "unit_id": "IMP-0259",
        "pass": True,
        "reviewer_id": "IMP-0259-probe2-anchor-resolution",
        "independent": True,
        "starts_from": "tests (schema invariant + negative controls), not author summary",
        "good_pass": {
            "fired": good["fired"],
            "checked": good["checked"],
            "fired_count": good["fired_count"],
        },
        "unanchored_verified": {
            "schema_errors": schema_errs,
            "resolution_fired": bad["fired"],
        },
        "missing_file_verified": {
            "fired": missing_walk["fired"],
            "reason": reason,
        },
        "line_past_eof_verified": {
            "fired": eof_walk["fired"],
            "reason": eof_reason,
        },
        "both_states": {
            "silent_on_good": not good["fired"],
            "fires_on_unanchored": bad["fired"],
            "fires_on_missing_file": missing_walk["fired"],
            "fires_on_line_past_eof": eof_walk["fired"],
        },
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"good_silent={not good['fired']} unanchored_fired={bad['fired']} "
        f"missing_file_fired={missing_walk['fired']} eof_fired={eof_walk['fired']}"
    )
    print("SUCCESS:IMP-0259-probe2 resolution-pass negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
