#!/usr/bin/env python3
"""Paths and live-input honesty for TST-0349."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "TST-0349"
OUT_REL = "command-center/receipts/TST-0349.json"
DECLARED_SCHEMA = "command-center/schema/receipt.schema.json"
LIVE_REGISTRY_REL = "command-center/TEST-REGISTRY.json"
PLANTED_REGISTRY_REL = (
    "command-center/p2-wave/probes/TST-0349/fixtures/registry.json"
)
PLANTED_TESTS_REL = (
    "command-center/p2-wave/probes/TST-0349/fixtures/tests"
)
LIVE_TEST_ROOTS = [
    "tools/command-center/tests",
    "agent-self/harness/tests",
]


def repo_path(rel: str) -> Path:
    return REPO / rel.replace("\\", "/")


def live_registry_path() -> Path:
    return repo_path(LIVE_REGISTRY_REL)


def planted_registry_path() -> Path:
    return repo_path(PLANTED_REGISTRY_REL)


def planted_tests_dir() -> Path:
    return repo_path(PLANTED_TESTS_REL)


def live_test_dirs() -> list[Path]:
    return [repo_path(rel) for rel in LIVE_TEST_ROOTS]


def live_roots_present() -> dict[str, bool]:
    return {rel: repo_path(rel).is_dir() for rel in LIVE_TEST_ROOTS}


def run_unit_census() -> dict:
    import census as C

    return C.run_census(
        REPO,
        planted_registry_path(),
        planted_tests_dir(),
        live_registry_path(),
        live_test_dirs(),
    )


def receipt_payload(doc: dict) -> dict:
    """Domain census lives in report[] for receipt_core additionalProperties=false."""
    report = doc.get("report")
    if isinstance(report, dict) and report:
        return report
    return doc
