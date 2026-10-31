"""Apply the published GEM rubric to a feature card.

The scorer never reads call_sheet_grade or any other label field. Two
implementations (apply / apply_independent) evaluate the same four gates
in opposite order so a partitioned reviewer is not a same-path re-run.
"""
from __future__ import annotations

from typing import Any

from rubric import RUBRIC

FEATURE_KEYS = tuple(RUBRIC["feature_keys"])
FORBIDDEN = frozenset(RUBRIC["forbidden_scorer_keys"])
PASSING_BUS = frozenset({"RIDES-BUS", "RIDES-BUS+STATE"})
PASSING_EVIDENCE = frozenset({"E1", "E2"})


def features_only(row: dict[str, Any]) -> dict[str, Any]:
    src = row.get("features") if isinstance(row.get("features"), dict) else row
    out = {k: src[k] for k in FEATURE_KEYS if k in src}
    return out


def gate_L(feat: dict[str, Any]) -> tuple[bool, str]:
    try:
        lev = int(feat["leverage"])
        cost = int(feat["integration_cost"])
    except (KeyError, TypeError, ValueError):
        return False, "L-missing"
    ok = lev >= 2 and cost <= 1
    return ok, f"L leverage={lev} cost={cost} pass={ok}"


def gate_I(feat: dict[str, Any]) -> tuple[bool, str]:
    irr = feat.get("irreplaceable") is True
    rename = feat.get("rename_of_existing") is True
    ok = irr and not rename
    return ok, f"I irreplaceable={irr} rename={rename} pass={ok}"


def gate_E(feat: dict[str, Any]) -> tuple[bool, str]:
    tier = str(feat.get("evidence_tier") or "")
    baseline = feat.get("has_baseline") is True
    effect = feat.get("has_effect_size") is True
    ok = tier in PASSING_EVIDENCE and baseline and effect
    return ok, f"E tier={tier} baseline={baseline} effect={effect} pass={ok}"


def gate_B(feat: dict[str, Any]) -> tuple[bool, str]:
    bus = str(feat.get("bus_fit") or "")
    ok = bus in PASSING_BUS
    return ok, f"B bus_fit={bus} pass={ok}"


def _assemble(feat: dict[str, Any], order: list[str]) -> dict[str, Any]:
    fns = {"L": gate_L, "I": gate_I, "E": gate_E, "B": gate_B}
    gates: dict[str, Any] = {}
    reasons: list[str] = []
    all_ok = True
    for name in order:
        ok, why = fns[name](feat)
        gates[name] = ok
        reasons.append(why)
        if not ok:
            all_ok = False
    leaked = sorted(k for k in feat if k in FORBIDDEN)
    return {
        "features_used": {k: feat.get(k) for k in FEATURE_KEYS},
        "forbidden_keys_seen_in_features": leaked,
        "gates": gates,
        "reasons": reasons,
        "gem": all_ok and not leaked,
        "gate_order": list(order),
    }


def apply(row: dict[str, Any]) -> dict[str, Any]:
    """Author scorer: L, I, E, B."""
    return _assemble(features_only(row), ["L", "I", "E", "B"])


def apply_independent(row: dict[str, Any]) -> dict[str, Any]:
    """Independent scorer: B, E, I, L. Same conjunction, different walk."""
    return _assemble(features_only(row), ["B", "E", "I", "L"])


def gem(row: dict[str, Any]) -> bool:
    return bool(apply(row)["gem"])


def expected_call_sheet_gem(grade: str) -> bool:
    return str(grade).upper() in {"TIER-1", "T1", "GEM", "ADOPT"}
