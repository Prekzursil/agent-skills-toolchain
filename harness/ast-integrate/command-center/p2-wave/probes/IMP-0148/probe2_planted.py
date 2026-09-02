#!/usr/bin/env python3
"""IMP-0148 probe 2: planted undocumented id turns the closure test red.

Uses tools/detector-self-test so silence-on-good and fire-on-bad are both required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "detector-self-test"))

from agentspec.id_closure import (  # noqa: E402
    PLANTED_UNDOCUMENTED_ID,
    VALIDATE_PATH,
    check_closure,
    plant_undocumented_id,
)
from detector_self_test import run_both_states  # noqa: E402


def detector(source: str) -> dict:
    result = check_closure(source=source)
    extra = result.get("extra") or []
    return {
        "equal": result["equal"],
        "fired": (not result["equal"]) and PLANTED_UNDOCUMENTED_ID in extra,
        "extra": extra,
        "missing": result.get("missing") or [],
    }


def is_silent(output: dict) -> bool:
    return bool(output.get("equal")) and not output.get("fired")


def is_fire(output: dict) -> bool:
    return bool(output.get("fired")) and PLANTED_UNDOCUMENTED_ID in (output.get("extra") or [])


def main() -> int:
    good = VALIDATE_PATH.read_text(encoding="utf-8")
    bad = plant_undocumented_id(good)
    pair = run_both_states(
        detector,
        good,
        bad,
        is_silent=is_silent,
        is_fire=is_fire,
    )
    payload = {
        "ok": pair.ok,
        "silent_on_good": pair.silent_on_good,
        "fires_on_bad": pair.fires_on_bad,
        "good_output": pair.good_output,
        "bad_output": pair.bad_output,
        "planted_id": PLANTED_UNDOCUMENTED_ID,
        "notes": pair.notes,
    }
    print(json.dumps(payload, sort_keys=True))
    if not pair.ok:
        print("FAIL:IMP-0148-probe2 detector both-states control", file=sys.stderr)
        return 1
    print(
        "SUCCESS:IMP-0148-probe2 planted-undocumented-id-turns-red "
        f"id={PLANTED_UNDOCUMENTED_ID} silent_on_good=True fires_on_bad=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
