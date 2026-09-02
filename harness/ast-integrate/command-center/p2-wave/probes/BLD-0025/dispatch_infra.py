"""Replica of dispatch_cursor.reap_one strike/INFRA gating, bound to live source.

The live runner treats predicate:absent as INFRA and does not append a strike.
That is unobservable retry: the supervisor will re-queue the unit with no
attempt record in /opt/p2/strikes.
"""
from __future__ import annotations

from pathlib import Path

DISPATCH_REL = "command-center/p2-wave/seed-stage/dispatch_cursor.py"
INFRA_SNIPPET = (
    'if fp in {"auth-missing", "predicate:absent"} or runtime < 45:'
)
STRIKE_SNIPPET = 'rec["attempts"].append'
BRINGUP_REL = "command-center/p2-wave/seed-stage/bringup_cursor_fleet.py"
BRINGUP_SNIPPET = 'for root in ("root-volume=block:80GB", "root-volume=sbs_volume:80GB", None):'
MEASURE_REL = "command-center/p2-wave/_measure_one_delivered.py"
MEASURE_SNIPPET = "p = subprocess.run("
P2LIB_REL = "command-center/p2-wave/_p2lib.py"
P2LIB_SNIPPET = "r = subprocess.run("


def _line_of(text: str, snippet: str) -> int:
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        if snippet in line:
            return i
    return 0


def live_anchors(repo: Path) -> dict:
    dispatch = (repo / DISPATCH_REL).read_text(encoding="utf-8")
    bringup = (repo / BRINGUP_REL).read_text(encoding="utf-8")
    measure = (repo / MEASURE_REL).read_text(encoding="utf-8")
    p2lib = (repo / P2LIB_REL).read_text(encoding="utf-8")
    return {
        "dispatch": {
            "path": DISPATCH_REL,
            "infra_present": INFRA_SNIPPET in dispatch,
            "infra_line": _line_of(dispatch, INFRA_SNIPPET),
            "strike_present": STRIKE_SNIPPET in dispatch,
            "strike_line": _line_of(dispatch, STRIKE_SNIPPET),
            "snippet": INFRA_SNIPPET,
        },
        "bringup": {
            "path": BRINGUP_REL,
            "loop_present": BRINGUP_SNIPPET in bringup,
            "loop_line": _line_of(bringup, "for root in ("),
            "snippet": BRINGUP_SNIPPET,
        },
        "measure_run_cmd": {
            "path": MEASURE_REL,
            "line": _line_of(measure, MEASURE_SNIPPET),
            "snippet": MEASURE_SNIPPET,
        },
        "p2lib_run": {
            "path": P2LIB_REL,
            "line": _line_of(p2lib, P2LIB_SNIPPET),
            "snippet": P2LIB_SNIPPET,
        },
    }


def would_record_strike(fp: str, runtime: float) -> bool:
    """Same predicate as dispatch_cursor.reap_one (live source INFRA_SNIPPET)."""
    if fp in {"auth-missing", "predicate:absent"} or runtime < 45:
        return False
    return True


def simulate_infra_fail_then_succeed() -> dict:
    """Attempt 1: predicate:absent at runtime 12s. Attempt 2: green.

    Strike file stays empty. First-attempt error is not in attempts[].
    """
    a1 = would_record_strike("predicate:absent", 12.0)
    first = "FAILED:delivered BLD-0025 predicate:absent"
    return {
        "attempt_count_distribution": {
            "1": {"ok": False, "error": first, "strike_recorded": a1},
            "2": {"ok": True, "error": None, "strike_recorded": False},
        },
        "first_attempt_error": first,
        "success_attempt": 2,
        "telemetry_present": a1,
        "always_fails_once": True,
    }
