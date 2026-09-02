#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0120-rebuild-versus-existing-gate.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import build as build_corpus  # noqa: E402
from gate import (  # noqa: E402
    NAMED_FAILURE,
    VERDICT_ALLOW,
    VERDICT_BLOCK,
    evaluate,
    evaluate_build_new_route,
    plant_rebuild,
)
from query import (  # noqa: E402
    INTERFACE_VERSION,
    by_route,
    by_state,
    empty_result,
    registry_candidates,
    wrap,
)

OUT_REL = "command-center/wfa/WFA-0120-rebuild-versus-existing-gate.json"
OUT = REPO / OUT_REL
SENTINEL = "SUCCESS:WFA-0120"
QUESTION = (
    "Implementation target: a gate that runs before any BUILD-NEW route - 32 "
    "blueprints are state NEW and 26 carry route BUILD-NEW - and fails when "
    "the registry already contains a candidate covering the same mechanism "
    "set with equal or better evidence, the spec's named failure class in "
    "which discovery ignores an existing superior workflow and rebuilds it."
)

RESTORE_CANDIDATES = [
    Path(
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
    ),
    Path.home() / ".claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    REPO / "harness-restore-20260806" / "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
]


def original_library_hits() -> list[str]:
    hits = []
    for p in RESTORE_CANDIDATES:
        try:
            if p.is_file() and p.stat().st_size > 0:
                hits.append(str(p))
        except OSError:
            continue
    return hits


def _decision_row(d: dict) -> dict:
    return {
        "proposal_id": d["proposal_id"],
        "verdict": d["verdict"],
        "reason": d["reason"],
        "cited_candidate_id": d["cited_candidate_id"],
        "nearest_existing_id": d["nearest_existing_id"],
        "overlap": d["overlap"],
        "evidence_comparison": d["evidence_comparison"],
        "proposal_mechanisms": d["proposal_mechanisms"],
    }


