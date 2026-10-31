"""Product blueprints 9-12: accessibility measured from pixels (IMP-0248)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

WHITE = (255, 255, 255)
NAVY = (0, 0, 128)
GREY_FG = (140, 140, 140)
GREY_BG = (150, 150, 150)
MARKER_RGB = (255, 0, 128)
INTENDED_TITLE = "IMP-0248 intended surface"


def _srgb(c: int) -> float:
    x = c / 255.0
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4


def _rel_lum(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    l1, l2 = _rel_lum(a), _rel_lum(b)
    hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
    return (hi + 0.05) / (lo + 0.05)


class CaptureTargetError(Exception):
    pass


@dataclass
class Framebuffer:
    width: int
    height: int
    pixels: list[list[tuple[int, int, int]]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.pixels:
            self.pixels = [[WHITE for _ in range(self.width)] for _ in range(self.height)]

    def fill_rect(self, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
        for yy in range(max(0, y), min(self.height, y + h)):
            for xx in range(max(0, x), min(self.width, x + w)):
                self.pixels[yy][xx] = color

    def majority(self, x: int, y: int, w: int, h: int) -> tuple[int, int, int]:
        c: Counter[tuple[int, int, int]] = Counter()
        for yy in range(max(0, y), min(self.height, y + h)):
            for xx in range(max(0, x), min(self.width, x + w)):
                c[self.pixels[yy][xx]] += 1
        return c.most_common(1)[0][0] if c else WHITE

    def color_counts(self) -> dict[tuple[int, int, int], int]:
        c: Counter[tuple[int, int, int]] = Counter()
        for row in self.pixels:
            c.update(row)
        return dict(c)


@dataclass
class Capture:
    window_title: str
    framebuffer: Framebuffer
    marker_count: int = 0


class _Render:
    WHITE = WHITE
    MARKER_RGB = MARKER_RGB
    INTENDED_TITLE = INTENDED_TITLE
    CaptureTargetError = CaptureTargetError

    def paint_intended_surface(self) -> tuple[Framebuffer, dict[str, Any]]:
        fb = Framebuffer(160, 80)
        fb.fill_rect(0, 0, 160, 80, WHITE)
        high_bg = (8, 8, 16, 24)
        high_fg = (28, 8, 16, 24)
        low_bg = (80, 8, 16, 24)
        low_fg = (100, 8, 16, 24)
        btn = (8, 40, 48, 48)
        icon = (80, 40, 12, 12)
        marker = (120, 40, 32, 32)
        fb.fill_rect(*high_bg, WHITE)
        fb.fill_rect(*high_fg, NAVY)
        fb.fill_rect(*low_bg, GREY_BG)
        fb.fill_rect(*low_fg, GREY_FG)
        fb.fill_rect(*btn, NAVY)
        fb.fill_rect(*icon, NAVY)
        fb.fill_rect(*marker, MARKER_RGB)
        layout = {
            "high_bg_rect": high_bg,
            "high_fg_rect": high_fg,
            "low_bg_rect": low_bg,
            "low_fg_rect": low_fg,
            "primary_tap": btn,
            "icon_tap": icon,
            "marker_rect": marker,
        }
        return fb, layout

    def measure_intended_accessibility(self, fb: Framebuffer, layout: dict[str, Any]) -> dict[str, Any]:
        hf = layout["high_fg_rect"]
        hb = layout["high_bg_rect"]
        lf = layout["low_fg_rect"]
        lb = layout["low_bg_rect"]
        high_fg = fb.majority(*hf)
        high_bg = fb.majority(*hb)
        low_fg = fb.majority(*lf)
        low_bg = fb.majority(*lb)
        btn = layout["primary_tap"]
        icon = layout["icon_tap"]
        return {
            "contrasts": {
                "high": {
                    "contrast_ratio": contrast_ratio(high_fg, high_bg),
                    "fg_rgb": high_fg,
                    "bg_rgb": high_bg,
                    "method": "pixel-majority-sample",
                },
                "low": {
                    "contrast_ratio": contrast_ratio(low_fg, low_bg),
                    "fg_rgb": low_fg,
                    "bg_rgb": low_bg,
                    "method": "pixel-majority-sample",
                },
            },
            "tap_targets": (
                {"width_px": btn[2], "height_px": btn[3]},
                {"width_px": icon[2], "height_px": icon[3]},
            ),
        }

    def grab(self, intended: bool = True) -> Capture:
        fb, layout = self.paint_intended_surface()
        if not intended:
            fb.fill_rect(*layout["marker_rect"], WHITE)
            return Capture(window_title="decoy window", framebuffer=fb, marker_count=0)
        counts = fb.color_counts()
        return Capture(
            window_title=INTENDED_TITLE,
            framebuffer=fb,
            marker_count=int(counts.get(MARKER_RGB, 0)),
        )

    def assert_capture_target(self, capture: Capture) -> dict[str, Any]:
        if capture.window_title != INTENDED_TITLE:
            raise CaptureTargetError(f"title {capture.window_title!r} != {INTENDED_TITLE!r}")
        counts = capture.framebuffer.color_counts()
        n = int(counts.get(MARKER_RGB, 0))
        if n < 256:
            raise CaptureTargetError(f"marker_count {n}")
        return {"asserted": True, "marker_count": n}


render = _Render()
