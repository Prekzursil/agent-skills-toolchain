#!/usr/bin/env python3
"""Known-broken fixture: classify liveness from file mtime alone.

This is the detector control. Equal-mtime stalled and finished files
must produce the SAME verdict. The orchestrator monitor must not.
"""
from __future__ import annotations

import time
from pathlib import Path

# Anything whose mtime is older than this is called STALLED.
STALE_S = 60.0


def classify_mtime_only(path: Path, *, now: float | None = None) -> dict:
    now = time.time() if now is None else float(now)
    if not path.is_file():
        return {
            "verdict": "DEAD",
            "data_source": f"mtime-only:{path}:missing",
            "mtime_used": True,
            "age_s": None,
        }
    mtime = path.stat().st_mtime
    age = now - mtime
    verdict = "STALLED" if age > STALE_S else "LIVE"
    return {
        "verdict": verdict,
        "data_source": f"mtime-only:{path}:st_mtime={mtime:.3f}:age_s={age:.3f}",
        "mtime_used": True,
        "age_s": age,
        "mtime": mtime,
    }
