#!/usr/bin/env python3
"""Scratch-tree builders for ADV-0131 detector controls."""
from __future__ import annotations

from pathlib import Path

SEED_SUBJECT = "seeded-widget-count"
SEED_MISSING = "scratch-missing-ADV-0131.json"
FP_SUBJECT = "fp-delivered-count"

COLLISION_LINE = (
    "The 31-way M-NN option-id collision is a live blocker. "
    "Queued as P2-09. Family M and architecture candidates still share the prefix."
)

ARCH_BODY = """# 13-ARCHITECTURE-CANDIDATES (control reconstruction, POST-FIX)

Re-prefixed to MECH-NN. This file must carry zero bare M-NN declaration headings.

## MECH-1 mechanism-card

Mechanism body MECH-1.

## MECH-16 mechanism-card

Mechanism body MECH-16.

## MECH-31 mechanism-card

Mechanism body MECH-31.
"""


def write_decision_log(path: Path, line: int = 175) -> None:
    lines = ["# 17-DECISION-LOG (control reconstruction)"]
    for i in range(2, line):
        lines.append(f"# pad-{i:04d}")
    lines.append(COLLISION_LINE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_architecture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ARCH_BODY, encoding="utf-8")


def write_seeded(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    numeric_a = root / "numeric-a.md"
    numeric_b = root / "numeric-b.md"
    exists_listed = root / "exists-listed.md"
    exists_absent = root / "exists-absent.md"
    numeric_a.write_text(
        "ADV-0131-NUMERIC subject=seeded-widget-count metric=count value=12 denom=active-units\n"
        "The seeded-widget-count count is 12 of active-units.\n",
        encoding="utf-8",
    )
    numeric_b.write_text(
        "ADV-0131-NUMERIC subject=seeded-widget-count metric=count value=7 denom=active-units\n"
        "The seeded-widget-count count is 7 of active-units.\n",
        encoding="utf-8",
    )
    exists_listed.write_text(
        "ADV-0131-EXISTS path=scratch-missing-ADV-0131.json present=true\n"
        "Manifest lists scratch-missing-ADV-0131.json as held.\n",
        encoding="utf-8",
    )
    exists_absent.write_text(
        "ADV-0131-EXISTS path=scratch-missing-ADV-0131.json present=false\n"
        "Filesystem does not hold scratch-missing-ADV-0131.json.\n",
        encoding="utf-8",
    )
    missing = root / SEED_MISSING
    if missing.exists():
        missing.unlink()
    return {
        "numeric_a": numeric_a,
        "numeric_b": numeric_b,
        "exists_listed": exists_listed,
        "exists_absent": exists_absent,
        "missing": missing,
    }


def write_false_positive(root: Path) -> dict[str, Path]:
    """Same metric, different numbers, each stating a different denominator."""
    root.mkdir(parents=True, exist_ok=True)
    a = root / "fp-ready.md"
    b = root / "fp-all.md"
    a.write_text(
        "ADV-0131-NUMERIC subject=fp-delivered-count metric=count value=42 denom=ready-units\n"
        "The fp-delivered-count count is 42 of ready-units.\n",
        encoding="utf-8",
    )
    b.write_text(
        "ADV-0131-NUMERIC subject=fp-delivered-count metric=count value=4 denom=all-units\n"
        "The fp-delivered-count count is 4 of all-units.\n",
        encoding="utf-8",
    )
    return {"fp_a": a, "fp_b": b}


def write_known_live(root: Path) -> dict[str, Path]:
    log = root / "17-DECISION-LOG.md"
    arch = root / "13-ARCHITECTURE-CANDIDATES.md"
    write_decision_log(log)
    write_architecture(arch)
    return {"decision_log": log, "architecture": arch}
