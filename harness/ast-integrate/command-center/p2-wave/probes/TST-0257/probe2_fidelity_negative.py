#!/usr/bin/env python3
"""Probe 2 (independent reviewer): persona fidelity + corrupt-script fail-loud.

Does not import probe1. Re-runs the both-states control from the simulator:
good cast seats the scripted dissenter; gutted critic script raises and does
not mint a default participant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0257.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0257-probe2 {msg}")
    return 1


def main() -> int:
    live = S.live()
    if not live.get("fidelity_ok"):
        return fail(
            f"scripted dissenter missing from transcript "
            f"expected={live.get('expected_dissenters')} got={live.get('dissenters')}"
        )
    if "critic" not in (live.get("dissenters") or []):
        return fail(f"critic not in dissenters {live.get('dissenters')}")
    neg = live.get("negative_control") or {}
    if not neg.get("fired"):
        return fail(f"corrupt persona did not fail loudly: {neg}")
    if neg.get("substituted_default"):
        return fail("corrupt persona was substituted with a default participant")
    if neg.get("error_type") not in {"PersonaScriptError", "CouncilSpecError"}:
        return fail(f"unexpected error_type {neg.get('error_type')}")
    if live.get("model_calls") != 0:
        return fail(f"model_calls={live.get('model_calls')} want 0")

    print(
        f"dissenters={live['dissenters']} "
        f"negative={neg.get('error_type')}: {neg.get('message')}"
    )

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec_d = list((doc.get("fidelity") or {}).get("dissenters") or [])
        if rec_d != list(live.get("dissenters") or []):
            return fail("receipt dissenters != live")
        rec_n = doc.get("negative_control") or {}
        if rec_n.get("fired") is not True:
            return fail("receipt negative_control.fired is not true")
        if rec_n.get("substituted_default") is not False:
            return fail("receipt claims a default was substituted")
        if rec_n.get("error_type") != neg.get("error_type"):
            return fail("receipt negative error_type != live")
        reviewer = doc.get("reviewer") or {}
        if reviewer.get("independent") is not True:
            return fail("receipt reviewer.independent is not true")
        if reviewer.get("verdict") not in {"PASS", "CONFIRMED"}:
            return fail(f"receipt reviewer.verdict={reviewer.get('verdict')}")
        print("receipt fidelity and negative control match live")

    print("SUCCESS:TST-0257-probe2 fidelity and fail-loud negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
