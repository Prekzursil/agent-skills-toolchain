#!/usr/bin/env python3
"""Named probe 1: the gate emits all three outcomes; underpowered is not KEEP.

Both-states: a mutant that treats a positive mean as KEEP (or that remaps
INSUFFICIENT-EVIDENCE to KEEP) accepts the underpowered run. The live gate
must not.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.gate import decide  # noqa: E402
from bench.margin import PostHocMarginOverrideError, load_margin_table  # noqa: E402
from bench.paired import paired_from_cases  # noqa: E402
from bench.scenarios import (  # noqa: E402
    improvement_cases,
    noop_cases,
    secondary_regression_cases,
    underpowered_cases,
)

UNIT = "TST-0311"
GATE_PY = REPO / "tools" / "bench" / "gate.py"
RAW = HERE / "probe1-three-outcomes.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0311-probe1 {msg}")
    return 1


def mutant_positive_mean_is_keep(
    paired: Mapping[str, Any], _margins: Mapping[str, Any]
) -> dict[str, Any]:
    """Omitted third outcome: any positive point estimate becomes KEEP."""
    interval = paired.get("interval") if isinstance(paired.get("interval"), dict) else {}
    mean = float(interval.get("mean") or paired.get("point_estimate") or 0.0)
    return {
        "outcome": "KEEP" if mean > 0.0 else "REVERT",
        "cited_interval": None,
        "reason_id": "mutant-positive-mean",
        "n": paired.get("n"),
    }


def mutant_drop_insufficient(
    paired: Mapping[str, Any], margins: Mapping[str, Any]
) -> dict[str, Any]:
    """The failure this unit exists to close: map INSUFFICIENT-EVIDENCE to KEEP."""
    decision = dict(decide(paired, margins))
    if decision.get("outcome") == "INSUFFICIENT-EVIDENCE":
        decision["outcome"] = "KEEP"
        decision["reason_id"] = "mutant-omitted-third-outcome"
    return decision


def ast_has_three_outcomes(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value in {
            "KEEP",
            "REVERT",
            "INSUFFICIENT-EVIDENCE",
        }:
            found.add(str(node.value))
    return found == {"KEEP", "REVERT", "INSUFFICIENT-EVIDENCE"}


def main() -> int:
    if not ast_has_three_outcomes(GATE_PY):
        return fail("gate.py AST does not contain all three outcome literals")

    margins = load_margin_table()
    refused = False
    try:
        load_margin_table(override=0.01)
    except PostHocMarginOverrideError:
        refused = True
    if not refused:
        return fail("post-hoc margin override was not refused")

    noop = decide(
        paired_from_cases(noop_cases(24), change_id="chg-noop"),
        margins,
    )
    under = decide(
        paired_from_cases(underpowered_cases(4), change_id="chg-under"),
        margins,
    )
    keep = decide(
        paired_from_cases(improvement_cases(24), change_id="chg-keep"),
        margins,
    )
    regress = decide(
        paired_from_cases(secondary_regression_cases(24), change_id="chg-regress"),
        margins,
    )

    if noop.get("outcome") != "REVERT":
        return fail(f"noop expected REVERT, got {noop.get('outcome')} {noop.get('reason_id')}")
    if noop.get("reason_id") != "neutral-or-unproven":
        return fail(f"noop reason_id {noop.get('reason_id')}")
    if int(noop.get("n") or 0) < int(margins["primary"]["pre_registered_n"]):
        return fail("noop was not powered")

    if under.get("outcome") != "INSUFFICIENT-EVIDENCE":
        return fail(
            f"underpowered expected INSUFFICIENT-EVIDENCE, got "
            f"{under.get('outcome')} {under.get('reason_id')}"
        )
    if under.get("reason_id") != "underpowered":
        return fail(f"underpowered reason_id {under.get('reason_id')}")
    if under.get("outcome") == "KEEP":
        return fail("underpowered run was KEEP")

    if keep.get("outcome") != "KEEP":
        return fail(f"improvement expected KEEP, got {keep.get('outcome')} {keep.get('reason_id')}")
    cited = str(keep.get("cited_interval") or "")
    if "lo=" not in cited or "hi=" not in cited or "n=24" not in cited:
        return fail(f"KEEP did not cite interval: {cited!r}")
    if float((keep.get("interval") or {}).get("lo") or 0) < float(margins["primary"]["min_effect"]):
        return fail("KEEP interval.lo below min_effect")

    if regress.get("outcome") != "REVERT":
        return fail(
            f"secondary regression expected REVERT, got "
            f"{regress.get('outcome')} {regress.get('reason_id')}"
        )
    if regress.get("reason_id") != "material-regression":
        return fail(f"secondary regression reason_id {regress.get('reason_id')}")

    under_paired = paired_from_cases(underpowered_cases(4), change_id="chg-under-mut")
    m1 = mutant_positive_mean_is_keep(under_paired, margins)
    m2 = mutant_drop_insufficient(under_paired, margins)
    if m1.get("outcome") != "KEEP":
        return fail("positive-mean mutant did not KEEP the underpowered run")
    if m2.get("outcome") != "KEEP":
        return fail("drop-insufficient mutant did not KEEP the underpowered run")
    live_under = decide(under_paired, margins)
    if live_under.get("outcome") != "INSUFFICIENT-EVIDENCE":
        return fail("live gate KEPT the underpowered run the mutants KEEP")

    bare = dict(under_paired)
    bare.pop("interval", None)
    bare["n"] = 24
    bare_d = decide(bare, margins)
    if bare_d.get("outcome") != "INSUFFICIENT-EVIDENCE":
        return fail("bare point estimate was not INSUFFICIENT-EVIDENCE")

    payload = {
        "pass": True,
        "probe": "probe1-three-outcomes",
        "unit_id": UNIT,
        "outcomes": {
            "KEEP": True,
            "REVERT": True,
            "INSUFFICIENT-EVIDENCE": True,
        },
        "noop": {"outcome": noop["outcome"], "reason_id": noop["reason_id"], "n": noop["n"]},
        "underpowered": {
            "outcome": under["outcome"],
            "reason_id": under["reason_id"],
            "n": under["n"],
        },
        "improvement": {
            "outcome": keep["outcome"],
            "reason_id": keep["reason_id"],
            "cited_interval": keep["cited_interval"],
            "interval": keep["interval"],
        },
        "secondary_regression": {
            "outcome": regress["outcome"],
            "reason_id": regress["reason_id"],
        },
        "mutant_positive_mean_keeps_underpowered": m1["outcome"] == "KEEP",
        "mutant_drop_insufficient_keeps_underpowered": m2["outcome"] == "KEEP",
        "live_underpowered_not_keep": live_under["outcome"] == "INSUFFICIENT-EVIDENCE",
        "bare_point_estimate": bare_d["outcome"],
        "post_hoc_override_refused": True,
        "ast_three_outcomes": True,
        "margin_table_id": margins.get("id"),
        "margin_table_sha256": margins.get("spec_sha256"),
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        f"noop={noop['outcome']} under={under['outcome']} "
        f"keep={keep['outcome']} regress={regress['outcome']} "
        f"mutants_keep_under=True live_not_keep=True"
    )
    print("SUCCESS:TST-0311-probe1 three outcomes; underpowered is INSUFFICIENT-EVIDENCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
