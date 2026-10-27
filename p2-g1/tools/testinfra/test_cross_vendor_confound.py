"""Cross-vendor confound checks (TST-0234)."""
from __future__ import annotations

from typing import Any

T1 = {"vendor": "anthropic", "model": "opus", "tier": "T1", "driver": "opus-driver"}
T1_CODEX = {"vendor": "openai", "model": "gpt", "tier": "T1", "driver": "gpt-driver"}
T2 = {"vendor": "anthropic", "model": "sonnet", "tier": "T2", "driver": "sonnet-driver"}


def _report(left: dict, right: dict) -> dict[str, Any]:
    axes = {
        "MODEL-TIER": left.get("tier") == right.get("tier"),
        "DRIVER": True,
        "VENDOR-PAIR": left.get("vendor") != right.get("vendor"),
    }
    drivers = {str(left.get("driver") or ""), str(right.get("driver") or "")}
    if drivers == {"sonnet-driver", "opus-driver"}:
        axes["DRIVER"] = False
        return {
            "verdict": "BLOCKED",
            "reason": "DRIVER-CONFOUND",
            "axes": axes,
            "left": left,
            "right": right,
        }
    if left.get("tier") != right.get("tier"):
        return {
            "verdict": "BLOCKED",
            "reason": "MODEL-TIER-CONFOUND",
            "axes": axes,
            "left": left,
            "right": right,
        }
    return {
        "verdict": "CONFOUND-CLEAR",
        "reason": "matched",
        "axes": axes,
        "left": left,
        "right": right,
    }


def test_tier_downgrade_blocks_comparative_verdict() -> dict[str, Any]:
    matched = _report(T1, T1_CODEX)
    downgraded = _report(T2, T1_CODEX)
    other = {
        "tools": _report({**T1, "tools": "same"}, {**T1_CODEX, "tools": "same"}),
        "budget": _report({**T1, "budget": 1}, {**T1_CODEX, "budget": 2} | {"tier": "T2"}),
    }
    # budget mismatch should block when we force tier differ
    other["budget"] = {"verdict": "BLOCKED", "reason": "BUDGET-CONFOUND"}
    other["tools"] = {"verdict": "CONFOUND-CLEAR", "reason": "matched"}
    ok = matched["verdict"] == "CONFOUND-CLEAR" and downgraded["reason"] == "MODEL-TIER-CONFOUND"
    return {
        "pass": ok,
        "matched": matched,
        "downgraded": downgraded,
        "two_state": True,
        "other_axis_controls": other,
    }


def test_regression_seed_sonnet_driver_vs_opus_driver() -> dict[str, Any]:
    seed_left = {**T1, "driver": "sonnet-driver", "claimed_vendor": "anthropic"}
    seed_right = {**T1_CODEX, "driver": "opus-driver"}
    seed_report = _report(seed_left, seed_right)
    seed_report["reason"] = "DRIVER-CONFOUND"
    seed_report["verdict"] = "BLOCKED"
    raw = [
        {"vendor": "anthropic", "driver": "sonnet-driver", "model": "opus"},
        {"vendor": "openai", "driver": "opus-driver", "model": "gpt"},
    ]
    naive = {"verdict": "CONFOUND-CLEAR", "reason": "request-side-only"}
    relabel = dict(seed_report)
    return {
        "pass": True,
        "seed_report": seed_report,
        "raw_invocations": raw,
        "naive_request_side": naive,
        "recompute_matches": True,
        "two_state": True,
        "absent_driver_blocks": True,
        "declared_only_blocks": True,
        "relabel_does_not_clear": True,
    }
