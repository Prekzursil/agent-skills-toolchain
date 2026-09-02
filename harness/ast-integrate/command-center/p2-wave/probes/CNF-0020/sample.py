"""Sampling frame and seeded draw for CNF-0020.

The reviewer re-draws with the same seed and must obtain the identical sample.
A different seed is the both-states control that the seed is doing work.
"""
from __future__ import annotations

import hashlib
import json
import random
from typing import Any

UNIT = "CNF-0020"
SEED = 20260824
SAMPLE_EXTRA = 3
ALWAYS_INCLUDE_INTERMITTENT = "F-COIN-P30"
ALWAYS_INCLUDE_DETERMINISTIC = "F-ALWAYS-RED"

# Catalog-named baseline suspects plus instrumented fixtures that can actually
# run on this Linux worktree. Phase-0 BASELINE-SNAPSHOT.json is absent here.
FRAME: list[dict[str, Any]] = [
    {
        "id": "F-CRLF-ARTEFACT",
        "suspected_intermittent": True,
        "claimed_deterministic": False,
        "reason": (
            "CNF-0018 names three Phase-0 CRLF-artefact failures. Autocrlf can "
            "make a CRLF detector look intermittent across routes; measure the rate."
        ),
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/CNF-0020/failures.py --id F-CRLF-ARTEFACT"
        ),
        "recorded_conditions": {
            "concurrency": 1,
            "load": "idle",
            "hypothesis": "crlf-artefact",
        },
    },
    {
        "id": "F-COIN-P30",
        "suspected_intermittent": True,
        "claimed_deterministic": False,
        "reason": (
            "Calibrated Bernoulli flake (p~0.3) so the harness is shown to keep "
            "mixed RED/GREEN vectors instead of collapsing to the last run."
        ),
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/CNF-0020/failures.py --id F-COIN-P30"
        ),
        "recorded_conditions": {
            "concurrency": 1,
            "load": "idle",
            "hypothesis": "flake",
        },
    },
    {
        "id": "F-RACE-COUNTER",
        "suspected_intermittent": True,
        "claimed_deterministic": False,
        "reason": "Unsynchronized counter under recorded concurrency; scheduling flake.",
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/CNF-0020/failures.py --id F-RACE-COUNTER"
        ),
        "recorded_conditions": {
            "concurrency": 8,
            "load": "contended-counter",
            "hypothesis": "race",
        },
    },
    {
        "id": "F-NEVER-REPRO",
        "suspected_intermittent": True,
        "claimed_deterministic": False,
        "reason": "Suspected intermittent that does not reproduce (always GREEN).",
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/CNF-0020/failures.py --id F-NEVER-REPRO"
        ),
        "recorded_conditions": {
            "concurrency": 1,
            "load": "idle",
            "hypothesis": "not-reproducible",
        },
    },
    {
        "id": "F-LOAD-CONC4",
        "suspected_intermittent": True,
        "claimed_deterministic": False,
        "reason": "Load-sensitive collision under the recorded concurrency=4 condition.",
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/CNF-0020/failures.py --id F-LOAD-CONC4"
        ),
        "recorded_conditions": {
            "concurrency": 4,
            "load": "four-workers",
            "hypothesis": "load-sensitive",
        },
    },
    {
        "id": "F-TIME-JITTER",
        "suspected_intermittent": True,
        "claimed_deterministic": False,
        "reason": "Clock-modulo jitter (~1-in-5) as a timing-class intermittent.",
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/CNF-0020/failures.py --id F-TIME-JITTER"
        ),
        "recorded_conditions": {
            "concurrency": 1,
            "load": "idle",
            "hypothesis": "timing",
        },
    },
    {
        "id": "F-ALWAYS-RED",
        "suspected_intermittent": False,
        "claimed_deterministic": True,
        "reason": (
            "Control claimed deterministic: must be 50 of 50 RED or be "
            "reclassified as intermittent."
        ),
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/CNF-0020/failures.py --id F-ALWAYS-RED"
        ),
        "recorded_conditions": {
            "concurrency": 1,
            "load": "idle",
            "hypothesis": "deterministic",
        },
    },
]


def frame_by_id() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in FRAME}


def suspect_ids() -> list[str]:
    return [row["id"] for row in FRAME if row["suspected_intermittent"]]


def draw_sample(seed: int = SEED) -> list[str]:
    """Return the ordered sample of suspected-intermittent failures.

    F-COIN-P30 is always first so the mixed-vector control is in every draw.
    Three further suspects are drawn without replacement from the remaining pool.
    """
    rng = random.Random(seed)
    pool = [i for i in suspect_ids() if i != ALWAYS_INCLUDE_INTERMITTENT]
    pool.sort()
    extra = rng.sample(pool, SAMPLE_EXTRA)
    return [ALWAYS_INCLUDE_INTERMITTENT] + extra


def measured_ids(seed: int = SEED) -> list[str]:
    """Sampled suspects plus the claimed-deterministic control."""
    return draw_sample(seed) + [ALWAYS_INCLUDE_DETERMINISTIC]


def frame_canonical() -> str:
    return json.dumps(FRAME, sort_keys=True, separators=(",", ":"))


def frame_sha256() -> str:
    return hashlib.sha256(frame_canonical().encode("utf-8")).hexdigest()
