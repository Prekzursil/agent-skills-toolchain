"""Confirm none of the four schedulers are installed or launched."""
from __future__ import annotations

import importlib.util
import shutil

PACKAGES = (
    "airflow",
    "prefect",
    "dagster",
    "temporalio",
    "temporal",
)
BINARIES = (
    "airflow",
    "prefect",
    "dagster",
    "temporal",
)


def census() -> dict:
    imported = []
    for name in PACKAGES:
        spec = importlib.util.find_spec(name)
        if spec is not None:
            imported.append(name)
    found_bins = [b for b in BINARIES if shutil.which(b)]
    return {
        "binaries_on_path": found_bins,
        "clean": not imported and not found_bins,
        "importable": imported,
    }
