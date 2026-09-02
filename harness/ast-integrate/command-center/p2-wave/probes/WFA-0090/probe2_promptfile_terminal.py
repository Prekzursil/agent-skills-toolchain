#!/usr/bin/env python3
"""Named probe 2: oversized inline routed to a prompt file; terminal states.

Independent of probe 1: this process re-runs the both-states background pair
(reviewer requirement) and then checks argv-cap routing plus the return-point
enumeration (no silent return on the repaired dispatcher).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from dispatch import (  # noqa: E402
    MEASURED_OVERFLOW_INLINE_LEN,
    WIN_CREATEPROCESS_CAP,
    campaign,
)

ART = REPO / "command-center/wfa/WFA-0090-repair-crossvendor-dispatch.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0090-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0090" not in json.dumps(doc):
        print("FAILED:WFA-0090-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0090-probe2 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="wfa0090-p2-") as raw:
        live = campaign(Path(raw))

    # Reviewer: re-run both-states in this process, not by reading probe 1.
    bg = live["both_states_background"]
    if not bg.get("pass"):
        print("FAILED:WFA-0090-probe2 reviewer both-states")
        print(json.dumps(bg, indent=2))
        return 1

    ov = live["oversized_inline"]
    if not ov.get("pass"):
        print("FAILED:WFA-0090-probe2 oversized inline not routed")
        print(json.dumps(ov, indent=2))
        return 1
    if ov.get("repaired_prompt_file_bytes") != MEASURED_OVERFLOW_INLINE_LEN:
        print(
            "FAILED:WFA-0090-probe2 routed file bytes "
            f"{ov.get('repaired_prompt_file_bytes')} want={MEASURED_OVERFLOW_INLINE_LEN}"
        )
        return 1
    if not ov.get("repaired_argv_under_cap"):
        print("FAILED:WFA-0090-probe2 argv still over CreateProcess cap")
        return 1
    if ov.get("repaired_argv_len", 10**9) >= WIN_CREATEPROCESS_CAP:
        print("FAILED:WFA-0090-probe2 argv_len", ov.get("repaired_argv_len"))
        return 1

    if not live.get("repaired_all_terminal"):
        print("FAILED:WFA-0090-probe2 repaired path missing a terminal state")
        print(json.dumps(live.get("terminals"), indent=2)[:3000])
        return 1
    if not live.get("broken_silent_hole"):
        print("FAILED:WFA-0090-probe2 broken twin no longer exhibits the silent hole")
        return 1
    if live.get("return_points_missing"):
        print("FAILED:WFA-0090-probe2 missing return points", live["return_points_missing"])
        return 1

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        print("FAILED:WFA-0090-probe2 artifact reviewer")
        return 1

    payload = {
        "pass": True,
        "probe": "probe2-promptfile-terminal",
        "unit_id": "WFA-0090",
        "reviewer_both_states": True,
        "oversized_routed": True,
        "prompt_file_bytes": ov["repaired_prompt_file_bytes"],
        "argv_len": ov["repaired_argv_len"],
        "createprocess_cap": WIN_CREATEPROCESS_CAP,
        "repaired_all_terminal": True,
        "broken_silent_hole": True,
        "return_points_seen": live["return_points_seen"],
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"routed_bytes={ov['repaired_prompt_file_bytes']} "
        f"argv_len={ov['repaired_argv_len']} cap={WIN_CREATEPROCESS_CAP} "
        "repaired_all_terminal=True broken_silent_hole=True reviewer_both_states=True"
    )
    print("SUCCESS:WFA-0090-probe2 prompt-file routing and terminal-state enumeration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
