#!/usr/bin/env python3
"""Named probe 1: contrast ratios computed from pixels, not asserted.

Both-states: a high-contrast swatch and a low-contrast swatch on the same
render produce different recorded numbers. A post-paint mutation of the
high-contrast swatch collapses its ratio, proving the figure is sampled
from the framebuffer.
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
    print(f"FAILED:IMP-0248-probe1 {msg}")
    return 1


def main() -> int:
    fb, layout = render.paint_intended_surface()
    measured = render.measure_intended_accessibility(fb, layout)
    high = measured["contrasts"]["high"]  # type: ignore[index]
    low = measured["contrasts"]["low"]  # type: ignore[index]
    high_ratio = float(high["contrast_ratio"])
    low_ratio = float(low["contrast_ratio"])
    if high["method"] != "pixel-majority-sample":
        return fail("high contrast was not pixel-sampled")
    if high_ratio <= 7.0:
        return fail(f"high contrast too small to be navy-on-white: {high_ratio}")
    if low_ratio >= 2.0:
        return fail(f"low contrast too large to be grey-on-grey: {low_ratio}")
    if high_ratio == low_ratio:
        return fail("high and low ratios identical — likely asserted, not measured")

    ok_btn, small = measured["tap_targets"]  # type: ignore[misc]
    if int(ok_btn["width_px"]) != 48 or int(ok_btn["height_px"]) != 48:
        return fail(f"primary tap bbox not from pixels: {ok_btn}")
    if int(small["width_px"]) != 12 or int(small["height_px"]) != 12:
        return fail(f"icon tap bbox not from pixels: {small}")

    fg = layout["high_fg_rect"]
    fb.fill_rect(int(fg[0]), int(fg[1]), int(fg[2]), int(fg[3]), render.WHITE)  # type: ignore[index]
    mutated = render.measure_intended_accessibility(fb, layout)
    mutated_ratio = float(mutated["contrasts"]["high"]["contrast_ratio"])  # type: ignore[index]
    if mutated_ratio >= high_ratio:
        return fail(f"mutating pixels did not change contrast: {mutated_ratio}")
    if mutated_ratio >= 1.2:
        return fail(f"whitened swatch still reports contrast {mutated_ratio}")

    payload = {
        "probe": "probe1-contrast-from-pixels",
        "unit_id": "IMP-0248",
        "high_contrast_ratio": high_ratio,
        "low_contrast_ratio": low_ratio,
        "high_fg_rgb": high["fg_rgb"],
        "high_bg_rgb": high["bg_rgb"],
        "low_fg_rgb": low["fg_rgb"],
        "low_bg_rgb": low["bg_rgb"],
        "mutated_high_contrast_ratio": mutated_ratio,
        "primary_tap_px": [ok_btn["width_px"], ok_btn["height_px"]],
        "icon_tap_px": [small["width_px"], small["height_px"]],
        "method": "pixel-majority-sample",
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"high={high_ratio:.3f} low={low_ratio:.3f} "
        f"mutated={mutated_ratio:.3f} tap={ok_btn['width_px']}x{ok_btn['height_px']}"
    )
    print("SUCCESS:IMP-0248-probe1 contrast measured from pixels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
