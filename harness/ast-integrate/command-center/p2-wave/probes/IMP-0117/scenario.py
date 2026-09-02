#!/usr/bin/env python3
"""Shared fixture + gate helpers for IMP-0117 probes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.fixture_prs import (  # noqa: E402
    PREEXISTING_BAD,
    PROPOSED_BAD,
    PROPOSED_CLEAN,
    build,
)
from tools.marketplace.registry_diff_gate import (  # noqa: E402
    load_index,
    run_gate,
    run_whole_index,
)

FIX = HERE / "fixtures"


def trees() -> dict[str, Path]:
    return build(FIX)


def gate(base: Path, head: Path) -> dict:
    return run_gate(
        base_index=load_index(base / "marketplace.json"),
        head_index=load_index(head / "marketplace.json"),
        head_index_path=head / "marketplace.json",
        head_blobs_dir=head / "blobs",
    )


def whole(head: Path) -> dict:
    return run_whole_index(
        load_index(head / "marketplace.json"),
        head / "marketplace.json",
        head / "blobs",
    )


def dump(report: dict) -> None:
    print(json.dumps(report, indent=2, sort_keys=True))
