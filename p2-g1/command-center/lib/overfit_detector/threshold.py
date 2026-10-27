"""Versioned, frozen overfit gap threshold. Per-run overrides are refused."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "threshold_v1.json"


class PerRunThresholdTuneError(Exception):
    pass


def load_threshold(threshold_override: float | None = None) -> dict[str, Any]:
    if threshold_override is not None:
        raise PerRunThresholdTuneError("per-run threshold override is refused")
    raw = SPEC_PATH.read_bytes().replace(b"\r\n", b"\n")
    spec = json.loads(raw.decode("utf-8"))
    spec["spec_sha256"] = hashlib.sha256(raw).hexdigest()
    spec["frozen"] = True
    return spec
