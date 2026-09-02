"""Live operator-surface measurements used by TST-0114 probes and emit."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "monitorcore"))

from monitorcore.cockpit import Cockpit  # noqa: E402
from monitorcore.operator_surface import (  # noqa: E402
    FOCUS_CONTRAST_THRESHOLD,
    TEXT_CONTRAST_THRESHOLD,
    THEMES,
    color_only_signal,
    contrast_ratio,
    decoy_low_contrast_grid,
    double_width_hits,
    glyph_scan,
    keyboard_map,
    planted_double_width_line,
    render_theme_grid,
    sample_capture_pairs,
    strip_sgr,
    write_ppm_p3,
)

ART = REPO / "command-center" / "receipts" / "TST-0114.json"
CAPTURES = HERE / "captures"


def make_cockpit() -> Cockpit:
    return Cockpit(REPO)


def live_surfaces(cock: Cockpit | None = None) -> dict[str, str]:
    cock = cock or make_cockpit()
    out: dict[str, str] = {}
    for pane in cock.pane_ids():
        out[f"pane:{pane}"] = cock.render_pane(pane)
    saved = os.environ.get("NO_COLOR")
    try:
        os.environ.pop("NO_COLOR", None)
        for theme in THEMES:
            out[f"status:{theme}:color"] = cock.render_status_line(
                theme=theme, color=True
            )
            out[f"status:{theme}:nocolor"] = cock.render_status_line(
                theme=theme, color=False
            )
        out["screen_reader"] = cock.render_screen_reader()
    finally:
        if saved is None:
            os.environ.pop("NO_COLOR", None)
        else:
            os.environ["NO_COLOR"] = saved
    return out


def width_report(surfaces: dict[str, str]) -> dict[str, Any]:
    per: dict[str, Any] = {}
    live_hits: list[dict[str, Any]] = []
    for name, text in surfaces.items():
        hits = double_width_hits(text)
        per[name] = {
            "double_width": hits,
            "scan_sample": glyph_scan(text)[:6],
        }
        for hit in hits:
            live_hits.append({"surface": name, **hit})
    planted = planted_double_width_line()
    planted_hits = double_width_hits(planted)
    return {
        "live_double_width": live_hits,
        "live_clean": not live_hits,
        "planted_line": planted,
        "planted_hits": planted_hits,
        "planted_detected": bool(planted_hits),
        "per_surface": per,
    }


def nocolor_report(cock: Cockpit | None = None) -> dict[str, Any]:
    cock = cock or make_cockpit()
    themes: dict[str, Any] = {}
    ok = True
    for theme in THEMES:
        colored = cock.render_status_line(theme=theme, color=True)
        plain = cock.render_status_line(theme=theme, color=False)
        stripped = strip_sgr(colored)
        match = stripped == plain
        themes[theme] = {
            "colored_has_sgr": "\x1b[" in colored,
            "plain_has_sgr": "\x1b[" in plain,
            "stripped_equals_plain": match,
            "plain": plain,
            "has_focus_token": "[FOCUS]" in plain,
            "has_status_token": any(t in plain for t in ("[OK]", "[FAIL]", "[WARN]")),
        }
        if not match or "\x1b[" in plain:
            ok = False
        if not themes[theme]["has_focus_token"] or not themes[theme]["has_status_token"]:
            ok = False
        if not themes[theme]["colored_has_sgr"]:
            ok = False
    collapsed = strip_sgr(color_only_signal(True)) == strip_sgr(color_only_signal(False))
    saved = os.environ.get("NO_COLOR")
    try:
        os.environ["NO_COLOR"] = "1"
        env_plain = cock.render_status_line(theme="dark", color=None)
    finally:
        if saved is None:
            os.environ.pop("NO_COLOR", None)
        else:
            os.environ["NO_COLOR"] = saved
    env_ok = "\x1b[" not in env_plain
    return {
        "themes": themes,
        "color_only_collapsed": collapsed,
        "NO_COLOR_env_honoured": env_ok,
        "env_plain": env_plain,
        "pass": ok and collapsed and env_ok,
    }


def a11y_inventory_report(cock: Cockpit | None = None) -> dict[str, Any]:
    cock = cock or make_cockpit()
    panes = list(cock.pane_ids())
    sr = cock.render_screen_reader()
    needed = (
        "focused_pane",
        "theme",
        "events",
        "receipts",
        "status",
        "keyboard_map",
    )
    missing = [field for field in needed if f"label: {field} " not in sr]
    status = cock.render_status_line(theme="dark", color=False)
    focus_visible = status.startswith("> ") and "[FOCUS]" in status
    keys_error = None
    try:
        keys = keyboard_map(panes)
        keys_ok = True
    except KeyError as exc:
        keys = {}
        keys_ok = False
        keys_error = str(exc)
    planted_caught = False
    planted_detail = None
    try:
        keyboard_map(list(panes) + ["secret"])
    except KeyError as exc:
        planted_caught = True
        planted_detail = str(exc)
    return {
        "panes": panes,
        "keyboard": keys,
        "keyboard_ok": keys_ok,
        "keyboard_error": keys_error,
        "screen_reader": sr,
        "missing_labels": missing,
        "focus_visible": focus_visible,
        "status_plain": status,
        "planted_unbound_pane_caught": planted_caught,
        "planted_unbound_detail": planted_detail,
        "pass": keys_ok and not missing and focus_visible and planted_caught,
    }


def write_captures() -> dict[str, str]:
    CAPTURES.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for theme in THEMES:
        rel = f"command-center/p2-wave/probes/TST-0114/captures/theme-{theme}.ppm"
        (REPO / rel).write_text(
            write_ppm_p3(render_theme_grid(theme)), encoding="utf-8", newline="\n"
        )
        paths[theme] = rel
    decoy_rel = "command-center/p2-wave/probes/TST-0114/captures/decoy-low-contrast.ppm"
    (REPO / decoy_rel).write_text(
        write_ppm_p3(decoy_low_contrast_grid()), encoding="utf-8", newline="\n"
    )
    paths["decoy"] = decoy_rel
    return paths


def product_contrast_table() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for theme in THEMES:
        pairs = sample_capture_pairs(render_theme_grid(theme))
        measured = {}
        for name, pair in pairs.items():
            ratio = contrast_ratio(pair["fg"], pair["bg"])
            threshold = (
                FOCUS_CONTRAST_THRESHOLD
                if name.startswith("focus")
                else TEXT_CONTRAST_THRESHOLD
            )
            measured[name] = {
                "fg": list(pair["fg"]),
                "bg": list(pair["bg"]),
                "ratio": round(ratio, 4),
                "threshold": threshold,
                "pass": ratio >= threshold,
            }
        rows[theme] = measured
    decoy_pairs = sample_capture_pairs(decoy_low_contrast_grid())
    decoy_ratio = contrast_ratio(
        decoy_pairs["fg_on_bg"]["fg"], decoy_pairs["fg_on_bg"]["bg"]
    )
    rows["decoy"] = {
        "fg_on_bg": {
            "fg": list(decoy_pairs["fg_on_bg"]["fg"]),
            "bg": list(decoy_pairs["fg_on_bg"]["bg"]),
            "ratio": round(decoy_ratio, 4),
            "threshold": TEXT_CONTRAST_THRESHOLD,
            "pass": decoy_ratio >= TEXT_CONTRAST_THRESHOLD,
        }
    }
    return rows


def load_receipt() -> dict[str, Any] | None:
    if not ART.is_file():
        return None
    return json.loads(ART.read_text(encoding="utf-8"))
