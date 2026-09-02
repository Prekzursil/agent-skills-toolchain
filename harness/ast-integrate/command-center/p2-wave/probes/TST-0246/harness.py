#!/usr/bin/env python3
"""Shared campaign for TST-0246 probes and emit_report."""
from __future__ import annotations

from typing import Any

import hud
import render
import scan

UNIT = "TST-0246"
OUT_REL = "command-center/receipts/TST-0246.json"
SUT_REL = "command-center/p2-wave/probes/TST-0246/hud.py"
SCHEMA_REL = "command-center/schema/receipt.schema.json#/$defs/ux_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0246/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0246/probe2_rendered_width.py"
)

# Plant into the disk-row flag cell: "WARN" starts after
# time(8)+gap+panel(8)+gap+cache(7)+gap+age(5)+gap+value(8)+gap = 41
PLANT_LINE = 5  # 0=title 1=header 2=rule 3=cpu 4=mem 5=disk
PLANT_COL = 41  # first column of flag ("W" of WARN)
SEED = "\u26A0"
WIDE = "\u4E2D"  # CJK UNIFIED IDEOGRAPH-4E2D, EAW=W, wcwidth=2


def _line_measures(lines: list[str]) -> list[dict[str, Any]]:
    rows = []
    for n, line in enumerate(lines):
        m = render.measure_line(line)
        m["line_no"] = n
        m["designed_columns"] = hud.row_width()
        m["tmux_matches_designed"] = (
            m["tmux"].get("ok") is True and m["tmux_cursor_x"] == hud.row_width()
        )
        m["libc_matches_designed"] = m["libc_wcswidth"] == hud.row_width()
        m["wt_matches_designed"] = m["wt_model_columns"] == hud.row_width()
        rows.append(m)
    return rows


def campaign() -> dict[str, Any]:
    lines = hud.emit_lines()
    text = hud.emit_text()
    live_hits = scan.scan_text(text, naive=False)
    live_naive = scan.scan_text(text, naive=True)

    disk = lines[PLANT_LINE]
    planted_seed_line = hud.plant_in_line(disk, SEED, PLANT_COL)
    planted_wide_line = hud.plant_in_line(disk, WIDE, PLANT_COL)

    seed_hits = scan.scan_line(planted_seed_line, naive=False, line_no=PLANT_LINE)
    seed_naive = scan.scan_line(planted_seed_line, naive=True, line_no=PLANT_LINE)
    wide_hits = scan.scan_line(planted_wide_line, naive=False, line_no=PLANT_LINE)
    wide_naive = scan.scan_line(planted_wide_line, naive=True, line_no=PLANT_LINE)

    baseline = render.measure_line(disk)
    seed_m = render.measure_line(planted_seed_line)
    wide_m = render.measure_line(planted_wide_line)

    live_rows = _line_measures(lines)
    tmux_all_ok = all(r["tmux"].get("ok") for r in live_rows)
    tmux_all_match = all(r["tmux_matches_designed"] for r in live_rows)
    libc_all_match = all(r["libc_matches_designed"] for r in live_rows)

    # Probe-1 both-states: live silent; planted U+26A0 fires on the real
    # scanner and is invisible to W/F-only.
    seed_real_fired = any(h.get("codepoint") == "U+26A0" for h in seed_hits)
    seed_naive_blind = not any(h.get("codepoint") == "U+26A0" for h in seed_naive)
    wide_real_fired = bool(wide_hits)
    wide_naive_fired = bool(wide_naive)

    # Probe-2 both-states: replacing one ASCII cell with 中 keeps the
    # codepoint count unchanged (naive len()) but tmux cursor advances.
    codepoints_unchanged_on_wide_plant = wide_m["codepoints"] == baseline["codepoints"]
    tmux_wide_moved = (
        wide_m["tmux"].get("ok")
        and baseline["tmux"].get("ok")
        and wide_m["tmux_cursor_x"] is not None
        and baseline["tmux_cursor_x"] is not None
        and wide_m["tmux_cursor_x"] > baseline["tmux_cursor_x"]
    )
    libc_wide_moved = wide_m["libc_wcswidth"] > baseline["libc_wcswidth"]
    wt_seed_moved = seed_m["wt_model_columns"] > baseline["wt_model_columns"]

    detector_pass = (
        not live_hits
        and not live_naive
        and seed_real_fired
        and seed_naive_blind
        and wide_real_fired
        and wide_naive_fired
    )
    render_pass = (
        tmux_all_ok
        and tmux_all_match
        and libc_all_match
        and codepoints_unchanged_on_wide_plant
        and tmux_wide_moved
        and libc_wide_moved
        and wt_seed_moved
    )

    return {
        "unit_id": UNIT,
        "sut": SUT_REL,
        "production_hud": hud.production_hud(),
        "kind": hud.KIND,
        "designed_columns": hud.row_width(),
        "line_count": len(lines),
        "live_text": text,
        "live_hits": live_hits,
        "live_naive_hits": live_naive,
        "seed": scan.seed_properties(),
        "plant": {
            "line_no": PLANT_LINE,
            "col": PLANT_COL,
            "baseline": disk,
            "seed_line": planted_seed_line,
            "wide_line": planted_wide_line,
            "seed_hits": seed_hits,
            "seed_naive_hits": seed_naive,
            "wide_hits": wide_hits,
            "wide_naive_hits": wide_naive,
            "seed_real_fired": seed_real_fired,
            "seed_naive_blind": seed_naive_blind,
            "wide_real_fired": wide_real_fired,
            "wide_naive_fired": wide_naive_fired,
        },
        "render": {
            "live": live_rows,
            "baseline": baseline,
            "seed": seed_m,
            "wide": wide_m,
            "tmux_all_ok": tmux_all_ok,
            "tmux_all_match": tmux_all_match,
            "libc_all_match": libc_all_match,
            "codepoints_unchanged_on_wide_plant": codepoints_unchanged_on_wide_plant,
            "tmux_wide_moved": tmux_wide_moved,
            "libc_wide_moved": libc_wide_moved,
            "wt_seed_moved": wt_seed_moved,
            "linux_tmux_seed_width": (
                (seed_m["tmux_cursor_x"] - baseline["tmux_cursor_x"])
                if (
                    seed_m["tmux"].get("ok")
                    and baseline["tmux"].get("ok")
                    and seed_m["tmux_cursor_x"] is not None
                    and baseline["tmux_cursor_x"] is not None
                )
                else None
            ),
        },
        "detector_pass": detector_pass,
        "render_pass": render_pass,
        "pass": detector_pass and render_pass,
    }
