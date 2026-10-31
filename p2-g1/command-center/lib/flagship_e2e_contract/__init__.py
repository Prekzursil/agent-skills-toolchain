"""Flagship e2e contract package."""
from __future__ import annotations

from .contract import MIN_BYTES, SPEC_FLAGSHIP_COUNT, evaluate_e2e, flagship_count_ok, independent_artifact_path
from .rail import run_mocked_only, run_real
from .registry import (
    REGISTRY_REL,
    all_ids,
    compute_flagship_count,
    flagship_ids,
    load_registry,
    plant_extra_flagship,
    plant_missing_flagship,
)

__all__ = [
    "MIN_BYTES",
    "REGISTRY_REL",
    "SPEC_FLAGSHIP_COUNT",
    "all_ids",
    "compute_flagship_count",
    "evaluate_e2e",
    "flagship_count_ok",
    "flagship_ids",
    "independent_artifact_path",
    "load_registry",
    "plant_extra_flagship",
    "plant_missing_flagship",
    "run_mocked_only",
    "run_real",
]
