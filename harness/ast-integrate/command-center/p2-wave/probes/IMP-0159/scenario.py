"""Shared IMP-0159 fixture loaders and injected clocks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from candidates.freshness import (  # noqa: E402
    CandidateEvidence,
    InjectedClock,
    candidate_from_dict,
    load_ttl_table,
)

FIXTURE = HERE / "fixtures" / "candidates.json"
TTL_SUBJECT = "cand.live-advisory.clock-subject"
ARCHIVED_ID = "cand.source-repo.archived"
MAINTAINED_ID = "cand.source-repo.maintained"
MISSING_ID = "cand.unmeasured.missing-verified"
T0 = 1_700_000_000
CLOCK_WITHIN = InjectedClock(T0 + 12 * 3600)
CLOCK_PAST = InjectedClock(T0 + 86400 + 1)


def load_raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def load_candidates() -> list[CandidateEvidence]:
    doc = load_raw()
    return [candidate_from_dict(row) for row in doc["candidates"]]


def by_id(rows: list[CandidateEvidence]) -> dict[str, CandidateEvidence]:
    return {row.candidate_id: row for row in rows}


def ttl_policy():
    return load_ttl_table()
