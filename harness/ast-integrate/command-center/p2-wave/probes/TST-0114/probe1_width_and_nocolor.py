#!/usr/bin/env python3
"""Probe 1: width-1 glyphs on live surfaces; NO_COLOR keeps tokens.

Catalog:
  test_no_double_width_glyph_in_the_status_surface
  test_surface_is_readable_under_no_color

Planted U+26A0 must be detected. A colour-only red/green pair must collapse
after SGR strip so the detector is not a no-op.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from live import (  # noqa: E402
    ART,
    a11y_inventory_report,
    live_surfaces,
    load_receipt,
    nocolor_report,
    width_report,
)

RAW = HERE / "probe1-width-nocolor.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0114-probe1 {msg}")
    return 1


def main() -> int:
    surfaces = live_surfaces()
    width = width_report(surfaces)
    nocolor = nocolor_report()
    a11y = a11y_inventory_report()
    RAW.write_text(
        json.dumps(
            {"width": width, "nocolor": nocolor, "a11y": a11y},
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    if not width["planted_detected"]:
        return fail("planted width-2 glyph was not detected")
    if not width["live_clean"]:
        return fail(f"live double-width glyphs: {width['live_double_width']}")
    status_keys = [k for k in surfaces if k.startswith("status:")]
    if len(status_keys) < 4:
        return fail(f"missing status surfaces: {sorted(surfaces)}")
    for key in status_keys:
        if not surfaces[key].strip():
            return fail(f"{key} empty")

    if not nocolor["pass"]:
        return fail("NO_COLOR contract failed")
    if not nocolor["color_only_collapsed"]:
        return fail("colour-only control did not collapse after SGR strip")

    if not a11y["pass"]:
        return fail("focus/keyboard/screen-reader inventory failed")

    receipt = load_receipt()
    if receipt is None or not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0114" not in text:
        return fail("sentinel absent")
    if str(receipt.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {receipt.get('state')}")

    print(
        "live_double_width=0 "
        f"planted_hits={len(width['planted_hits'])} "
        f"nocolor_pass={nocolor['pass']} "
        f"focus={a11y['focus_visible']} keys={sorted(a11y['keyboard'])}"
    )
    print("SUCCESS:TST-0114-probe1 width-1 glyphs and NO_COLOR tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
