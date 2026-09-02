"""Shared live measurement used by emit and named probes.

Evaluation order is collapsed-anchor, diverse-anchor, separation-gate,
then real-council. Real councils are never scored before the gate.
"""
from __future__ import annotations

from typing import Any

from classifier import attribute
from common import (
    BINOMIAL_ALPHA,
    CHANCE_ACCURACY,
    INVENTORY_RULE,
    MAX_COLLAPSED_DIVERGENCE,
    MIN_DIVERSE_DIVERGENCE,
    MIN_MARGIN,
    TARGET_ID,
)
from councils import (
    collapsed_anchor,
    diverse_anchor,
    diverse_unlabelled,
    prototypes_sha256,
    surface_varied_collapse,
)
from inventory import inventory as scan_inventory
from metrics import council_summary


def separation_gate(collapsed: dict[str, Any], diverse: dict[str, Any]) -> dict[str, Any]:
    c = float(collapsed["mean_combined_divergence"])
    d = float(diverse["mean_combined_divergence"])
    margin = d - c
    passed = (
        c <= MAX_COLLAPSED_DIVERGENCE
        and d >= MIN_DIVERSE_DIVERGENCE
        and margin >= MIN_MARGIN
    )
    return {
        "collapsed_mean_combined_divergence": c,
        "diverse_mean_combined_divergence": d,
        "anchor_margin": margin,
        "threshold": {
            "max_collapsed_divergence": MAX_COLLAPSED_DIVERGENCE,
            "min_diverse_divergence": MIN_DIVERSE_DIVERGENCE,
            "min_margin": MIN_MARGIN,
        },
        "passed": passed,
    }


def measure_probe1(*, clone_diverse_from_collapsed: bool = False) -> dict[str, Any]:
    collapsed_briefs = collapsed_anchor()
    diverse_briefs = collapsed_anchor() if clone_diverse_from_collapsed else diverse_anchor()
    collapsed = council_summary(collapsed_briefs, "collapsed-anchor")
    diverse = council_summary(diverse_briefs, "diverse-anchor")
    gate = separation_gate(collapsed, diverse)
    same_role = len({b["role"] for b in collapsed_briefs}) == 1
    diverse_roles = {b["role"] for b in diverse_anchor()}
    inv = scan_inventory()
    real_scored = False
    real_summary = None
    target_verdict = "NOT-CHECKED"
    target_reason = (
        "no eligible runtime-produced five-role first-round brief set; "
        "configuration text is not participant behaviour"
    )
    if gate["passed"] and inv["eligible"]:
        # Score only the first eligible set; remaining sets are listed.
        real_summary = council_summary(inv["eligible"][0]["briefs"], "real-council")
        real_scored = True
        real_mean = float(real_summary["mean_combined_divergence"])
        # Pathology CONFIRMED when a live five-role set sits with the collapsed
        # anchor; REFUTED when it sits with the diverse anchor.
        if real_mean <= MAX_COLLAPSED_DIVERGENCE:
            target_verdict = "CONFIRMED"
            target_reason = (
                "eligible real council mean combined divergence sits with the "
                "collapsed anchor; distinct labels without distinct behaviour"
            )
        elif real_mean >= MIN_DIVERSE_DIVERGENCE:
            target_verdict = "REFUTED"
            target_reason = (
                "eligible real council mean combined divergence sits with the "
                "diverse anchor on Probe 1; Probe 2 must still recover roles"
            )
        else:
            target_verdict = "PARTIAL"
            target_reason = (
                "eligible real council sits between anchors; neither collapse "
                "nor full differentiation is established by Probe 1 alone"
            )
    elif not gate["passed"]:
        target_verdict = "NOT-CHECKED"
        target_reason = "anchor separation gate red; real council not scored"
    return {
        "mechanism": (
            "token-set Jaccard distance plus independently recorded stance distance"
        ),
        "evaluation_order": "collapsed-anchor>diverse-anchor>separation-gate>real-council",
        "combined_statistic": "mean(pairwise((lexical_divergence+stance_divergence)/2))",
        "collapsed": collapsed,
        "diverse": diverse,
        "gate": gate,
        "check": {
            "all_collapsed_participants_given_same_role": same_role,
            "diverse_roles_exact": diverse_roles == set(
                ("advocate", "skeptic", "domain_expert", "user_proxy", "judge")
            ),
            "anchor_separation_passed": gate["passed"],
        },
        "inventory": inv,
        "real_council_scored": real_scored,
        "real_council": real_summary,
        "target_id": TARGET_ID,
        "target_verdict": target_verdict,
        "target_reason": target_reason,
        "clone_diverse_from_collapsed": clone_diverse_from_collapsed,
        "inventory_rule": INVENTORY_RULE,
    }


