#!/usr/bin/env python3
"""Probe 2: rendered column count in a real terminal (signal b).

Each live HUD line is sent to a tmux pane; #{cursor_x} must equal the
designed single-width column count (and libc wcswidth agrees).

Both-states: replacing one ASCII cell with U+4E2D keeps the codepoint
count unchanged (so a len() assertion is blind) but tmux/wcwidth advance
by one extra column. U+26A0 is width-1 on this Linux tmux and width-2
under the Windows Terminal model — the catalog regression.

Mechanically different from probe 1 (no codepoint-class labels).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

ART = REPO / H.OUT_REL
SENTINEL = "SUCCESS:TST-0246"


def check_artifact_if_present() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    return None


def main() -> int:
    err = check_artifact_if_present()
    if err:
        print(f"FAILED:TST-0246-probe2 {err}")
        return 1

    camp = H.campaign()
    rnd = camp["render"]
    payload = {
        "pass": camp["render_pass"],
        "probe": "probe2-rendered-width",
        "unit_id": H.UNIT,
        "designed_columns": camp["designed_columns"],
        "tmux_all_ok": rnd["tmux_all_ok"],
        "tmux_all_match": rnd["tmux_all_match"],
        "libc_all_match": rnd["libc_all_match"],
        "codepoints_unchanged_on_wide_plant": rnd[
            "codepoints_unchanged_on_wide_plant"
        ],
        "tmux_wide_moved": rnd["tmux_wide_moved"],
        "libc_wide_moved": rnd["libc_wide_moved"],
        "wt_seed_moved": rnd["wt_seed_moved"],
        "linux_tmux_seed_width_delta": rnd["linux_tmux_seed_width"],
        "baseline_tmux": rnd["baseline"]["tmux_cursor_x"],
        "wide_tmux": rnd["wide"]["tmux_cursor_x"],
        "seed_tmux": rnd["seed"]["tmux_cursor_x"],
        "seed_wt_model": rnd["seed"]["wt_model_columns"],
        "method": "tmux #{cursor_x} plus libc wcswidth",
    }
    print(json.dumps(payload, sort_keys=True))
    if not rnd["tmux_all_ok"]:
        print("FAILED:TST-0246-probe2 tmux cursor query failed")
        return 1
    if not rnd["tmux_all_match"]:
        print("FAILED:TST-0246-probe2 tmux cursor_x != designed columns on a HUD line")
        return 1
    if not rnd["libc_all_match"]:
        print("FAILED:TST-0246-probe2 libc wcswidth != designed columns on a HUD line")
        return 1
    if not rnd["codepoints_unchanged_on_wide_plant"]:
        print("FAILED:TST-0246-probe2 wide plant changed codepoint count")
        return 1
    if not rnd["tmux_wide_moved"]:
        print("FAILED:TST-0246-probe2 tmux did not advance on planted U+4E2D")
        return 1
    if not rnd["libc_wide_moved"]:
        print("FAILED:TST-0246-probe2 libc wcswidth did not advance on planted U+4E2D")
        return 1
    if not rnd["wt_seed_moved"]:
        print("FAILED:TST-0246-probe2 WT model did not widen on planted U+26A0")
        return 1
    print(
        f"tmux_match={rnd['tmux_all_match']} libc_match={rnd['libc_all_match']} "
        f"wide_delta_tmux="
        f"{(rnd['wide']['tmux_cursor_x'] or 0) - (rnd['baseline']['tmux_cursor_x'] or 0)} "
        f"U+26A0_linux_delta={rnd['linux_tmux_seed_width']} "
        f"U+26A0_WT_model_delta="
        f"{rnd['seed']['wt_model_columns'] - rnd['baseline']['wt_model_columns']}"
    )
    print(
        "SUCCESS:TST-0246-probe2 tmux rendered columns match designed width; "
        "planted width-2 moves the cursor"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
