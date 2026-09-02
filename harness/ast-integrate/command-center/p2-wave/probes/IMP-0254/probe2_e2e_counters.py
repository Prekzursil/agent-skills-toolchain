#!/usr/bin/env python3
"""Probe 2: e2e through library entries drives real engines (counter proof)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.foundry import counters  # noqa: E402
from tools.foundry.forge import ForgeError  # noqa: E402
from tools.foundry.fusion_ops import FusionRefused  # noqa: E402
from tools.foundry.tournament import ranking_from_matrix  # noqa: E402
from tools.library import registry  # noqa: E402
from tools.library.load import load_library  # noqa: E402


def _must(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAILED:IMP-0254-probe2 {msg}")


def main() -> int:
    load_library()
    counters.reset()

    scout = registry.execute(
        "workflow-scout",
        {
            "goal": "recover-and-verify a document pack",
            "required_capabilities": ["retrieve", "verify"],
        },
    )
    _must(counters.get("scout.run") >= 1, "scout engine counter did not increment")
    _must(counters.get("scout.score_candidate") >= 1, "scout scoring counter silent")
    _must(not scout.get("empty_honest"), "planted incumbent produced empty ranking")
    ranked = scout.get("ranked") or []
    _must(ranked and ranked[0].get("id") == "incumbent-rtv", "planted incumbent not rank-1")
    _must(ranked[0].get("verdict") == "ADOPT", "incumbent verdict not ADOPT")
    _must(ranked[0].get("provenance"), "ranked hit missing provenance")
    print(f"scout.rank1={ranked[0].get('id')} verdict={ranked[0].get('verdict')}")
    print(f"counters.scout.run={counters.get('scout.run')}")

    empty = registry.execute(
        "workflow-scout",
        {"goal": "teleport across campuses", "required_capabilities": ["teleport"]},
    )
    _must(empty.get("empty_honest") is True, "unknown capability was padded")
    _must(empty.get("ranked") == [], "unknown capability returned hits")
    print("scout.empty_honest=True")

    before_forge = counters.get("forge.run")
    forged = registry.execute(
        "workflow-forge",
        {
            "goal": "recover-and-verify",
            "required_capabilities": ["retrieve", "verify"],
            "scout": scout,
        },
    )
    _must(counters.get("forge.run") > before_forge, "forge engine counter did not increment")
    _must(counters.get("forge.simulate") >= 1, "simulation counter silent")
    wf = forged.get("workflow") or {}
    _must(wf.get("certified") is True, "forge returned uncertified workflow")
    _must(wf.get("operator") == "adopt", "expected adopt of incumbent")
    print(f"forge.operator={wf.get('operator')} certified={wf.get('certified')}")

    try:
        registry.execute(
            "workflow-forge",
            {"goal": "recover-and-verify", "scout": scout, "broken_input": "planted-broken"},
        )
        _must(False, "broken forge input was accepted")
    except ForgeError as exc:
        _must(exc.code == "typed-failure", f"broken input code {exc.code}")
        print(f"forge.broken_input.code={exc.code}")

    retrieve_only = {
        "id": "retrieve-only",
        "stages": [
            {
                "id": "retrieve",
                "input_type": "Goal",
                "output_type": "Doc",
                "capabilities": ["retrieve"],
            }
        ],
    }
    verify_only = {
        "id": "verify-only",
        "stages": [
            {
                "id": "verify",
                "input_type": "Doc",
                "output_type": "Report",
                "capabilities": ["verify"],
            }
        ],
    }
    before_fusion = counters.get("fusion.apply_operator")
    fused = registry.execute(
        "workflow-merger-composer",
        {"operator": "concat", "parent_a": retrieve_only, "parent_b": verify_only},
    )
    _must(counters.get("fusion.apply_operator") > before_fusion, "fusion counter silent")
    _must(fused.get("operator") == "concat", "concat operator not recorded")
    _must(len(fused.get("stages") or []) == 2, "concat did not keep both stages")
    _must(
        fused.get("id") != retrieve_only["id"] and fused.get("id") != verify_only["id"],
        "fusion id collapsed to a parent",
    )
    print(f"fusion.id={fused.get('id')} stages={len(fused.get('stages') or [])}")

    try:
        registry.execute(
            "workflow-merger-composer",
            {
                "operator": "concat",
                "parent_a": retrieve_only,
                "parent_b": {
                    "id": "starts-with-goal",
                    "stages": [
                        {
                            "id": "retrieve",
                            "input_type": "Goal",
                            "output_type": "Doc",
                            "capabilities": ["retrieve"],
                        }
                    ],
                },
            },
        )
        _must(False, "contract mismatch was accepted")
    except FusionRefused as exc:
        _must(exc.code == "contract-mismatch", f"mismatch code {exc.code}")
        print(f"fusion.mismatch.code={exc.code}")

    before_t = counters.get("tournament.run")
    tourney = registry.execute(
        "workflow-tournament",
        {
            "candidates": [
                {"id": "alpha", "metric": 10},
                {"id": "beta", "metric": 10},
                {"id": "gamma", "metric": 8},
            ]
        },
    )
    _must(counters.get("tournament.run") > before_t, "tournament counter silent")
    _must(tourney.get("has_tie") is True, "injected tie was ordered")
    _must(tourney.get("pairwise_matrix"), "pairwise matrix missing")
    rebuilt = ranking_from_matrix(tourney["pairwise_matrix"], tourney["candidate_ids"])
    live_ranks = [(r["id"], r["rank"]) for r in tourney["ranking"]]
    rebuilt_ranks = [(r["id"], r["rank"]) for r in rebuilt]
    _must(live_ranks == rebuilt_ranks, "ranking not reconstructible from matrix")
    alpha_rank = next(r["rank"] for r in tourney["ranking"] if r["id"] == "alpha")
    beta_rank = next(r["rank"] for r in tourney["ranking"] if r["id"] == "beta")
    _must(alpha_rank == beta_rank, "tied pair received distinct ranks")
    print(f"tournament.has_tie={tourney.get('has_tie')} reconstructed=True")

    mock_before = counters.snapshot()
    mock = {
        "engine": "mock",
        "ranked": [{"id": "incumbent-rtv", "verdict": "ADOPT"}],
        "empty_honest": False,
    }
    _must(mock["ranked"][0]["id"] == "incumbent-rtv", "mock control setup")
    _must(counters.snapshot() == mock_before, "mock JSON bumped engine counters")
    print("mock.path_does_not_bump_counters=True")

    snap = counters.snapshot()
    print(f"counters={snap}")
    print("SUCCESS:IMP-0254-probe2 e2e real-engine counters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