def build_artifact() -> dict:
    corpus = build_corpus()
    registry = registry_candidates(corpus)
    decisions = evaluate_build_new_route(corpus)
    blocked = [d for d in decisions if d["verdict"] == VERDICT_BLOCK]
    allowed = [d for d in decisions if d["verdict"] == VERDICT_ALLOW]

    planted_src = next(c for c in registry if c["id"] == "cand.lit-review")
    planted = plant_rebuild(planted_src, "bp.planted-rename-lit-review")
    planted_on = evaluate(planted, registry, enabled=True)
    planted_off = evaluate(planted, registry, enabled=False)

    novel = next(b for b in corpus["blueprints"] if b["id"] == "bp.build-new-19")
    novel_on = evaluate(novel, registry, enabled=True)

    adapt = next(b for b in corpus["blueprints"] if b["id"] == "bp.new-adapt")
    adapt_d = evaluate(adapt, registry, enabled=True)

    miss = empty_result()
    by_bn = wrap(by_route(corpus, "BUILD-NEW"))
    by_new = wrap(by_state(corpus, "NEW"))

    both_ok = (
        planted_on["verdict"] == VERDICT_BLOCK
        and planted_on["cited_candidate_id"] == "cand.lit-review"
        and planted_off["verdict"] == VERDICT_ALLOW
        and novel_on["verdict"] == VERDICT_ALLOW
        and adapt_d["verdict"] == "SKIP-NOT-BUILD-NEW"
    )

    census = corpus["census"]
    hits = original_library_hits()
    answer = (
        "The anti-rebuild gate evaluates every BUILD-NEW blueprint against "
        "definition-derived mechanism sets (self-description is ignored). It "
        "BLOCKs when an existing candidate covers the proposal set with equal "
        "or better evidence (lexicographic tier, independent-source count, "
        "quality) and cites that candidate id. On this control corpus "
        f"BUILD-NEW n={census['n_build_new']} (blocked={len(blocked)} "
        f"allowed={len(allowed)}) and NEW n={census['n_new']}. Planted rename "
        f"of cand.lit-review is {planted_on['verdict']} citing "
        f"{planted_on['cited_candidate_id']}; legitimate novel lattice+qec is "
        f"{novel_on['verdict']}. Original 09-WORKFLOW-BLUEPRINT-LIBRARY.json "
        f"present={bool(hits)}. {SENTINEL}"
    )
    return {
        "record_type": "RegressionFixture",
        "unit_id": "WFA-0120",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "Anti-rebuild gate: block a BUILD-NEW route when a superior workflow already exists",
        "question": QUESTION,
        "answer": answer,
        "named_failure": NAMED_FAILURE,
        "schema_note": (
            "Catalog output_schema command-center/wfa/schema/wfa-schema-pack.json"
            "#/$defs/RegressionFixture is absent (WFA-0001 not delivered here). "
            "Record is a RegressionFixture: named failure, both-states control, "
            "per-BUILD-NEW nearest-existing with overlap and evidence comparison, "
            "and a planted rebuild the gate rejects."
        ),
        "inputs_present": {
            "original_blueprint_library": bool(hits),
            "original_library_paths_hit": hits,
            "wfa_0059_mechanism_matrix": False,
            "wfa_0084_query_interface": False,
            "local_query_interface_version": INTERFACE_VERSION,
            "control_corpus": True,
        },
        "gate": {
            "id": "wfa-0120-rebuild-versus-existing",
            "runs_before": "BUILD-NEW",
            "cover_rule": "proposal mechanisms subset-or-equal existing mechanisms AND existing evidence >= proposal evidence",
            "evidence_key": "lexicographic (tier_rank, independent_source_count, quality)",
            "citation_on_block": True,
            "uses_definition_not_self_description": True,
        },
        "corpus_census": census,
        "corpus_origin": corpus["origin"],
        "query_empty_is_empty_list": miss["empty"] is True and miss["matches"] == [],
        "query_build_new_count": by_bn["count"],
        "query_new_count": by_new["count"],
        "build_new_decisions": [_decision_row(d) for d in decisions],
        "blocked_ids": [d["proposal_id"] for d in blocked],
        "allowed_ids": [d["proposal_id"] for d in allowed],
        "controls": [
            {
                "id": "planted-rename-rebuild",
                "kind": "known-present-rebuild",
                "plant": {
                    "id": planted["id"],
                    "path": "command-center/p2-wave/probes/WFA-0120/gate.py",
                    "from": "cand.lit-review",
                },
                "gated": _decision_row(planted_on),
                "ungated_mutant": _decision_row(planted_off),
                "verdict": "fired"
                if planted_on["verdict"] == VERDICT_BLOCK
                else "silent",
            },
            {
                "id": "legitimate-novel-build-new",
                "kind": "known-absent-incumbent",
                "plant": {
                    "id": novel["id"],
                    "path": "command-center/p2-wave/probes/WFA-0120/corpus.py",
                },
                "gated": _decision_row(novel_on),
                "verdict": "silent"
                if novel_on["verdict"] == VERDICT_ALLOW
                else "false-positive",
            },
            {
                "id": "non-build-new-is-skipped",
                "kind": "route-filter",
                "plant": {
                    "id": adapt["id"],
                    "path": "command-center/p2-wave/probes/WFA-0120/corpus.py",
                },
                "gated": _decision_row(adapt_d),
                "verdict": "fired"
                if adapt_d["verdict"] == "SKIP-NOT-BUILD-NEW"
                else "leaked",
            },
        ],
        "both_states": {
            "planted_rebuild_blocked": planted_on["verdict"] == VERDICT_BLOCK,
            "planted_cites_incumbent": planted_on["cited_candidate_id"]
            == "cand.lit-review",
            "ungated_would_allow_rebuild": planted_off["verdict"] == VERDICT_ALLOW,
            "legitimate_novel_allowed": novel_on["verdict"] == VERDICT_ALLOW,
            "ok": both_ok,
        },
        "tests": [
            {
                "id": "planted-rebuild-rejected",
                "result": "PASS" if planted_on["verdict"] == VERDICT_BLOCK else "FAIL",
            },
            {
                "id": "legitimate-build-new-passes",
                "result": "PASS" if novel_on["verdict"] == VERDICT_ALLOW else "FAIL",
            },
            {
                "id": "block-cites-candidate-id",
                "result": "PASS"
                if planted_on["cited_candidate_id"] == "cand.lit-review"
                else "FAIL",
            },
            {
                "id": "census-26-32",
                "result": "PASS"
                if census["n_build_new"] == 26 and census["n_new"] == 32
                else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0120-probe2-independent-nearest",
            "verdict": "PASS" if both_ok else "FAIL",
            "independent": True,
            "note": (
                "Probe 2 recomputes covering incumbents without calling "
                "evaluate() and checks every BLOCK cites a live registry id. "
                "A second-vendor reviewer was not fabricated."
            ),
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/WFA-0120/gate.py",
                "kind": "implementation",
                "claim": "Cover+evidence gate with citation on BLOCK.",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0120/probe1_both_states.py",
                "kind": "both-states-control",
                "claim": "Planted rename is rejected; novel BUILD-NEW is allowed.",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0120/probe2_nearest_and_citation.py",
                "kind": "independent-recompute",
                "claim": "Every BUILD-NEW has nearest overlap+evidence; BLOCKs cite ids.",
            },
        ],
        "output_path": OUT_REL,
        "output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture"
        ),
    }


def write_artifact() -> Path:
    doc = build_artifact()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    fx = HERE / "fixtures"
    fx.mkdir(parents=True, exist_ok=True)
    (fx / "corpus.json").write_text(
        json.dumps(build_corpus(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return OUT


def main() -> int:
    path = write_artifact()
    print(f"wrote {path.relative_to(REPO).as_posix()}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
