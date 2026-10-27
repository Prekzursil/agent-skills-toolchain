#!/usr/bin/env python3
"""TST-0247 probe B: TUI field set vs ``--plain``, plus the both-states control.

Signal (b): the field set rendered by the production TUI — every pane's
``frame()`` painted exactly as the interactive cockpit paints it
(``cursor=True``) — parsed by the SAME shared parser as probe A. The unit's
PASS predicate is the mechanical set comparison: ``only_plain`` and
``only_tui`` must both be empty. The both-states control then hides the
``health.driver`` marker from the TUI text and requires the differ to fire
(mutant oracle exit 1) while the unmuted baseline compares clean (exit 0).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fieldparse import parse_fields  # noqa: E402


def plain_fields() -> set[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO / "tools" / "monitorcore"), env.get("PYTHONPATH", "")]
    )
    p = subprocess.run(
        [sys.executable, "-m", "monitorcore.unified", "--plain", "--once"],
        cwd=str(REPO),
        capture_output=True,
        env=env,
        timeout=600,
    )
    if p.returncode != 0:
        raise SystemExit(f"FAILED:plain-subprocess rc={p.returncode}")
    return parse_fields(p.stdout.decode("utf-8", errors="replace").splitlines())


def tui_lines() -> list[str]:
    """Production render: frame() of every pane, cursor ON, as the cockpit paints."""
    import time

    sys.path.insert(0, str(REPO / "tools" / "monitorcore"))
    from monitorcore.pane_views import PANES
    from monitorcore.unified import BoardState, _build_parser, default_sources, frame, poll_all

    args = _build_parser().parse_args(["--once"])
    srcs = default_sources(args)
    snaps = poll_all(srcs, clock=time.time)
    now = time.time()
    lines: list[str] = []
    for pane in PANES:
        fr = frame(
            BoardState(pane=pane.id),
            snaps=snaps,
            panes=PANES,
            cols=120,
            now=now,
            cursor=True,
        )
        lines.extend(fr.lines)
    return lines


def differ(baseline: set[str], candidate: set[str]) -> tuple[set[str], set[str]]:
    return baseline - candidate, candidate - baseline


def main() -> int:
    checks: dict[str, bool] = {}
    plain = plain_fields()
    tui_lines_good = tui_lines()
    tui = parse_fields(tui_lines_good)
    only_plain, only_tui = differ(plain, tui)
    checks["field_sets_equal"] = not only_plain and not only_tui
    checks["tui_field_floor_met"] = len(tui) >= 40

    # Both-states control: hiding a field from the TUI must show up as a set
    # difference. GOOD oracle: the baseline compared against itself parses to
    # the same set and health.driver is present -> differ silent, exit 0.
    # BAD oracle: the health driver marker is dropped from the rendered text;
    # the differ must LOSE health.driver in the mutant parse (fires, exit 1).
    good_oracle_exit_0 = "health.driver" in tui and differ(
        tui, parse_fields(tui_lines_good)
    ) == (set(), set())
    mutant_lines = []
    for ln in tui_lines_good:
        if " phys " in ln and " driver " in ln:
            ln = ln.split(" phys ", 1)[0]  # drop everything from phys onward
        mutant_lines.append(ln)
    mutant_fields = parse_fields(mutant_lines)
    bad_oracle_exit_1 = "health.driver" in tui and "health.driver" not in mutant_fields

    checks["nc_good_state_silent"] = good_oracle_exit_0
    checks["nc_bad_state_fires"] = bad_oracle_exit_1

    out = {
        "probe": "probe_tui_field_set",
        "unit": "TST-0247",
        "signal": "(b) the field set rendered by the TUI panes, compared mechanically",
        "plain_field_count": len(plain),
        "tui_field_count": len(tui),
        "only_plain": sorted(only_plain),
        "only_tui": sorted(only_tui),
        "field_sets_equal": not only_plain and not only_tui,
        "negative_control": {
            "id": "TST0247-NC-HIDE-TUI-FIELD",
            "mutation": "hide health.driver by dropping its rendered segment",
            "fired_on_bad_state": bad_oracle_exit_1,
            "silent_on_good_state": good_oracle_exit_0,
        },
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe-b-tui-field-set.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
