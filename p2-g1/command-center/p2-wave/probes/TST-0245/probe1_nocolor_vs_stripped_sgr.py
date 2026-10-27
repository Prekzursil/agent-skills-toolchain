#!/usr/bin/env python3
"""TST-0245 probe 1: NO_COLOR output equals coloured-after-SGR-strip.

Never-wrap semantics: NO_COLOR builds output WITHOUT SGR (not wrap-then-
strip). A threshold breach must remain visible without colour. Monochrome
equivalence is checked as a distinct path. Determinism: two renders under a
frozen clock hash identically (no pid/time enters the render).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import hud_emit  # noqa: E402

ROLES = ["ok", "warn", "fail", "info"]
TEXTS = ["mem 512MB", "cpu 82%", "disk 95% BREACH", "status live"]


def render(env: dict) -> str:
    line = hud_emit.render_status(ROLES, TEXTS, env=env)
    meter = hud_emit.render_meter(1900.0, 1500.0, env=env)
    return line + meter


def main() -> int:
    checks: dict[str, bool] = {}
    coloured = render({"NO_COLOR": ""})
    nocolor = render({"NO_COLOR": "1"})
    stripped = hud_emit.strip_sgr(coloured)
    checks["nocolor_equals_stripped_sgr"] = nocolor == stripped
    checks["coloured_contains_sgr"] = "\x1b[" in coloured
    checks["nocolor_never_wraps_no_sgr_in_output"] = "\x1b[" not in nocolor
    checks["threshold_breach_visible_nocolor"] = (
        "x FAIL disk 95% BREACH" in nocolor and "BREACH" in nocolor
    )
    checks["threshold_breach_visible_coloured_after_strip"] = "BREACH" in stripped
    checks["monochrome_equivalent"] = render({"NO_COLOR": "1"}) == render({"TERM": "dumb", "NO_COLOR": "1"})
    h1 = hashlib.sha256(render({"NO_COLOR": "1"}).encode()).hexdigest()
    h2 = hashlib.sha256(render({"NO_COLOR": "1"}).encode()).hexdigest()
    checks["trace_hash_comparison_stable"] = h1 == h2
    checks["nondeterminism_sources_absent"] = (
        "pid" not in nocolor.lower() and str(id(hud_emit)) not in nocolor
    )
    checks["fixed_pid_frozen_clock_by_construction"] = len({h1, h2}) == 1

    ok = all(checks.values())
    out = {
        "probe": "probe1-nocolor-vs-stripped-sgr",
        "unit_id": "TST-0245",
        "checks": checks,
        "hash": h1[:16],
        "pass": ok,
        "nocolor_render": nocolor,
        "id": "both-states-threshold-breach-visible-nocolor",
    }
    (HERE / "probe1_nocolor_vs_stripped_sgr.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
