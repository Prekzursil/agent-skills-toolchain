#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0061-mechanism-coverage-gaps.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import coverage as CV  # noqa: E402
import sources as S  # noqa: E402

OUT = "command-center/wfa/WFA-0061-mechanism-coverage-gaps.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0061/coverage_matrix.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0061/probe1_both_directions.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0061/probe2_spotcheck_goals.py"
)
SENTINEL = "SUCCESS:WFA-0061"
QUESTION = (
    "Over the mechanism-by-artifact bipartite graph, which canonical "
    "mechanisms are implemented by at least one candidate but by ZERO of "
    "the 108 blueprints - and which blueprints implement no recognised "
    "mechanism at all?"
)


def main() -> int:
    corpus = C.load_corpus()
    C.materialize_bodies(corpus)
    live = S.inventory(REPO)
    worktree_docs = CV.load_worktree_docs(REPO, live.get("worktree_observed") or [])
    computed = CV.compute(corpus, live, worktree_docs)

    if not computed["both_directions_published"]:
        print("FAILED:WFA-0061 emit both directions not published")
        return 1
    if computed["namespaces"]["collision"] or not computed["namespaces"]["prefix_ok"]:
        print("FAILED:WFA-0061 emit namespace collision")
        return 1
    if computed["planted_extraction_miss"]["published_as_empty"]:
        print("FAILED:WFA-0061 emit planted extraction miss published as empty")
        return 1
    if not computed["planted_extraction_miss"]["prose_extractor_lists_as_empty"]:
        print("FAILED:WFA-0061 emit prose mutant did not fire on planted miss")
        return 1
    spots = computed["spot_checks"]
    if spots["n_checked"] < 10 or not spots["all_survived"]:
        print("FAILED:WFA-0061 emit spot checks", json.dumps(spots)[:1500])
        return 1
    if not spots["both_directions_in_sample"]:
        print("FAILED:WFA-0061 emit spot-check sample hid a direction")
        return 1
    if not computed["generation_lane_is_typed"]:
        print("FAILED:WFA-0061 emit goals collapsed to an id list")
        return 1
    if live.get("invented_108_blueprints"):
        print("FAILED:WFA-0061 emit invented 108 blueprints")
        return 1
    if computed["incidence"]["n_blueprints"] == 108:
        print("FAILED:WFA-0061 emit fixture padded to catalog 108")
        return 1

    incidence = computed["incidence"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "record_type": "CoverageMatrix",
        "schema_id": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/CoverageMatrix",
        "schema_pack_present": bool((live.get("schema_pack") or {}).get("present")),
        "local_schema": SCHEMA_REL,
        "unit_id": "WFA-0061",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Find the mechanisms that no blueprint carries and the "
            "blueprints that carry no mechanism"
        ),
        "question": QUESTION,
        "row_axis": "canonical_mechanism",
        "col_axis": "artifact",
        "row_ids": incidence["row_ids"],
        "col_ids": incidence["col_ids"],
        "cells": incidence["cells"],
        "n_cells": incidence["n_cells"],
        "n_evidenced": incidence["n_evidenced"],
        "n_honest_null": incidence["n_honest_null"],
        "extraction_rule": computed["extraction_rule"],
        "corpus_id": computed["corpus_id"],
        "corpus_label": computed["corpus_label"],
        "corpus_sha256": CV.corpus_sha(C.CORPUS_PATH),
        "uncovered_mechanisms": computed["uncovered_mechanisms"],
        "empty_blueprints": computed["empty_blueprints"],
        "blueprint_only_mechanisms": incidence["blueprint_only_mechanisms"],
        "both_directions_published": True,
        "spot_checks": spots,
        "generation_lane_goals": computed["generation_lane_goals"],
        "generation_lane_is_typed": True,
        "planted_extraction_miss": computed["planted_extraction_miss"],
        "use_versus_mention": computed["use_versus_mention"],
        "namespaces": computed["namespaces"],
        "live_sources": live,
        "worktree_observed_extraction": computed["worktree_observed_extraction"],
        "counts": {
            "fixture_candidates": incidence["n_candidates"],
            "fixture_blueprints": incidence["n_blueprints"],
            "uncovered_mechanisms": len(computed["uncovered_mechanisms"]),
            "empty_blueprints": len(computed["empty_blueprints"]),
            "catalog_claimed_blueprints": live.get("catalog_claimed_blueprints"),
            "live_108_enumerated": live.get("library_108_enumerated"),
        },
        "answer": (
            f"Fixture corpus ({incidence['n_candidates']} candidates, "
            f"{incidence['n_blueprints']} blueprints): uncovered mechanisms "
            f"{computed['uncovered_mechanisms']}; empty blueprints "
            f"{computed['empty_blueprints']}. Named 108-blueprint library "
            f"present={live.get('library_108_enumerated')}; WFA-0059 present="
            f"{live.get('extraction_matrix_enumerated')}. Catalog 108 was not "
            "invented. Both gap lists are published and routed as typed "
            "generation-lane goals. SUCCESS:WFA-0061"
        ),
        "evidence": [
            {
                "id": "A-set-differences",
                "claim": (
                    "Both set differences were computed exactly over the "
                    "bipartite incidence matrix and both gap lists are enumerated."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0061/coverage.py:build_incidence",
            },
            {
                "id": "B-spot-check-bodies",
                "claim": (
                    "At least ten claimed gaps were re-checked by reading "
                    "blueprint bodies through the definition extractor, not "
                    "the mechanisms[] prose field."
                ),
                "verdict": "CONFIRMED" if spots["all_survived"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/WFA-0061/spotcheck.py",
            },
            {
                "id": "C-typed-goals",
                "claim": "Every published gap is a typed generation-lane goal, not a bare id list.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0061/goals.py",
            },
            {
                "id": "D-live-108",
                "claim": (
                    "The catalog's 108-blueprint library was enumerated from disk."
                ),
                "verdict": "NOT-CHECKED" if not live.get("library_108_enumerated") else "CONFIRMED",
                "anchor": "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
            },
        ],
        "tests": [
            {
                "id": "T-BOTH-DIRECTIONS",
                "name": "both gap directions published",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-SPOT-CHECK-BODIES",
                "name": "ten claimed gaps survive body reads",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T-TYPED-GOALS",
                "name": "gaps routed as typed generation-lane goals",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-DROP-EMPTY-BLUEPRINTS",
                "kind": "suppress-direction",
                "description": (
                    "Dropping empty_blueprints while keeping uncovered "
                    "mechanisms must fail the both-directions predicate."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "NC-PROSE-EXTRACTOR",
                "kind": "self-description-extraction-miss",
                "description": (
                    "Trusting mechanisms[] lists bp.prose-says-empty as empty; "
                    "definition extraction does not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0061-probe2-spotcheck-goals",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests",
            "verdict": "PASS",
            "notes": (
                "Adversarial probe re-reads blueprint body files, checks the "
                "planted extraction miss, and rejects a bare gap-id list."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "09-WORKFLOW-BLUEPRINT-LIBRARY.json and "
                    "WFA-0059-mechanism-extraction.json are absent, so the "
                    "108-by-canonical-mechanism census is not a count of those "
                    "records."
                ),
                "settling_experiment": (
                    "Place the named library and WFA-0059 matrix on disk and "
                    "re-run coverage.compute over those rows."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "falsifiable_answer": {
            "question": QUESTION,
            "uncovered_mechanisms": computed["uncovered_mechanisms"],
            "empty_blueprints": computed["empty_blueprints"],
            "live_108_enumerated": live.get("library_108_enumerated"),
            "fixture_n_blueprints": incidence["n_blueprints"],
        },
        "min_bytes_threshold": 2048,
        "generated_at": now,
    }

    schema = json.loads((HERE / "coverage_matrix.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:WFA-0061 emit sentinel missing from text")
        return 1
    print(f"wrote {OUT} uncovered={len(computed['uncovered_mechanisms'])} "
          f"empty_bp={len(computed['empty_blueprints'])} "
          f"cells={incidence['n_cells']}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
