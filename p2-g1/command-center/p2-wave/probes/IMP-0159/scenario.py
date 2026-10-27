"""Fixture loader for the IMP-0159 freshness probes (injected clock only)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parents[3]) not in sys.path:
    sys.path.insert(0, str(HERE.parents[3]))

from tools.candidates.freshness import InjectedClock, TtlTable, candidate_from_dict  # noqa: E402

CLOCK_WITHIN = 1700043200
CLOCK_PAST = 1700086401


def load_rows():
    doc = json.loads((HERE / "fixtures" / "candidates.json").read_text(encoding="utf-8"))
    return [candidate_from_dict(r) for r in doc["candidates"]]


def clock_within() -> InjectedClock:
    return InjectedClock(now_unix=CLOCK_WITHIN)


def clock_past() -> InjectedClock:
    return InjectedClock(now_unix=CLOCK_PAST)


def ttl_table() -> TtlTable:
    return TtlTable(classes={
        "live-advisory": 86400,
        "source-repo": 604800,
        "measurement": 3600,
        "maintenance-cache": 86400,
        "unmeasured-class": 86400,
    })
