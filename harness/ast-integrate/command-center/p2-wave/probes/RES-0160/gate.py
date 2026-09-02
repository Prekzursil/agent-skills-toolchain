#!/usr/bin/env python3
"""Adopt / park / reject decision record and back-test evaluator.

A gem may be ADOPTed only when all three bindings are present AND the named
before/after metric improved. Neutral or harmful metrics REJECT (catalog
anchor: revert when neutral or harmful). Adoptions with no metric are
WOULD-NOT-HAVE-PASSED. Missing revert trigger or owner-visible cost parks a
prospective record and WOULD-NOT-HAVE-PASSED a historical one.
"""
from __future__ import annotations

from typing import Any

DECISIONS = ("ADOPT", "PARK", "REJECT")
BACKTEST = ("WOULD-HAVE-PASSED", "WOULD-NOT-HAVE-PASSED")
BINDINGS = ("named_metric", "revert_trigger", "owner_visible_cost")

RECORD_KIND = "adopt-park-reject"
NO_METRIC_RULE = "WOULD-NOT-HAVE-PASSED"
NEUTRAL_OR_HARMFUL_RULE = "REJECT / WOULD-NOT-HAVE-PASSED"


def decision_record_spec() -> dict[str, Any]:
    return {
        "kind": RECORD_KIND,
        "required_bindings": list(BINDINGS),
        "decisions": list(DECISIONS),
        "backtest_verdicts": list(BACKTEST),
        "adopt_requires": (
            "named before/after metric showing improvement in the declared "
            "direction, a named revert trigger, and an owner-visible cost line"
        ),
        "no_metric_rule": NO_METRIC_RULE,
        "neutral_or_harmful_rule": NEUTRAL_OR_HARMFUL_RULE,
        "fields": {
            "mechanism_id": "stable id for the adopted locus",
            "named_metric": {
                "id": "metric id",
                "before": "measured value before adoption",
                "after": "measured value after adoption",
                "direction": (
                    "increase | decrease | false_to_true | true_to_false | "
                    "unequal-improvement"
                ),
            },
            "revert_trigger": {
                "predicate": "falsifiable condition that undoes the adoption"
            },
            "owner_visible_cost": {
                "amount": "numeric",
                "unit": "what the amount counts",
                "owner_visible": True,
            },
        },
    }


def _present_metric(metric: Any) -> bool:
    if not isinstance(metric, dict):
        return False
    if not str(metric.get("id") or "").strip():
        return False
    if "before" not in metric or "after" not in metric:
        return False
    return True


def _present_revert(trigger: Any) -> bool:
    if not isinstance(trigger, dict):
        return False
    return bool(str(trigger.get("predicate") or "").strip())


def _present_cost(cost: Any) -> bool:
    if not isinstance(cost, dict):
        return False
    if cost.get("owner_visible") is not True:
        return False
    unit = str(cost.get("unit") or "").strip()
    if not unit:
        return False
    amount = cost.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return False
    return True


def metric_improved(metric: dict[str, Any]) -> bool | None:
    """True=improved, False=neutral or harmful, None=unscorable."""
    if not _present_metric(metric):
        return None
    before, after = metric.get("before"), metric.get("after")
    direction = str(metric.get("direction") or "").strip()
    if direction == "increase":
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            return None
        if after > before:
            return True
        return False
    if direction == "decrease":
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            return None
        if after < before:
            return True
        return False
    if direction == "false_to_true":
        if before is False and after is True:
            return True
        return False
    if direction == "true_to_false":
        if before is True and after is False:
            return True
        return False
    if before == after:
        return False
    return True


def evaluate_record(rec: dict[str, Any]) -> dict[str, Any]:
    """Score one adoption record. Does not mutate rec."""
    missing: list[str] = []
    metric = rec.get("named_metric")
    if not _present_metric(metric):
        missing.append("named_metric")
    if not _present_revert(rec.get("revert_trigger")):
        missing.append("revert_trigger")
    if not _present_cost(rec.get("owner_visible_cost")):
        missing.append("owner_visible_cost")

    improved = metric_improved(metric) if "named_metric" not in missing else None

    if "named_metric" in missing:
        decision = "REJECT"
        backtest = "WOULD-NOT-HAVE-PASSED"
        reason = "no-metric"
    elif improved is False:
        decision = "REJECT"
        backtest = "WOULD-NOT-HAVE-PASSED"
        reason = "neutral-or-harmful"
    elif missing:
        decision = "PARK"
        backtest = "WOULD-NOT-HAVE-PASSED"
        reason = "unbound:" + ",".join(missing)
    elif improved is None:
        decision = "PARK"
        backtest = "WOULD-NOT-HAVE-PASSED"
        reason = "metric-unscorable"
    else:
        decision = "ADOPT"
        backtest = "WOULD-HAVE-PASSED"
        reason = "bound-and-improved"

    return {
        "mechanism_id": rec.get("mechanism_id"),
        "decision": decision,
        "backtest_verdict": backtest,
        "reason": reason,
        "missing_bindings": missing,
        "metric_improved": improved,
        "still_in_use": bool(rec.get("still_in_use")),
    }


def evaluate_population(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [evaluate_record(r) for r in records]
    passed = [r for r in rows if r["backtest_verdict"] == "WOULD-HAVE-PASSED"]
    failed = [r for r in rows if r["backtest_verdict"] == "WOULD-NOT-HAVE-PASSED"]
    still_failed = [r for r in failed if r["still_in_use"]]
    return {
        "n": len(rows),
        "would_have_passed": len(passed),
        "would_not_have_passed": len(failed),
        "would_not_have_passed_still_in_use": len(still_failed),
        "negative_control_fired": len(still_failed) >= 1,
        "blesses_everything": len(rows) > 0 and len(failed) == 0,
        "rows": rows,
    }


def blessing_mutant(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Force every historical row to WOULD-HAVE-PASSED. A real gate must refuse this."""
    mutant = []
    for rec in records:
        clone = dict(rec)
        clone["named_metric"] = {
            "id": "forced-pass",
            "before": False,
            "after": True,
            "direction": "false_to_true",
        }
        clone["revert_trigger"] = {"predicate": "forced-pass revert"}
        clone["owner_visible_cost"] = {
            "amount": 1,
            "unit": "forced-pass",
            "owner_visible": True,
        }
        mutant.append(clone)
    return mutant


def complete_example() -> dict[str, Any]:
    """Synthetic record that MUST pass, proving the gate is not a brick wall."""
    return {
        "mechanism_id": "SYNTH-complete-bindings",
        "still_in_use": False,
        "named_metric": {
            "id": "rejects_keyed_garbage",
            "before": False,
            "after": True,
            "direction": "false_to_true",
        },
        "revert_trigger": {
            "predicate": (
                "schema_doc_verdict({'$schema': META, 'totally': 'unrelated'})[0] "
                "is True"
            )
        },
        "owner_visible_cost": {
            "amount": 3,
            "unit": "garbage-probes-per-schema-document",
            "owner_visible": True,
        },
    }
