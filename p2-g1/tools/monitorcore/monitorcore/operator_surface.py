"""Operator-surface a11y contract (TST-0114): glyph widths, NO_COLOR, contrast.

Pure and terminal-free: themes are RGB palettes, captures are P3 PPM text,
and every renderer is deterministic so probes can re-derive the pixels.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

THEMES: tuple[str, ...] = ("dark", "light")

# WCAG 2.1 AA: normal text 4.5:1, non-text focus indicators 3:1.
TEXT_CONTRAST_THRESHOLD = 4.5
FOCUS_CONTRAST_THRESHOLD = 3.0

PALETTES: dict[str, dict[str, tuple[int, int, int]]] = {
    "dark": {
        "bg": (18, 18, 18),
        "fg": (224, 224, 224),
        "accent": (102, 178, 255),
        "focus": (255, 196, 0),
    },
    "light": {
        "bg": (255, 255, 255),
        "fg": (33, 33, 33),
        "accent": (0, 90, 156),
        "focus": (139, 0, 0),
    },
}

GRID_W = 80
GRID_H = 24

_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")

KEY_BINDINGS: dict[str, str] = {
    "codex": "1",
    "agents": "2",
    "workflows": "3",
    "databricks": "4",
    "mcp": "5",
    "program": "6",
}


# --- glyph widths -----------------------------------------------------------

def _is_double_width(ch: str) -> bool:
    code = ord(ch)
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return True
    # Symbols/emoji commonly rendered double-width in terminals (incl. U+26A0).
    if 0x2600 <= code <= 0x27BF:
        return True
    if 0x1F000 <= code <= 0x1FAFF:
        return True
    return code == 0xFE0F


def double_width_hits(text: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for idx, ch in enumerate(strip_sgr(text)):
        if _is_double_width(ch):
            hits.append(
                {
                    "char": ch,
                    "codepoint": f"U+{ord(ch):04X}",
                    "eaw": unicodedata.east_asian_width(ch),
                    "index": idx,
                }
            )
    return hits


def glyph_scan(text: str) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for ch in strip_sgr(text):
        if ch in seen or ch in ("\n", "\r"):
            continue
        seen[ch] = {
            "char": ch,
            "codepoint": f"U+{ord(ch):04X}",
            "eaw": unicodedata.east_asian_width(ch),
            "width": 2 if _is_double_width(ch) else 1,
        }
    return list(seen.values())


def planted_double_width_line() -> str:
    return "planted control: \u26a0 warning sign is double-width"


# --- SGR / NO_COLOR ---------------------------------------------------------

def strip_sgr(text: str) -> str:
    return _SGR_RE.sub("", text)


def color_only_signal(ok: bool) -> str:
    """A red/green pair that differs ONLY in colour (collapses after strip)."""
    sgr = "\x1b[32m" if ok else "\x1b[31m"
    return f"{sgr}STATUS\x1b[0m"


# --- keyboard / focus -------------------------------------------------------

def keyboard_map(panes: list[str]) -> dict[str, str]:
    """Key binding per pane; an unbound pane is a hard KeyError, never silent."""
    out: dict[str, str] = {}
    for pane in panes:
        if pane not in KEY_BINDINGS:
            raise KeyError(f"no key bound for pane {pane!r}")
        out[pane] = KEY_BINDINGS[pane]
    return out


# --- contrast ---------------------------------------------------------------

def _srgb_to_lin(channel: int) -> float:
    x = channel / 255.0
    if x <= 0.04045:
        return x / 12.92
    return ((x + 0.055) / 1.055) ** 2.4


def _rel_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _srgb_to_lin(r) + 0.7152 * _srgb_to_lin(g) + 0.0722 * _srgb_to_lin(b)


def contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    a, b = _rel_luminance(tuple(fg)), _rel_luminance(tuple(bg))
    hi, lo = (a, b) if a >= b else (b, a)
    return (hi + 0.05) / (lo + 0.05)


# --- captures (P3 PPM) ------------------------------------------------------

Grid = list[list[tuple[int, int, int]]]


def _quadrant_grid(
    fg: tuple[int, int, int],
    accent: tuple[int, int, int],
    focus: tuple[int, int, int],
    bg: tuple[int, int, int],
) -> Grid:
    grid: Grid = []
    for y in range(GRID_H):
        row: list[tuple[int, int, int]] = []
        for x in range(GRID_W):
            top = y < GRID_H // 2
            left = x < GRID_W // 2
            if top and left:
                row.append(fg)
            elif top:
                row.append(accent)
            elif left:
                row.append(focus)
            else:
                row.append(bg)
        grid.append(row)
    return grid


def render_theme_grid(theme: str) -> Grid:
    pal = PALETTES[theme]
    return _quadrant_grid(pal["fg"], pal["accent"], pal["focus"], pal["bg"])


def decoy_low_contrast_grid() -> Grid:
    """Yellow-on-white: a pair that MUST fail the text threshold (detector control)."""
    yellow = (255, 255, 0)
    white = (255, 255, 255)
    return _quadrant_grid(yellow, yellow, yellow, white)


def sample_capture_pairs(grid: Grid) -> dict[str, dict[str, tuple[int, int, int]]]:
    def pix(x: int, y: int) -> tuple[int, int, int]:
        return grid[y][x]

    return {
        "fg_on_bg": {"fg": pix(20, 6), "bg": pix(60, 18)},
        "accent_on_bg": {"fg": pix(60, 6), "bg": pix(60, 18)},
        "focus_on_bg": {"fg": pix(20, 18), "bg": pix(60, 18)},
    }


def write_ppm_p3(grid: Grid) -> str:
    height = len(grid)
    width = len(grid[0]) if grid else 0
    lines = ["P3", f"{width} {height}", "255"]
    for row in grid:
        lines.append(" ".join(f"{r} {g} {b}" for r, g, b in row))
    return "\n".join(lines) + "\n"


__all__ = [
    "FOCUS_CONTRAST_THRESHOLD",
    "GRID_H",
    "GRID_W",
    "KEY_BINDINGS",
    "PALETTES",
    "TEXT_CONTRAST_THRESHOLD",
    "THEMES",
    "color_only_signal",
    "contrast_ratio",
    "decoy_low_contrast_grid",
    "double_width_hits",
    "glyph_scan",
    "keyboard_map",
    "planted_double_width_line",
    "render_theme_grid",
    "sample_capture_pairs",
    "strip_sgr",
    "write_ppm_p3",
]
