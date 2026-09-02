#!/usr/bin/env python3
"""Probe 2: independent WCAG contrast from rendered PPM pixels, both themes.

Catalog: test_contrast_meets_the_declared_threshold_in_both_themes

Re-parses the PPM and reimplements relative luminance. Does not call
operator_surface.contrast_ratio. Yellow-on-white decoy must fail the threshold.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "monitorcore"))

from monitorcore.operator_surface import (  # noqa: E402
    FOCUS_CONTRAST_THRESHOLD,
    TEXT_CONTRAST_THRESHOLD,
    THEMES,
    decoy_low_contrast_grid,
    render_theme_grid,
    write_ppm_p3,
)

from live import ART, load_receipt, write_captures  # noqa: E402

RAW = HERE / "probe2-contrast.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0114-probe2 {msg}")
    return 1


def srgb_to_lin(channel: int) -> float:
    x = channel / 255.0
    if x <= 0.04045:
        return x / 12.92
    return ((x + 0.055) / 1.055) ** 2.4


def luma(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)


def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    x, y = luma(a), luma(b)
    hi, lo = (x, y) if x >= y else (y, x)
    return (hi + 0.05) / (lo + 0.05)


def parse_ppm_p3(text: str) -> list[list[tuple[int, int, int]]]:
    tokens: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tokens.extend(line.split())
    if not tokens or tokens[0] != "P3":
        raise ValueError("not a P3 PPM")
    width, height, maxval = int(tokens[1]), int(tokens[2]), int(tokens[3])
    if maxval != 255:
        raise ValueError(f"maxval {maxval}")
    nums = [int(t) for t in tokens[4:]]
    need = width * height * 3
    if len(nums) < need:
        raise ValueError(f"ppm short: {len(nums)} < {need}")
    grid: list[list[tuple[int, int, int]]] = []
    i = 0
    for _y in range(height):
        row: list[tuple[int, int, int]] = []
        for _x in range(width):
            row.append((nums[i], nums[i + 1], nums[i + 2]))
            i += 3
        grid.append(row)
    return grid


def sample(
    grid: list[list[tuple[int, int, int]]],
) -> dict[str, dict[str, tuple[int, int, int]]]:
    def pix(x: int, y: int) -> tuple[int, int, int]:
        return grid[y][x]

    return {
        "fg_on_bg": {"fg": pix(20, 6), "bg": pix(60, 18)},
        "accent_on_bg": {"fg": pix(60, 6), "bg": pix(60, 18)},
        "focus_on_bg": {"fg": pix(20, 18), "bg": pix(60, 18)},
    }


def main() -> int:
    paths = write_captures()
    measured: dict[str, Any] = {}
    for theme in THEMES:
        ppm_text = write_ppm_p3(render_theme_grid(theme))
        on_disk = (REPO / paths[theme]).read_text(encoding="utf-8")
        if on_disk != ppm_text:
            return fail(f"{theme} on-disk PPM != live render")
        pairs = sample(parse_ppm_p3(on_disk))
        row: dict[str, Any] = {}
        for name, pair in pairs.items():
            ratio = contrast(pair["fg"], pair["bg"])
            threshold = (
                FOCUS_CONTRAST_THRESHOLD
                if name.startswith("focus")
                else TEXT_CONTRAST_THRESHOLD
            )
            ok = ratio >= threshold
            row[name] = {
                "fg": list(pair["fg"]),
                "bg": list(pair["bg"]),
                "ratio": round(ratio, 4),
                "threshold": threshold,
                "pass": ok,
            }
            if not ok:
                RAW.write_text(
                    json.dumps({"measured": measured, "fail": theme, "row": row}, indent=2)
                    + "\n",
                    encoding="utf-8",
                )
                return fail(f"{theme} {name} ratio={ratio:.3f} < {threshold}")
        measured[theme] = row

    decoy_text = (REPO / paths["decoy"]).read_text(encoding="utf-8")
    if decoy_text != write_ppm_p3(decoy_low_contrast_grid()):
        return fail("decoy PPM drifted from renderer")
    decoy_ratio = contrast(
        sample(parse_ppm_p3(decoy_text))["fg_on_bg"]["fg"],
        sample(parse_ppm_p3(decoy_text))["fg_on_bg"]["bg"],
    )
    if decoy_ratio >= TEXT_CONTRAST_THRESHOLD:
        return fail(f"decoy contrast {decoy_ratio:.3f} did not fall under threshold")

    receipt = load_receipt()
    if receipt is None or not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0114" not in text:
        return fail("sentinel absent")
    recorded = ((receipt.get("measurements") or {}).get("contrast")) or {}
    if recorded:
        for theme in THEMES:
            rec_theme = recorded.get(theme) or {}
            for name, row in measured[theme].items():
                rec = rec_theme.get(name) or {}
                if rec and abs(float(rec.get("ratio") or 0) - row["ratio"]) > 0.05:
                    return fail(
                        f"receipt {theme}.{name} ratio {rec.get('ratio')} "
                        f"!= live {row['ratio']}"
                    )

    RAW.write_text(
        json.dumps(
            {
                "measured": measured,
                "decoy_ratio": round(decoy_ratio, 4),
                "decoy_fails_threshold": decoy_ratio < TEXT_CONTRAST_THRESHOLD,
                "threshold_text": TEXT_CONTRAST_THRESHOLD,
                "threshold_focus": FOCUS_CONTRAST_THRESHOLD,
                "paths": paths,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        "dark_fg={d} light_fg={l} decoy={decoy} threshold={th}".format(
            d=measured["dark"]["fg_on_bg"]["ratio"],
            l=measured["light"]["fg_on_bg"]["ratio"],
            decoy=round(decoy_ratio, 4),
            th=TEXT_CONTRAST_THRESHOLD,
        )
    )
    print("SUCCESS:TST-0114-probe2 contrast from pixels both themes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
