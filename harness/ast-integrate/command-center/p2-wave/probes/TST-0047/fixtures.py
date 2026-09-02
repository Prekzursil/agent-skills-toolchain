#!/usr/bin/env python3
"""Fixture sources and deliberately non-conforming plants for TST-0047."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

from engine import FORMAT_FAMILY, good_registry  # noqa: E402

REAL_ARTIFACTS: tuple[tuple[str, str], ...] = (
    (
        "command-center/p2-wave/probes/ARC-0010/registry.json",
        "real-ARC-0010-registry.json",
    ),
    (
        "command-center/p2-wave/probes/ARC-0012/fixtures/complete/registry.json",
        "real-ARC-0012-registry.json",
    ),
    (
        "command-center/phase3/A2/DESIGN.json",
        "real-A2-DESIGN.json",
    ),
)

FIXTURE_ARTIFACTS: tuple[tuple[str, str], ...] = (
    (
        "command-center/p2-wave/probes/TST-0047/fixtures/artifacts/alpha.json",
        "fixture-alpha.json",
    ),
    (
        "command-center/p2-wave/probes/TST-0047/fixtures/artifacts/beta.json",
        "fixture-beta.json",
    ),
    (
        "command-center/p2-wave/probes/TST-0047/fixtures/artifacts/gamma.json",
        "fixture-gamma.json",
    ),
)

UNPARSEABLE = (
    "command-center/p2-wave/probes/TST-0047/fixtures/garbage.unparseable",
    "garbage.unparseable",
)

CONTRACT_RULES: tuple[str, ...] = (
    "coverage",
    "first-apply-progress",
    "idempotence",
    "quarantine-no-drop",
    "transformation-obligation",
)


@dataclass(frozen=True)
class Plant:
    id: str
    rule: str
    include_unparseable: bool
    registry: dict[str, Any]


def all_conforming_sources() -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    for rel, dest in (*FIXTURE_ARTIFACTS, *REAL_ARTIFACTS):
        rows.append((REPO / rel, dest))
    return rows


def _one_migration(reg: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    out = copy.deepcopy(reg)
    mig = copy.deepcopy(out["migrations"][0])
    mig.update(overrides)
    out["migrations"] = [mig, *out["migrations"][1:]]
    return out


def plants() -> list[Plant]:
    good = good_registry()
    missing = copy.deepcopy(good)
    missing["id"] = "missing-2-to-3"
    missing["migrations"] = [copy.deepcopy(good["migrations"][0])]

    mutate = _one_migration(good, apply_mode="always-mutate", id="1-to-2-always-mutate")
    mutate["id"] = "non-idempotent"

    noop = _one_migration(good, apply_mode="always-noop", id="1-to-2-always-noop")
    noop["id"] = "vacuous-noop"

    drop = copy.deepcopy(good)
    drop["id"] = "silent-drop"
    for mig in drop["migrations"]:
        mig["untransformable_policy"] = "DROP"

    incomplete = _one_migration(
        good,
        id="1-to-2-incomplete",
        done_when="schema_version",
        steps=[{"op": "set", "path": "schema_version", "value": 2}],
        postconditions={"schema_version": 2, "format_family": FORMAT_FAMILY},
    )
    incomplete["id"] = "incomplete-transform"

    return [
        Plant("missing-transition", "coverage", False, missing),
        Plant("non-idempotent-stamp", "idempotence", False, mutate),
        Plant("always-noop", "first-apply-progress", False, noop),
        Plant("silent-drop-unparseable", "quarantine-no-drop", True, drop),
        Plant("incomplete-transform", "transformation-obligation", False, incomplete),
    ]
