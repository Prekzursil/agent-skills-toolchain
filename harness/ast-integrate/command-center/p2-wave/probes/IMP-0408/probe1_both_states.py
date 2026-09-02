#!/usr/bin/env python3
"""Probe 1: both-states over a 20s window — ALIVE vs NOT-ALIVE, same code path."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from session_liveness.harness import finished_session, live_session  # noqa: E402
from session_liveness.liveness import (  # noqa: E402
    EVIDENCE_WINDOW_SECONDS,
    VERDICT_ALIVE,
    VERDICT_NOT_ALIVE,
    measure_pair,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0408-probe1-") as tmp:
        root = Path(tmp)
        with live_session(root) as live, finished_session(root) as finished:
            live_r, fin_r = measure_pair(
                live,
                finished,
                window_seconds=EVIDENCE_WINDOW_SECONDS,
            )

    payload = {
        "pass": False,
        "probe": "probe1-both-states",
        "unit_id": "IMP-0408",
        "window_seconds": EVIDENCE_WINDOW_SECONDS,
        "same_code_path": "session_liveness.liveness.measure_pair",
        "signals": ["process-cpu-delta", "artifact-byte-growth"],
        "live": live_r.to_dict(),
        "finished": fin_r.to_dict(),
        "verdicts_differ": live_r.verdict != fin_r.verdict,
    }
    ok = (
        live_r.verdict == VERDICT_ALIVE
        and fin_r.verdict == VERDICT_NOT_ALIVE
        and live_r.cpu_delta > 0
        and live_r.byte_growth > 0
        and fin_r.cpu_delta <= 0
        and fin_r.byte_growth <= 0
        and live_r.verdict != fin_r.verdict
        and live_r.signals_used == fin_r.signals_used
    )
    payload["pass"] = bool(ok)
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        print(
            "FAILED:IMP-0408-probe1 both-states "
            f"live={live_r.verdict} finished={fin_r.verdict} "
            f"cpu_live={live_r.cpu_delta} bytes_live={live_r.byte_growth} "
            f"cpu_fin={fin_r.cpu_delta} bytes_fin={fin_r.byte_growth}"
        )
        return 1
    print(
        "SUCCESS:IMP-0408-probe1 both-states ALIVE vs NOT-ALIVE "
        f"over {int(EVIDENCE_WINDOW_SECONDS)}s two-signal window"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
