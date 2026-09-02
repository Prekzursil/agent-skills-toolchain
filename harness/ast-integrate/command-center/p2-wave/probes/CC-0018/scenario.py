#!/usr/bin/env python3
"""Adversarial fixtures and live control runs for CC-0018.

Naive ranking (agent/row counts) is computed here as a BEFORE control only.
The ranker under test never sees those fields.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rank as R  # noqa: E402

SHA_STALE = "a" * 64
SHA_PROBE = "b" * 64
SHA_CORROB = "c" * 64
SHA_ALIAS = SHA_STALE

MECH_WEAK = "stale-premise-carried-as-ground-truth"
MECH_STRONG = "probe-measured-defect-against-live-bytes"


def _claim(
    claim_id: str,
    mechanism: str,
    lineage: list[dict[str, Any]],
    *,
    verification: str,
    severity: str,
    impact: str,
    confidence: str,
    probe: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "claim_id": claim_id,
        "canonical_mechanism": mechanism,
        "duplicate_of": None,
        "support": [],
        "contradiction": [],
        "source_lineage": lineage,
        "verification_status": verification,
        "severity": severity,
        "implementation_impact": impact,
        "confidence": confidence,
        "settling_probe": probe,
        "agent_count": 0,
        "repetition_count": 0,
    }
    if extra:
        rec.update(extra)
    rec["agent_count"] = len(
        {e.get("agent_id") for e in lineage if e.get("agent_id")}
    )
    rec["repetition_count"] = len(lineage)
    return rec


def echo_lineage(
    agent_id: str,
    *,
    path: str = "docs/stale-premise.md",
    uri: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "agent_id": agent_id,
        "source_document": path,
        "path": path,
        "source_sha256": SHA_STALE,
        "domain": "incident-notes",
        "excerpt": "three agents repeated the stale premise",
    }
    if uri:
        row["uri"] = uri
    return row


def strong_lineage() -> dict[str, Any]:
    return {
        "agent_id": "probe-runner",
        "source_document": "command-center/p2-wave/probes/CC-0018/rank.py",
        "path": "command-center/p2-wave/probes/CC-0018/rank.py",
        "source_sha256": SHA_PROBE,
        "domain": "measurement",
        "excerpt": "live probe against ranking function source",
    }


def corroborating_lineage() -> dict[str, Any]:
    return {
        "agent_id": "second-instrument",
        "source_document": "command-center/p2-wave/probes/CC-0018/scenario.py",
        "path": "command-center/p2-wave/probes/CC-0018/scenario.py",
        "source_sha256": SHA_CORROB,
        "domain": "adversarial-control",
        "excerpt": "independent second instrument on a different file",
    }


def weak_claim_n_agents(n: int) -> dict[str, Any]:
    lineage = [
        echo_lineage(f"synthetic-agent-{i:02d}")
        for i in range(1, n + 1)
    ]
    return _claim(
        f"CLM-ECHO-N{n}",
        MECH_WEAK,
        lineage,
        verification="UNVERIFIED",
        severity="low",
        impact="low",
        confidence="remote",
        probe="none — echo of a stale premise",
    )


def strong_claim() -> dict[str, Any]:
    return _claim(
        "CLM-STRONG-PROBE",
        MECH_STRONG,
        [strong_lineage()],
        verification="CONFIRMED",
        severity="high",
        impact="critical",
        confidence="almost_certain",
        probe="python3 -B command-center/p2-wave/probes/CC-0018/probe1_adversarial_repetition.py",
    )


def ten_echo_claims() -> list[dict[str, Any]]:
    claims = []
    for i in range(1, 11):
        claims.append(
            _claim(
                f"CLM-ECHO-{i:02d}",
                MECH_WEAK,
                [echo_lineage(f"echo-agent-{i:02d}")],
                verification="UNVERIFIED",
                severity="low",
                impact="low",
                confidence="remote",
                probe="none — echo",
            )
        )
    return claims


def alias_pair_claims() -> tuple[dict[str, Any], dict[str, Any]]:
    a = _claim(
        "CLM-ALIAS-A",
        "same-source-two-paths",
        [
            {
                "agent_id": "reader-a",
                "source_document": "docs/stale-premise.md",
                "path": "docs/stale-premise.md",
                "source_sha256": SHA_ALIAS,
                "domain": "docs",
            }
        ],
        verification="PARTIAL",
        severity="medium",
        impact="medium",
        confidence="probable",
        probe="sha256 of docs/stale-premise.md",
    )
    b = _claim(
        "CLM-ALIAS-B",
        "same-source-two-paths",
        [
            {
                "agent_id": "reader-b",
                "source_document": "vendor/copy-of-stale-premise.md",
                "path": "./vendor/../vendor/copy-of-stale-premise.md",
                "uri": "file://vendor/copy-of-stale-premise.md",
                "source_sha256": SHA_ALIAS,
                "domain": "vendor-mirror",
            }
        ],
        verification="PARTIAL",
        severity="medium",
        impact="medium",
        confidence="probable",
        probe="sha256 of vendor copy (same bytes)",
        extra={"duplicate_of": "same-source-two-paths"},
    )
    return a, b


def path_alias_game_claim() -> dict[str, Any]:
    """Adversary tries to inflate independence via path spelling variants."""
    paths = [
        "docs/stale-premise.md",
        "./docs/stale-premise.md",
        "docs/./stale-premise.md",
        "docs/foo/../stale-premise.md",
        "file://docs/stale-premise.md",
    ]
    lineage = []
    for i, path in enumerate(paths, 1):
        lineage.append(
            {
                "agent_id": f"alias-gamer-{i}",
                "source_document": path,
                "path": path,
                "uri": path if path.startswith("file://") else None,
                "domain": "docs",
            }
        )
    for row in lineage:
        if row["uri"] is None:
            row.pop("uri")
    return _claim(
        "CLM-PATH-ALIAS-GAME",
        "path-alias-inflation",
        lineage,
        verification="UNVERIFIED",
        severity="low",
        impact="low",
        confidence="remote",
        probe="normalize_document over spelling variants",
    )


def naive_repetition_score(claim: dict[str, Any]) -> int:
    """BEFORE control: rank by how many agents repeated the idea.

    Uses live lineage rows only. A stale agent_count field is ignored so a
    sliced copy cannot fake a higher (or equal) naive score.
    """
    lineage = claim.get("source_lineage") or []
    agents = {
        e.get("agent_id") for e in lineage if isinstance(e, dict) and e.get("agent_id")
    }
    return max(len(agents), len(lineage))


def _score(claim: dict[str, Any]) -> dict[str, int]:
    return R.score_components(claim)


def run_repetition_control() -> dict[str, Any]:
    before = weak_claim_n_agents(1)
    after = weak_claim_n_agents(10)
    sb, sa = _score(before), _score(after)
    nb, na = naive_repetition_score(before), naive_repetition_score(after)
    return {
        "id": "adversarial-n-agent-repetition",
        "before_n_agents": 1,
        "after_n_agents": 10,
        "before_independent": sb,
        "after_independent": sa,
        "before_naive": nb,
        "after_naive": na,
        "independent_score_before": sb["independent_evidence"],
        "independent_score_after": sa["independent_evidence"],
        "independent_rose": sa["independent_evidence"] > sb["independent_evidence"],
        "naive_rose": na > nb,
        "sort_key_unchanged": R.sort_key(before) == R.sort_key(after),
        "pass": (
            sa["independent_evidence"] == sb["independent_evidence"] == 1
            and R.sort_key(before) == R.sort_key(after)
            and na > nb
        ),
    }


def run_strong_vs_echoes() -> dict[str, Any]:
    strong = strong_claim()
    echoes = ten_echo_claims()
    naive_strong = naive_repetition_score(strong)
    naive_echo_mass = sum(naive_repetition_score(c) for c in echoes)
    ranked = R.rank_claims([strong] + echoes, merge=True)
    by_mech = {row["canonical_mechanism"]: row for row in ranked}
    strong_row = by_mech[MECH_STRONG]
    weak_row = by_mech[MECH_WEAK]
    return {
        "id": "strong-probe-vs-ten-echoes",
        "naive_strong": naive_strong,
        "naive_echo_mass": naive_echo_mass,
        "naive_echoes_would_win": naive_echo_mass > naive_strong,
        "strong_rank": strong_row["rank"],
        "weak_rank": weak_row["rank"],
        "strong_sort_key": strong_row["sort_key"],
        "weak_sort_key": weak_row["sort_key"],
        "weak_merged_from": weak_row["merged_from"],
        "weak_independent_evidence": weak_row["components"]["independent_evidence"],
        "strong_independent_evidence": strong_row["components"]["independent_evidence"],
        "pass": (
            strong_row["rank"] < weak_row["rank"]
            and naive_echo_mass > naive_strong
            and weak_row["components"]["independent_evidence"] == 1
            and len(weak_row["merged_from"]) == 10
        ),
    }


def run_lineage_collapse() -> dict[str, Any]:
    a, b = alias_pair_claims()
    n_separate = R.independent_signal_count([a, b])
    merged = R.merge_claims([a, b])
    n_merged = R.independent_signal_count(merged)
    one = copy.deepcopy(a)
    one["source_lineage"] = list(a["source_lineage"]) + list(b["source_lineage"])
    n_one = len(R.source_set(R.ranking_view(one)))
    return {
        "id": "lineage-collapse-same-source-document",
        "claim_ids": [a["claim_id"], b["claim_id"]],
        "paths": [
            a["source_lineage"][0]["path"],
            b["source_lineage"][0]["path"],
        ],
        "shared_sha256": SHA_ALIAS,
        "independent_signals_two_claims": n_separate,
        "independent_signals_merged": n_merged,
        "independent_signals_one_claim_two_rows": n_one,
        "pass": n_separate == 1 and n_merged == 1 and n_one == 1,
    }


def run_monotonicity() -> dict[str, Any]:
    base = strong_claim()
    added = copy.deepcopy(base)
    added["source_lineage"] = list(base["source_lineage"]) + [corroborating_lineage()]
    kb, ka = R.sort_key(base), R.sort_key(added)
    sb, sa = _score(base), _score(added)
    return {
        "id": "monotonicity-independent-corroboration",
        "before_components": sb,
        "after_components": sa,
        "before_sort_key": list(kb),
        "after_sort_key": list(ka),
        "independent_before": sb["independent_evidence"],
        "independent_after": sa["independent_evidence"],
        "rank_key_rose": ka > kb,
        "pass": ka > kb and sa["independent_evidence"] == sb["independent_evidence"] + 1,
    }


def run_path_alias_game() -> dict[str, Any]:
    game = path_alias_game_claim()
    single = path_alias_game_claim()
    single["source_lineage"] = [single["source_lineage"][0]]
    sg, ss = _score(game), _score(single)
    naive_g, naive_s = naive_repetition_score(game), naive_repetition_score(single)
    return {
        "id": "adversary-path-alias-inflation",
        "n_spellings": len(game["source_lineage"]),
        "independent_after_game": sg["independent_evidence"],
        "independent_single_spelling": ss["independent_evidence"],
        "naive_after_game": naive_g,
        "naive_single": naive_s,
        "independent_rose": sg["independent_evidence"] > ss["independent_evidence"],
        "naive_rose": naive_g > naive_s,
        "pass": (
            sg["independent_evidence"] == ss["independent_evidence"] == 1
            and naive_g > naive_s
        ),
    }


def execute_controls() -> dict[str, Any]:
    tests = [
        run_repetition_control(),
        run_strong_vs_echoes(),
        run_lineage_collapse(),
        run_monotonicity(),
        run_path_alias_game(),
    ]
    failed = [t["id"] for t in tests if not t.get("pass")]
    return {
        "tests": tests,
        "failed": failed,
        "pass": not failed,
    }


def ranked_demo() -> list[dict[str, Any]]:
    claims = [strong_claim()] + ten_echo_claims()
    rows = R.rank_claims(claims, merge=True)
    out = []
    for row in rows:
        out.append(
            {
                "rank": row["rank"],
                "claim_id": row["claim_id"],
                "canonical_mechanism": row["canonical_mechanism"],
                "merged_from": row["merged_from"],
                "independent_evidence": row["components"]["independent_evidence"],
                "cross_domain": row["components"]["cross_domain"],
                "verification": row["components"]["verification"],
                "severity": row["components"]["severity"],
                "decision_impact": row["components"]["decision_impact"],
                "confidence": row["components"]["confidence"],
                "source_set": row["source_set"],
            }
        )
    return out
