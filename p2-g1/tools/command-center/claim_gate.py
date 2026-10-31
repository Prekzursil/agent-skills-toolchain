"""Claim lineage gate: CONFIRMED/REFUTED require a source_probe (ADV-0113).

Independence is a property of a (source, verifier) pair. An absent source
cannot be compared against a verifier. The pre-fix hole only enforced
missing-verifier.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

RULE_NO_SOURCE = "no-source-probe"
RULE_NO_VERIFIER = "no-verifier-probe"
PROBE_FIELDS = ("tool", "engine", "shell", "field", "path", "instrument", "fingerprint", "sha256")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]  # tools/command-center -> repo
FIXTURES = REPO / "command-center" / "p2-wave" / "probes" / "ADV-0113" / "fixtures"


def probe_present(obj: dict[str, Any] | None, key: str) -> bool:
    if not isinstance(obj, dict):
        return False
    probe = obj.get(key)
    if probe is None:
        return False
    if isinstance(probe, str):
        return bool(probe.strip())
    if isinstance(probe, dict):
        for field in PROBE_FIELDS:
            val = probe.get(field)
            if isinstance(val, str) and val.strip():
                return True
    return False


def check_claim(claim: dict[str, Any]) -> dict[str, Any]:
    source_present = probe_present(claim, "source_probe")
    verifier_present = probe_present(claim, "verifier_probe")
    rules: list[str] = []
    violations: list[dict[str, str]] = []
    if not source_present:
        rules.append(RULE_NO_SOURCE)
        violations.append(
            {
                "rule": RULE_NO_SOURCE,
                "detail": (
                    "CONFIRMED needs a source_probe declaring at least one of "
                    "tool, engine, shell, field: independence is a property of a pair, "
                    "and an absent source cannot be compared against anything"
                ),
            }
        )
    if not verifier_present:
        rules.append(RULE_NO_VERIFIER)
        violations.append(
            {
                "rule": RULE_NO_VERIFIER,
                "detail": "CONFIRMED needs a verifier_probe mechanically different from the source",
            }
        )
    return {
        "id": claim.get("id"),
        "ok": not rules,
        "rules_fired": rules,
        "source_present": source_present,
        "verdict": claim.get("verdict"),
        "verifier_present": verifier_present,
        "violations": violations,
    }


def check_claim_pre_fix_hole(claim: dict[str, Any]) -> dict[str, Any]:
    """Pre-fix suite: missing verifier is caught; missing source is not."""
    verifier_present = probe_present(claim, "verifier_probe")
    rules: list[str] = []
    violations: list[dict[str, str]] = []
    if not verifier_present:
        rules.append(RULE_NO_VERIFIER)
        violations.append(
            {
                "rule": RULE_NO_VERIFIER,
                "detail": "missing verifier (pre-fix suite covered this arm)",
            }
        )
    return {
        "id": claim.get("id"),
        "mode": "pre-fix-hole",
        "ok": not rules,
        "rules_fired": rules,
        "violations": violations,
    }


def _load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES / name
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def absent_source_regression() -> dict[str, Any]:
    absent = _load_fixture("absent_source_valid_verifier.json")
    empty = dict(absent)
    empty["id"] = "ADV-0113-C-EMPTY-SOURCE"
    empty["source_probe"] = {}
    complete = _load_fixture("complete_claim.json")
    missing_v = _load_fixture("absent_verifier.json")
    cases = [
        {"id": "absent-source-valid-verifier", "live": check_claim(absent)},
        {"id": "empty-source-valid-verifier", "live": check_claim(empty)},
        {"id": "complete-claim-admitted", "live": check_claim(complete)},
        {"id": "absent-verifier-is-different-rule", "live": check_claim(missing_v)},
        {"id": "pre-fix-hole-accepts-absent-source", "live": check_claim_pre_fix_hole(absent)},
        {
            "id": "pre-fix-suite-catches-absent-verifier-only",
            "live": check_claim_pre_fix_hole(missing_v),
        },
    ]
    want_ok = {
        "absent-source-valid-verifier": False,
        "empty-source-valid-verifier": False,
        "complete-claim-admitted": True,
        "absent-verifier-is-different-rule": False,
        "pre-fix-hole-accepts-absent-source": True,
        "pre-fix-suite-catches-absent-verifier-only": False,
    }
    for case in cases:
        case["ok"] = case["live"]["ok"] is want_ok[case["id"]]
        if case["id"] == "absent-source-valid-verifier":
            case["ok"] = case["ok"] and RULE_NO_SOURCE in case["live"]["rules_fired"]
        if case["id"] == "absent-verifier-is-different-rule":
            case["ok"] = (
                case["ok"]
                and RULE_NO_VERIFIER in case["live"]["rules_fired"]
                and RULE_NO_SOURCE not in case["live"]["rules_fired"]
            )
    return {
        "cases": cases,
        "note": (
            "ABSENT-SOURCE is the required direction. The pre-fix suite went 30/30 "
            "while the hole was live because its missing-probe case omitted the verifier, "
            "not the source."
        ),
        "pass": all(c["ok"] for c in cases),
    }


__all__ = [
    "RULE_NO_SOURCE",
    "RULE_NO_VERIFIER",
    "absent_source_regression",
    "check_claim",
    "check_claim_pre_fix_hole",
    "probe_present",
]
