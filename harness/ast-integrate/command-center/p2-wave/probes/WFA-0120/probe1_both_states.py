#!/usr/bin/env python3
"""Probe 1: both-states control — planted rebuild blocked, novel BUILD-NEW allowed."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import M, build as build_corpus  # noqa: E402
from gate import (  # noqa: E402
    VERDICT_ALLOW,
    VERDICT_BLOCK,
    VERDICT_INCOMPLETE,
    VERDICT_SKIP,
    evaluate,
    plant_rebuild,
)
from query import registry_candidates  # noqa: E402


def fail(msg: str, payload: dict | None = None) -> int:
    if payload:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAILED:WFA-0120-probe1 {msg}")
    return 1


def main() -> int:
    corpus = build_corpus()
    registry = registry_candidates(corpus)
    incumbent = next(c for c in registry if c["id"] == "cand.lit-review")

    planted = plant_rebuild(incumbent, "bp.planted-rename-lit-review")
    if planted["mechanisms_from_definition"] != incumbent["mechanisms_from_definition"]:
        return fail("plant did not preserve definition mechanisms")
    if planted["id"] == incumbent["id"]:
        return fail("plant kept the incumbent id")

    gated = evaluate(planted, registry, enabled=True)
    ungated = evaluate(planted, registry, enabled=False)
    if gated["verdict"] != VERDICT_BLOCK:
        return fail(f"planted rebuild verdict={gated['verdict']} want=BLOCK-REBUILD", gated)
    if gated["cited_candidate_id"] != "cand.lit-review":
        return fail(
            f"planted rebuild cited={gated['cited_candidate_id']!r} want=cand.lit-review",
            gated,
        )
    if ungated["verdict"] != VERDICT_ALLOW:
        return fail("ungated mutant did not allow the planted rebuild", ungated)

    novel = next(b for b in corpus["blueprints"] if b["id"] == "bp.build-new-19")
    novel_d = evaluate(novel, registry, enabled=True)
    if novel_d["verdict"] != VERDICT_ALLOW:
        return fail(f"novel BUILD-NEW verdict={novel_d['verdict']} want=ALLOW", novel_d)

    # Use-versus-mention: self-description copies the incumbent, definition is novel.
    trap = deepcopy(novel)
    trap["id"] = "bp.self-described-as-lit-review"
    trap["mechanisms_self_described"] = list(incumbent["mechanisms_from_definition"])
    trap_d = evaluate(trap, registry, enabled=True)
    if trap_d["verdict"] != VERDICT_ALLOW:
        return fail("self-description trap was credited as a rebuild", trap_d)

    empty = {
        "id": "bp.empty-mechanisms",
        "route": "BUILD-NEW",
        "mechanisms_from_definition": [],
        "evidence_tier": "E4",
        "independent_source_count": 0,
        "quality": 0,
    }
    empty_d = evaluate(empty, registry, enabled=True)
    if empty_d["verdict"] != VERDICT_INCOMPLETE:
        return fail("empty mechanism set was not fail-closed", empty_d)

    adapt = next(b for b in corpus["blueprints"] if b["id"] == "bp.new-adapt")
    adapt_d = evaluate(adapt, registry, enabled=True)
    if adapt_d["verdict"] != VERDICT_SKIP:
        return fail("ADAPT route leaked into BUILD-NEW gate", adapt_d)

    # Partial keyword overlap is not coverage.
    partial = {
        "id": "bp.cite-plus-zk",
        "route": "BUILD-NEW",
        "mechanisms_from_definition": [M["cite"], M["zk"]],
        "evidence_tier": "E4",
        "independent_source_count": 0,
        "quality": 0,
    }
    partial_d = evaluate(partial, registry, enabled=True)
    if partial_d["verdict"] != VERDICT_ALLOW:
        return fail("shared-token non-subset was blocked (false positive)", partial_d)

    payload = {
        "probe": "probe1-both-states",
        "unit_id": "WFA-0120",
        "planted_verdict": gated["verdict"],
        "cited": gated["cited_candidate_id"],
        "ungated_verdict": ungated["verdict"],
        "novel_verdict": novel_d["verdict"],
        "self_desc_trap_verdict": trap_d["verdict"],
        "empty_verdict": empty_d["verdict"],
        "adapt_verdict": adapt_d["verdict"],
        "partial_overlap_verdict": partial_d["verdict"],
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "planted=BLOCK-REBUILD cited=cand.lit-review "
        "ungated=ALLOW novel=ALLOW trap=ALLOW empty=BLOCK-INCOMPLETE "
        "adapt=SKIP partial=ALLOW"
    )
    print("SUCCESS:WFA-0120-probe1 planted-rebuild-rejected novel-allowed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
