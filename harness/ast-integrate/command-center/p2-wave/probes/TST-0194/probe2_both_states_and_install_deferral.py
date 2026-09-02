#!/usr/bin/env python3
"""Probe 2: both-states clean build + install-time-deferral negative control.

Independent of probe 1's colliding-fixture subprocess: this probe packs the
clean fixture and the mutant install-time packer, then applies TST-0194's
PASS rule to the mutant (must FAIL).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0194.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0194-probe2 {msg}")
    return 1


def main() -> int:
    live = S.evaluate()
    both = live["both_states"]
    nc = live["negative_control"]
    sig_a = live["signal_a"]

    if not both["clean_manifest_builds"]:
        return fail(
            f"clean fixture did not build rc={sig_a['clean']['rc']} "
            f"exists={sig_a['clean']['output_exists']} tail={sig_a['clean']['text_tail'][-200:]}"
        )
    if live["signal_b"]["clean"]["collision"] is not False:
        return fail("clean fixture independent set-size reported a collision")

    if nc["fired_on_bad_state"] is not True:
        return fail(f"negative control did not fire: {nc}")
    if nc["silent_on_good_state"] is not True:
        return fail("negative control was not silent on the real packer")
    if nc["test_applied_to_mutant"] != "FAIL":
        return fail("deferring the check to install time did not fail TST-0194")
    if nc["mutant_build_rc"] != 0:
        return fail(f"mutant packer should succeed at build rc={nc['mutant_build_rc']}")
    if nc["mutant_named_collision_at_build"] is True:
        return fail("mutant unexpectedly named a collision at build")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        errs = S.artifact_ok(doc)
        if errs:
            return fail(",".join(errs))
        tests = doc.get("tests") or {}
        if (tests.get("both_states_clean_builds") or {}).get("pass") is not True:
            return fail("artifact both-states not pass")
        if (tests.get("negative_control_install_deferral") or {}).get("pass") is not True:
            return fail("artifact negative control not pass")

    summary = {
        "probe": "probe2-both-states-and-install-deferral",
        "unit_id": "TST-0194",
        "clean_builds": both["clean_manifest_builds"],
        "mutant_build_rc": nc["mutant_build_rc"],
        "test_applied_to_mutant": nc["test_applied_to_mutant"],
        "negative_control_fired": nc["fired_on_bad_state"],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"clean_builds={both['clean_manifest_builds']} "
        f"mutant_rc={nc['mutant_build_rc']} "
        f"test_on_mutant={nc['test_applied_to_mutant']}"
    )
    print("SUCCESS:TST-0194-probe2 both-states control and install-time deferral")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
