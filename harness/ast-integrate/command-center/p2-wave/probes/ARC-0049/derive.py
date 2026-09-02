"""Derive least-privilege required grants from two independent signals."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from perm import covered_by_set  # noqa: E402

import observe as O  # noqa: E402

SAMPLE_IDS = (
    "ARC-0094",
    "CNL-0051",
    "IMP-0087",
    "TST-0066",
    "ADV-0026",
    "ADV-0053",
    "ADV-0035",
    "ARC-0085",
    "CNF-0048",
    "ARC-0058",
)

ROLLBACK_CAPABILITY = "ARC-0094"
DROP_CANDIDATE = "PowerShell"
EARLY_TIGHTEN_PERM = "Bash"


def _count(src: dict[str, int] | Counter[str], perm: str) -> int:
    return int(src.get(perm) or 0)


def _covered(perm: str, grant: list[str]) -> bool:
    try:
        return covered_by_set(perm, grant)
    except ValueError:
        return perm in grant


def derive_one(
    uid: str,
    declared: list[str],
    signal1: dict[str, int],
    signal2: dict[str, int],
) -> dict[str, Any]:
    events = sum(int(v) for v in signal1.values())
    coverage_ok = events >= O.COVERAGE_THRESHOLD
    required: list[str] = []
    drops: list[str] = []
    inferred_keep: list[str] = []
    disagreements: list[dict[str, Any]] = []
    evidence: dict[str, str] = {}
    underdeclared: list[str] = []

    for perm in declared:
        c1 = _count(signal1, perm)
        c2 = _count(signal2, perm)
        used = c1 > 0 or c2 > 0
        if (c1 > 0) != (c2 > 0) and perm in {"PowerShell", "Bash"}:
            disagreements.append(
                {"permission": perm, "signal1": c1, "signal2": c2}
            )
        if used:
            if perm not in required:
                required.append(perm)
            evidence[perm] = "OBSERVED"
        elif not coverage_ok:
            inferred_keep.append(perm)
            evidence[perm] = "INFERRED"
            if perm not in required:
                required.append(perm)
        else:
            drops.append(perm)
            evidence[perm] = "OBSERVED-ABSENT"

    for perm in sorted(signal1.keys()):
        if perm not in declared and _count(signal1, perm) > 0:
            underdeclared.append(perm)
            if perm not in required:
                required.append(perm)
            evidence[perm] = "OBSERVED"

    if drops and coverage_ok:
        decision = "TIGHTEN-BEHIND-SHADOW"
    elif inferred_keep:
        decision = "INFERRED-KEEP"
    else:
        decision = "KEEP"

    return {
        "capability_id": uid,
        "declared": list(declared),
        "observed_signal1": {k: int(v) for k, v in sorted(signal1.items())},
        "observed_signal2": {k: int(v) for k, v in sorted(signal2.items())},
        "derived_required": required,
        "candidate_drops": drops,
        "inferred_keep": inferred_keep,
        "underdeclared_additions": underdeclared,
        "signal_disagreement": disagreements,
        "evidence_class": evidence,
        "decision": decision,
        "coverage_ok": coverage_ok,
        "transcript_events": events,
        "proposed_grant": [p for p in declared if p not in drops] + [
            p for p in underdeclared if p not in declared
        ],
    }


def derive_sample(scan: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    scan = scan or O.scan_transcripts()
    units = O.load_catalog_units()
    by_unit = scan.get("by_unit") or {}
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for uid in SAMPLE_IDS:
        unit = units.get(uid)
        if unit is None:
            missing.append(f"{uid}:catalog")
            continue
        declared = O.declared_permissions(unit)
        if not declared:
            missing.append(f"{uid}:no-declared")
            continue
        s1 = by_unit.get(uid) or {}
        s2 = dict(O.probe_command_counts(uid))
        rows.append(derive_one(uid, declared, s1, s2))
    if missing or len(rows) != 10:
        raise RuntimeError(f"sample incomplete missing={missing} n={len(rows)}")
    return rows


def mapped_observed(row: dict[str, Any]) -> list[str]:
    """Replay list: observed counts already mapped into declared vocabulary.

    Signal 1 is transcript tool_use.name. Signal 2 is named-probe command
    tokens (python3 -> Bash, pwsh -> PowerShell). Both are live logs.
    """
    calls: list[str] = []
    declared = set(row["declared"])
    for src in (row.get("observed_signal1") or {}, row.get("observed_signal2") or {}):
        for perm, n in sorted(src.items()):
            if perm in declared:
                calls.extend([perm] * int(n))
    return calls
