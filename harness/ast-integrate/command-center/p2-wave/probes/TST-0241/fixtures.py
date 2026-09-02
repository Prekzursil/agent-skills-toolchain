"""Deterministic work-unit cohorts for TST-0241 scaling.

Empty lists are a valid *control* input and must not be timed.
"""
from __future__ import annotations

import hashlib
import json

UNIT = "TST-0241"
SEED = 241
SIZES = (16, 64, 256, 1024, 2048)
LANES = (
    "local-serialized",
    "local-parallel",
    "worktree-isolated",
    "cloud-batch",
)


def make_units(n: int, seed: int = SEED) -> list[dict]:
    if n < 0:
        raise ValueError("n must be >= 0")
    out: list[dict] = []
    for i in range(n):
        uid = f"u-{seed:04d}-{i:05d}"
        payload = f"cohort-{seed}-unit-{i}-pad={i * 17 + seed}"
        out.append({"id": uid, "seq": i, "payload": payload})
    return out


def input_fingerprint(units: list[dict]) -> str:
    blob = json.dumps(units, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
