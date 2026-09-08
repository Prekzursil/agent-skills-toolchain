#!/usr/bin/env python3
"""CC-0018 planted controls: anti-repetition ranking over claim records."""

from __future__ import annotations

import ast
import copy
from pathlib import Path

import claim_rank as cr

REPO = Path(__file__).resolve().parents[3]
RANK_SRC = REPO / "tools/command-center/claim_rank.py"


def _claim(
    claim_id: str,
    mechanism: str,
    *,
    anchors: list[tuple[str, str | None]],
    confidence: str | None = "likely",
    verification: str = "UNVERIFIED",
    impact: str = "medium",
    settling: str = "default-settling-probe",
    **extra,
) -> dict:
    rec = {
        "schema_version": 1,
        "schema_status": "PROVISIONAL",
        "superseded_by_unit": "ARC-0085",
        "claim_id": claim_id,
        "canonical_mechanism": mechanism,
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [
            {"anchor": a, "probe": p} for a, p in anchors
        ],
        "confidence": confidence,
        "verification_status": verification,
        "implementation_impact": impact,
        "settling_probe": settling,
    }
    rec.update(extra)
    return rec


def test_adversarial_control_rank_does_not_rise_with_n_shared_source_echoes() -> None:
    """Duplicate one claim across N synthetic agents sharing one source."""
    base = _claim(
        "ADV",
        "shared-stale-premise",
        anchors=[("docs://stale.md", "agent-read")],
        confidence="likely",
        verification="UNVERIFIED",
        impact="medium — carried as ground truth",
        settling="re-read docs://stale.md",
    )
    background = [
        _claim(
            "BG1",
            "background-strong",
            anchors=[
                ("probes://a", "command"),
                ("probes://b", "file-read"),
            ],
            confidence="almost-certain",
            verification="CONFIRMED",
            impact="high — decision-blocking",
            settling="pytest -q",
        ),
        _claim(
            "BG2",
            "background-weak",
            anchors=[("notes://weak", "skim")],
            confidence="uncertain",
            verification="NOT-CHECKED",
            impact="low — cosmetic",
            settling="manual skim",
        ),
    ]
    report = cr.adversarial_repetition_run(
        base, n_values=[1, 5, 15, 40], background=background
    )
    assert report["ok"] is True
    assert report["score_rose"] is False
    assert report["rank_improved"] is False
    before = report["before"]
    after = report["after"]
    assert before["score"] == after["score"]
    assert before["rank"] == after["rank"]
    assert after["repetition_count"] == 40
    assert after["independent_source_count"] == 1


def test_strong_independent_probe_outranks_ten_weaker_echoes() -> None:
    """One strong independent probe outranks ten echoes of a weaker claim."""
    strong = _claim(
        "STRONG",
        "strong-independent-finding",
        anchors=[("evidence://probe-primary", "command-trace")],
        confidence="almost-certain",
        verification="CONFIRMED",
        impact="critical — blocker for phase gate",
        settling="python3 -B tools/command-center/claim_rank.py meta",
    )
    weak_echoes = [
        _claim(
            f"WEAK-ECHO-{i}",
            "weak-echo-finding",
            anchors=[("rumor://same-stale-note", f"echo-agent-{i}")],
            confidence="uncertain",
            verification="UNVERIFIED",
            impact="low — cosmetic",
            settling="restate rumor://same-stale-note",
        )
        for i in range(10)
    ]
    ranked = cr.rank_claims([strong, *weak_echoes])
    strong_row = cr.find_rank(ranked, "STRONG")
    weak_row = cr.find_rank(ranked, cluster="weak-echo-finding")
    assert strong_row is not None and weak_row is not None
    assert strong_row["rank"] < weak_row["rank"]
    assert strong_row["score"] > weak_row["score"]
    assert weak_row["repetition_count"] == 10
    assert weak_row["independent_source_count"] == 1


def test_lineage_collapse_same_source_document_is_one_signal() -> None:
    """Two claims whose lineages resolve to the same source count as one signal."""
    a = _claim(
        "L1",
        "lineage-collapse-case",
        anchors=[("./docs/spec.md", "read")],
        settling="grep docs/spec.md",
    )
    b = _claim(
        "L2",
        "lineage-collapse-case",
        anchors=[("docs/spec.md/", "read-again"), ("docs/spec.md#section", "browser")],
        settling="grep docs/spec.md",
    )
    signals = cr.independent_signals([a, b])
    assert signals["independent_source_count"] == 1
    assert signals["independent_sources"] == ["docs/spec.md"]
    assert signals["repetition_count"] == 2

    scored = cr.score_cluster([a, b])
    assert scored["independent_source_count"] == 1
    # Same score as a single record with that source (quality fields equalized).
    single = cr.score_cluster([a])
    assert scored["independence"] == single["independence"]


def test_monotonicity_independent_corroborating_probe_raises_rank() -> None:
    """Adding a genuinely independent corroborating probe must raise the rank."""
    mech = "monotonicity-target"
    competitor = _claim(
        "COMP",
        "monotonicity-competitor",
        anchors=[("other://one", "cmd")],
        confidence="likely",
        verification="PARTIAL",
        impact="medium",
        settling="other probe",
    )
    before_rec = _claim(
        "MONO",
        mech,
        anchors=[("evidence://first", "command")],
        confidence="likely",
        verification="PARTIAL",
        impact="medium",
        settling="command evidence://first",
    )
    ranked_before = cr.rank_claims([before_rec, competitor])
    row_before = cr.find_rank(ranked_before, "MONO")
    assert row_before is not None

    after_rec = copy.deepcopy(before_rec)
    after_rec["source_lineage"].append(
        {"anchor": "evidence://second-independent", "probe": "file-read"}
    )
    after_rec["legacy_fields"] = {
        "independent_probes": [
            {
                "anchor": "evidence://second-independent",
                "method": "file-read",
            }
        ]
    }
    ranked_after = cr.rank_claims([after_rec, competitor])
    row_after = cr.find_rank(ranked_after, "MONO")
    assert row_after is not None
    assert row_after["score"] > row_before["score"]
    assert row_after["independent_source_count"] == row_before["independent_source_count"] + 1
    # Rank improves or stays strictly better on score; with one competitor it should
    # not get worse.
    assert row_after["rank"] <= row_before["rank"]


def test_score_cluster_source_does_not_multiply_by_repetition_count() -> None:
    """AST/param guard: score_cluster body must not multiply by len(records)."""
    tree = ast.parse(RANK_SRC.read_text(encoding="utf-8"))
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "score_cluster":
            fn = node
            break
    assert fn is not None
    src = ast.get_source_segment(RANK_SRC.read_text(encoding="utf-8"), fn) or ""
    # Forbidden patterns that would bake repetition into the score.
    assert "len(records)" not in src or "repetition_count" in src
    # Explicit contract string must remain in the formula documentation.
    assert "repetition_count" in src
    assert "NOT" in src or "not" in src

    # Behavioral: 1 vs 20 echoes identical score.
    one = [
        _claim(
            "R1",
            "rep-guard",
            anchors=[("shared://x", "p")],
            settling="s",
            verification="UNVERIFIED",
            confidence="uncertain",
            impact="low",
        )
    ]
    many = [
        _claim(
            f"R{i}",
            "rep-guard",
            anchors=[("shared://x", f"agent-{i}")],
            settling="s",
            verification="UNVERIFIED",
            confidence="uncertain",
            impact="low",
        )
        for i in range(20)
    ]
    assert cr.score_cluster(one)["score"] == cr.score_cluster(many)["score"]
