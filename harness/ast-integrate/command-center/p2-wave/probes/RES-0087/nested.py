#!/usr/bin/env python3
"""Worked two-level nested-council example for RES-0087.

Maps Nurmi's referendum / compound-majority paradox onto COMPLETE/BLOCKED
verdicts. Label-only fan-in (majority of subcouncil labels) disagrees with
the flattened member majority. Per-subcouncil tallies are the minimal
forwarding set that restores the flattened conclusion and surfaces dissent.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

COMPLETE = "COMPLETE"
BLOCKED = "BLOCKED"
LABELS = (COMPLETE, BLOCKED)

# 3 subcouncils × 3 members. Flattened: 5 COMPLETE, 4 BLOCKED.
# Subcouncil labels: A COMPLETE, B BLOCKED, C BLOCKED → meta BLOCKED.
MEMBERS: tuple[dict[str, Any], ...] = (
    {
        "subcouncil": "A",
        "member_id": "A1",
        "verdict": COMPLETE,
        "confidence": 0.95,
        "evidence_ids": ("shared-spec", "unique-A-pass"),
        "dissent": False,
    },
    {
        "subcouncil": "A",
        "member_id": "A2",
        "verdict": COMPLETE,
        "confidence": 0.92,
        "evidence_ids": ("shared-spec",),
        "dissent": False,
    },
    {
        "subcouncil": "A",
        "member_id": "A3",
        "verdict": COMPLETE,
        "confidence": 0.90,
        "evidence_ids": ("shared-spec",),
        "dissent": False,
    },
    {
        "subcouncil": "B",
        "member_id": "B1",
        "verdict": COMPLETE,
        "confidence": 0.55,
        "evidence_ids": ("shared-spec", "unique-B-pass"),
        "dissent": True,
    },
    {
        "subcouncil": "B",
        "member_id": "B2",
        "verdict": BLOCKED,
        "confidence": 0.95,
        "evidence_ids": ("shared-spec",),
        "dissent": False,
    },
    {
        "subcouncil": "B",
        "member_id": "B3",
        "verdict": BLOCKED,
        "confidence": 0.93,
        "evidence_ids": ("shared-spec",),
        "dissent": False,
    },
    {
        "subcouncil": "C",
        "member_id": "C1",
        "verdict": COMPLETE,
        "confidence": 0.58,
        "evidence_ids": ("shared-spec", "unique-C-pass"),
        "dissent": True,
    },
    {
        "subcouncil": "C",
        "member_id": "C2",
        "verdict": BLOCKED,
        "confidence": 0.94,
        "evidence_ids": ("shared-spec",),
        "dissent": False,
    },
    {
        "subcouncil": "C",
        "member_id": "C3",
        "verdict": BLOCKED,
        "confidence": 0.91,
        "evidence_ids": ("shared-spec",),
        "dissent": False,
    },
)

# The only field required to prevent THIS completion reversal.
MINIMAL_FORWARDING_SET = ("per_subcouncil_verdict_counts",)


def majority(labels: list[str]) -> str:
    counts = Counter(labels)
    complete = counts[COMPLETE]
    blocked = counts[BLOCKED]
    if complete > blocked:
        return COMPLETE
    if blocked > complete:
        return BLOCKED
    return "TIE"


def flattened_member_majority(members: tuple[dict[str, Any], ...] = MEMBERS) -> dict[str, Any]:
    labels = [m["verdict"] for m in members]
    counts = Counter(labels)
    return {
        "rule": "flattened-member-majority",
        "n_complete": counts[COMPLETE],
        "n_blocked": counts[BLOCKED],
        "conclusion": majority(labels),
        "payload": {"member_verdicts": labels},
    }


def label_only_fanin(members: tuple[dict[str, Any], ...] = MEMBERS) -> dict[str, Any]:
    """What a meta-council sees if each child forwards only its majority label."""
    by_child: dict[str, list[str]] = {}
    for m in members:
        by_child.setdefault(m["subcouncil"], []).append(m["verdict"])
    child_labels = {cid: majority(vs) for cid, vs in sorted(by_child.items())}
    conclusion = majority(list(child_labels.values()))
    return {
        "rule": "label-only-fan-in",
        "child_labels": child_labels,
        "conclusion": conclusion,
        "payload": {"child_labels": child_labels},
        "forwarded_dissent": [],
        "forwarded_confidences": [],
        "forwarded_evidence_ids": [],
    }


def per_child_counts(members: tuple[dict[str, Any], ...] = MEMBERS) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for m in members:
        slot = out.setdefault(m["subcouncil"], {COMPLETE: 0, BLOCKED: 0})
        slot[m["verdict"]] += 1
    return out


def tally_forward_fanin(members: tuple[dict[str, Any], ...] = MEMBERS) -> dict[str, Any]:
    """Minimal forwarding set: per-child (n_complete, n_blocked)."""
    counts = per_child_counts(members)
    n_complete = sum(v[COMPLETE] for v in counts.values())
    n_blocked = sum(v[BLOCKED] for v in counts.values())
    labels = [COMPLETE] * n_complete + [BLOCKED] * n_blocked
    child_maj = {cid: majority([COMPLETE] * v[COMPLETE] + [BLOCKED] * v[BLOCKED]) for cid, v in counts.items()}
    dissent_present = any(v[COMPLETE] > 0 and v[BLOCKED] > 0 for v in counts.values())
    labels_disagree = len(set(child_maj.values())) > 1
    return {
        "rule": "tally-forward-fan-in",
        "forwarding_set": list(MINIMAL_FORWARDING_SET),
        "per_subcouncil_verdict_counts": counts,
        "n_complete": n_complete,
        "n_blocked": n_blocked,
        "conclusion": majority(labels),
        "child_labels_reconstructed": child_maj,
        "disagreement_surfaced": labels_disagree,
        "dissent_present": dissent_present,
    }


def lost_under_label_only(members: tuple[dict[str, Any], ...] = MEMBERS) -> dict[str, Any]:
    labels = label_only_fanin(members)
    flat = flattened_member_majority(members)
    tallies = tally_forward_fanin(members)
    unique_evidence = sorted(
        {eid for m in members for eid in m["evidence_ids"] if eid != "shared-spec"}
    )
    dissenters = [m["member_id"] for m in members if m["dissent"]]
    conf_by_child: dict[str, list[float]] = {}
    for m in members:
        conf_by_child.setdefault(m["subcouncil"], []).append(m["confidence"])
    mean_only = {cid: round(sum(vs) / len(vs), 4) for cid, vs in conf_by_child.items()}
    spread = {
        cid: {
            "min": min(vs),
            "max": max(vs),
            "mean": mean_only[cid],
            "bimodal_split": (max(vs) - min(vs)) >= 0.3,
        }
        for cid, vs in conf_by_child.items()
    }
    return {
        "label_only_conclusion": labels["conclusion"],
        "flattened_conclusion": flat["conclusion"],
        "tally_forward_conclusion": tallies["conclusion"],
        "meta_differs_from_full_evidence": labels["conclusion"] != flat["conclusion"],
        "tally_restores_full_evidence": tallies["conclusion"] == flat["conclusion"],
        "lost_dissent_member_ids": dissenters,
        "lost_unique_evidence_ids": unique_evidence,
        "confidence_mean_only": mean_only,
        "confidence_spread": spread,
        "child_labels": labels["child_labels"],
        "flat_counts": {"n_complete": flat["n_complete"], "n_blocked": flat["n_blocked"]},
        "minimal_forwarding_set": list(MINIMAL_FORWARDING_SET),
    }


def assert_example() -> dict[str, Any]:
    report = lost_under_label_only()
    if report["flattened_conclusion"] != COMPLETE:
        raise AssertionError("full evidence must be COMPLETE (5-4)")
    if report["label_only_conclusion"] != BLOCKED:
        raise AssertionError("label-only meta must be BLOCKED (1-2 child labels)")
    if not report["meta_differs_from_full_evidence"]:
        raise AssertionError("loss not exhibited")
    if not report["tally_restores_full_evidence"]:
        raise AssertionError("minimal forwarding set failed to restore")
    if set(report["lost_dissent_member_ids"]) != {"B1", "C1"}:
        raise AssertionError("dissent roster drifted")
    if set(report["lost_unique_evidence_ids"]) != {
        "unique-A-pass",
        "unique-B-pass",
        "unique-C-pass",
    }:
        raise AssertionError("unique evidence roster drifted")
    if not report["confidence_spread"]["B"]["bimodal_split"]:
        raise AssertionError("B confidence spread should be lost under a mean")
    return report
