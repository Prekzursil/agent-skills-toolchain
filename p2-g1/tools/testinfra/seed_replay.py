"""Deterministic seed record-and-replay for randomised suites (TST-0027, rebuild).

Three properties, all proven live by probes/TST-0027/probe2:
  1. a run records the seed it used (record_run);
  2. replaying from that seed alone reproduces a BYTE-IDENTICAL trace
     (replay same seed twice -> identical trace_sha256);
  3. a different seed yields a DIFFERENT trace (the seed is load-bearing).
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Trace:
    seed: int
    steps: list[int]

    def trace_sha256(self) -> str:
        blob = json.dumps({"seed": self.seed, "steps": self.steps}, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()


def seeded_trace(seed: int, steps: int = 24) -> Trace:
    """One randomised-suite-shaped run: a seeded RNG walked for N steps."""
    rng = random.Random(seed)
    return Trace(seed=seed, steps=[rng.randrange(2**32) for _ in range(steps)])


def record_run(seed: int | None, steps: int = 24) -> dict[str, Any]:
    """Run once; if the caller passed no seed, fresh entropy is used AND recorded."""
    used = int(seed) if seed is not None else int.from_bytes(random.SystemRandom().randbytes(6), "big")
    trace = seeded_trace(used, steps)
    return {
        "seed_recorded": used,
        "entropy_was_fresh": seed is None,
        "trace_sha256": trace.trace_sha256(),
        "steps": trace.steps,
    }


def replay(seed: int, steps: int = 24) -> dict[str, Any]:
    """Reproduce the identical verdict from the recorded seed alone."""
    trace = seeded_trace(int(seed), steps)
    return {"seed_recorded": int(seed), "entropy_was_fresh": False, "trace_sha256": trace.trace_sha256(), "steps": trace.steps}
