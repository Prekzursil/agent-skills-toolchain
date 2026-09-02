#!/usr/bin/env python3
"""Named probe 2: capture-target assertion fires on a decoy window (both-states).

Intended surface: window title + planted marker colour-count pass.
Decoy surface: different title, zero intended-marker pixels → assertion fires.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from product_blueprints import render  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0248-probe2 {msg}")
    return 1


def main() -> int:
    intended = render.grab(intended=True)
    try:
        good = render.assert_capture_target(intended)
    except render.CaptureTargetError as exc:
        return fail(f"intended surface rejected: {exc}")
    if good.get("asserted") is not True:
        return fail("intended capture did not record asserted=true")
    if int(good["marker_count"]) < 256:  # type: ignore[arg-type]
        return fail(f"intended marker count too low: {good['marker_count']}")

    decoy = render.grab(intended=False)
    fired = False
    decoy_msg = ""
    try:
        render.assert_capture_target(decoy)
    except render.CaptureTargetError as exc:
        fired = True
        decoy_msg = str(exc)
    if not fired:
        return fail("decoy window did not fire capture-target assertion")
    if decoy.window_title == render.INTENDED_TITLE:
        return fail("decoy reused the intended window title")
    decoy_counts = decoy.framebuffer.color_counts()
    decoy_marker = int(decoy_counts.get(render.MARKER_RGB, 0))
    if decoy_marker != 0:
        return fail(f"decoy still contains intended marker pixels: {decoy_marker}")

    payload = {
        "probe": "probe2-capture-target-decoy",
        "unit_id": "IMP-0248",
        "intended_title": intended.window_title,
        "decoy_title": decoy.window_title,
        "intended_marker_count": int(good["marker_count"]),  # type: ignore[arg-type]
        "decoy_intended_marker_count": decoy_marker,
        "intended_asserted": True,
        "decoy_fired": True,
        "decoy_error": decoy_msg,
        "method": "window-title-and-colour-count",
        "both_states": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"intended_ok=True decoy_fired=True "
        f"marker_intended={good['marker_count']} marker_decoy={decoy_marker}"
    )
    print("SUCCESS:IMP-0248-probe2 capture-target fires on decoy window")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