def measure_probe2() -> dict[str, Any]:
    diverse = attribute("diverse-anchor", diverse_unlabelled())
    collapsed = attribute("surface-varied-role-collapse", surface_varied_collapse())
    recovered = (
        diverse["accuracy"] > CHANCE_ACCURACY
        and diverse["binomial_tail_p"] <= BINOMIAL_ALPHA
        and diverse["correct"] >= 4
    )
    unrecoverable = (
        collapsed["accuracy"] <= CHANCE_ACCURACY + 1e-12
        or collapsed["binomial_tail_p"] > BINOMIAL_ALPHA
    )
    inv = scan_inventory()
    real_scored = False
    real_attr = None
    target_verdict = "NOT-CHECKED"
    target_reason = (
        "no eligible runtime-produced five-role first-round brief set; "
        "classifier calibration is not a substitute"
    )
    if recovered and unrecoverable and inv["eligible"]:
        real_attr = attribute("real-council", inv["eligible"][0]["briefs"])
        real_scored = True
        if real_attr["binomial_tail_p"] <= BINOMIAL_ALPHA and real_attr["accuracy"] > CHANCE_ACCURACY:
            target_verdict = "REFUTED"
            target_reason = (
                "assigned roles recovered above chance from unlabelled real briefs"
            )
        else:
            target_verdict = "CONFIRMED"
            target_reason = (
                "assigned roles were not recoverable above chance on real briefs; "
                "surface wording differences do not refute role collapse"
            )
    return {
        "mechanism": (
            "frozen role-mandate prototype classifier; no Probe 1 statistic "
            "or readout is consumed"
        ),
        "classifier_input": "brief text only; role labels are revealed after each prediction",
        "classifier_fixture": "command-center/p2-wave/probes/ADV-0092/fixtures.json",
        "classifier_prototypes_sha256": prototypes_sha256(),
        "chance_accuracy": CHANCE_ACCURACY,
        "diverse": diverse,
        "surface_varied_collapse": collapsed,
        "check": {
            "diverse_roles_recovered_above_chance": recovered,
            "diverse_recovery_binomial_p_lte_0_05": diverse["binomial_tail_p"] <= BINOMIAL_ALPHA,
            "surface_varied_collapse_unrecoverable": unrecoverable,
        },
        "inventory": {
            "eligible_real_council_count": inv["eligible_real_council_count"],
            "documents_with_participant_briefs_key": inv[
                "documents_with_participant_briefs_key"
            ],
        },
        "real_council_scored": real_scored,
        "real_council": real_attr,
        "target_id": TARGET_ID,
        "target_verdict": target_verdict,
        "target_reason": target_reason,
    }


def combine_target(p1: dict[str, Any], p2: dict[str, Any]) -> dict[str, Any]:
    """One verdict. Missing real-council evidence stays NOT-CHECKED."""
    v1, v2 = p1["target_verdict"], p2["target_verdict"]
    if "BLOCKED" in (v1, v2):
        verdict = "BLOCKED"
        reason = "a named probe blocked scoring"
    elif v1 == "NOT-CHECKED" and v2 == "NOT-CHECKED":
        verdict = "NOT-CHECKED"
        reason = p1["target_reason"]
    elif v1 == "CONFIRMED" or v2 == "CONFIRMED":
        if v1 == "REFUTED" or v2 == "REFUTED":
            verdict = "PARTIAL"
            reason = "Probe 1 and Probe 2 disagree on the real council"
        else:
            verdict = "CONFIRMED"
            reason = p1["target_reason"] if v1 == "CONFIRMED" else p2["target_reason"]
    elif v1 == "REFUTED" and v2 == "REFUTED":
        verdict = "REFUTED"
        reason = "both probes place the real council with the diverse control"
    else:
        verdict = "PARTIAL"
        reason = f"probe1={v1}; probe2={v2}"
    return {
        "id": TARGET_ID,
        "verdict": verdict,
        "reason": reason,
        "probe1_verdict": v1,
        "probe2_verdict": v2,
    }
