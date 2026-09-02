#!/usr/bin/env python3
"""Probe 1: both-states gate on a scratch overlay, detector control first.

A planted unmigrated edit of a frozen schema MUST reject. The same edit with
a versioned migration MUST accept. A clean tree and a not-frozen edit MUST
stay silent. Live artifact fingerprint must match this re-run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import both_states as B  # noqa: E402
import report as R  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0110.json"


def main() -> int:
    demo = B.run(REPO)
    control = demo["detector_control"]
    states = demo["states"]
    print(
        "control fired="
        f"{control.get('fired')} clean_silent={control.get('clean_silent')} "
        f"trusted={control.get('trusted')} order={control.get('order')}"
    )
    print(
        "unmigrated_rejects="
        f"{states['unmigrated_rejects']} migrated_accepts={states['migrated_accepts']} "
        f"nonfrozen_silent={states['nonfrozen_silent']} both={demo['both_states_pass']}"
    )
    if not control.get("fired"):
        print("FAILED:ARC-0110-probe1 planted unmigrated edit did not reject")
        return 1
    if not control.get("clean_silent"):
        print("FAILED:ARC-0110-probe1 clean tree was not silent")
        return 1
    if not states["migrated_accepts"]:
        print("FAILED:ARC-0110-probe1 migrated change was not accepted")
        return 1
    if not states["nonfrozen_silent"]:
        print("FAILED:ARC-0110-probe1 not-frozen edit was not silent")
        return 1
    if not states["not_checked_rejects"]:
        print("FAILED:ARC-0110-probe1 unevaluated dry-run was admitted")
        return 1
    if not states["no_bump_rejects"]:
        print("FAILED:ARC-0110-probe1 no-version-bump migration was admitted")
        return 1
    if not states["launcher_unmigrated_rejects"]:
        print("FAILED:ARC-0110-probe1 unmigrated launcher edit was admitted")
        return 1
    if not demo.get("git_checkout_not_used"):
        print("FAILED:ARC-0110-probe1 git checkout was used")
        return 1
    if not demo.get("both_states_pass"):
        print("FAILED:ARC-0110-probe1 both-states did not pass")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0110-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0110-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ARC-0110" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0110-probe1 sentinel absent")
        return 1
    art_ctrl = doc.get("detector_control") or {}
    if art_ctrl.get("fired") is not True or art_ctrl.get("clean_silent") is not True:
        print("FAILED:ARC-0110-probe1 artifact detector_control did not record both-states")
        return 1
    live = R.measured()
    fp = live["fingerprint"]
    art_fp = doc.get("fingerprint") or {}
    # Behavioural keys must match this live both-states run. set_sha256 /
    # frozen_count / schema_count are the ceremony snapshot: concurrent
    # writers on command-center/schema/ can add or edit files after arming,
    # and that drift is what the gate is for, not a probe failure.
    for key in (
        "launcher_count",
        "both_states_pass",
        "unmigrated_rejects",
        "migrated_accepts",
        "nonfrozen_silent",
        "detector_control_fired",
        "trigger_id",
        "git_checkout_not_used",
    ):
        if art_fp.get(key) != fp.get(key):
            print(
                f"FAILED:ARC-0110-probe1 fingerprint mismatch {key}: "
                f"art={art_fp.get(key)} live={fp.get(key)}"
            )
            return 1
    art_frozen = (doc.get("census") or {}).get("frozen") or []
    if len(art_frozen) < 2:
        print("FAILED:ARC-0110-probe1 freeze set too small")
        return 1
    from hashutil import digest_bytes

    recomputed = digest_bytes(
        ("\n".join(f"{r['path']} {r['sha256']}" for r in art_frozen) + "\n").encode(
            "utf-8"
        )
    )[0]
    if art_fp.get("set_sha256") != recomputed:
        print("FAILED:ARC-0110-probe1 artifact freeze-set hash is not self-consistent")
        return 1
    if art_fp.get("frozen_count") != len(art_frozen):
        print("FAILED:ARC-0110-probe1 artifact frozen_count is not self-consistent")
        return 1
    print("SUCCESS:ARC-0110-probe1 both-states detector-control scratch overlay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
