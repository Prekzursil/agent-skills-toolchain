#!/usr/bin/env python3
"""Shared live measurement for TST-0257 probes and the receipt emitter."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.simulate import measure_pair  # noqa: E402

SPEC = HERE / "fixtures" / "council-spec.json"
CAST = HERE / "fixtures" / "cast"
CORRUPT = HERE / "fixtures" / "cast-corrupt"
SEED_A = 257
SEED_B = 8257


def prepare_corrupt_cast() -> None:
    """Keep chair/proposer intact in the corrupt cast; only critic is gutted."""
    CORRUPT.mkdir(parents=True, exist_ok=True)
    for name in ("chair.json", "proposer.json"):
        shutil.copyfile(CAST / name, CORRUPT / name)


def live() -> dict:
    prepare_corrupt_cast()
    return measure_pair(SPEC, CAST, SEED_A, SEED_B, corrupt_dir=CORRUPT)
