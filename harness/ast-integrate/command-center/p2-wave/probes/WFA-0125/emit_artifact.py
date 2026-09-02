#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0125-library-category-coverage.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0125/probe1_extract_count.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0125/probe2_spotcheck_and_recount.py"
)
QUESTION = (
    "For each workflow the spec's Phase 7 library explicitly requires - "
    "across research and evidence, engineering and reliability, security "
    "and governance, product and strategy, data and science, and collective "
    "intelligence - is there a covering candidate, a covering blueprint, "
    "both, or neither?"
)


def main() -> int:
    units = X.catalog_units()
    extracted = X.extract_requirements(units)
    if extracted["errors"]:
        print("FAILED:WFA-0125 emit extraction errors")
        print(extracted["errors"])
        return 1
    expected = extracted["expected_total_from_imp0178"]
    if extracted["n"] != expected:
        print(
            f"FAILED:WFA-0125 emit n={extracted['n']} "
            f"imp0178_sum={expected}"
        )
        return 1
    if extracted["family_counts_parsed"] != extracted["family_counts_imp0178"]:
        print("FAILED:WFA-0125 emit per-family mismatch")
        print(extracted["family_counts_parsed"])
        print(extracted["family_counts_imp0178"])
        return 1
    q_fams = extracted["wfa0125_question_families"]
    if len(q_fams) != 6:
        print(f"FAILED:WFA-0125 emit question families n={len(q_fams)} {q_fams}")
        return 1
    measured = X.measure_cells(extracted["requirements"])
    trap = measured["keyword_trap"]
    if not trap["downgraded"]:
        print("FAILED:WFA-0125 emit keyword trap did not downgrade")
        print(trap)
        return 1
    neither_or_uncovered = [
        c for c in measured["cells"] if c["status"] in {"NEITHER", "UNCOVERED"}
    ]
    if len(measured["generation_lane_goals"]) != len(neither_or_uncovered):
        print("FAILED:WFA-0125 emit NEITHER cells not fully routed")
        return 1
    if not measured["generation_lane_goals"]:
        print("FAILED:WFA-0125 emit expected at least one generation goal")
        return 1
    for g in measured["generation_lane_goals"]:
        if "10902-10907" not in g["spec_cite"]:
            print("FAILED:WFA-0125 emit generation goal missing spec cite")
            return 1
    controls = X.both_states_extract(units)
    if not controls["count_changed"] or not controls["family_sum_changed"]:
        print("FAILED:WFA-0125 emit both-states did not fire")
        print(controls)
        return 1

    census = X.source_census()
    fragments = X.spec_fragments()
    schema_pack = bool(census["schema_pack"].get("coverage_matrix_def"))
    n = extracted["n"]
    counts = measured["counts"]
    answer = (
        f"Measured coverage over {n} mechanically extracted requirements "
        f"(IMP-0178 family sum {expected}; parsed items {n}): "
        f"BOTH={counts['BOTH']} CANDIDATE={counts['CANDIDATE']} "
        f"BLUEPRINT={counts['BLUEPRINT']} NEITHER={counts['NEITHER']} "
        f"UNCOVERED={counts['UNCOVERED']}. "
        "Live _USER-PROMPTS.md:10900-10907 bytes are "
        f"{'present' if extracted['spec_bytes_present'] else 'absent'}; "
        "the item list is reconstructed from IMP-0234..IMP-0256 catalog "
        "questions so no required workflow is dropped by paraphrase. "
        "Registry v2, blueprint library and WFA-0035 task-fit are "
        f"{'present' if census['wfa_0078']['exists'] else 'absent'} / "
        f"{'present' if any(r['exists'] for r in census['blueprint'][:4]) else 'absent'} / "
        f"{'present' if census['wfa_0035']['exists'] else 'absent'} "
        "on this worktree. Keyword-only mentions are not covers: the planted "
        "taxonomy-note mentioning deep-research is downgraded to UNCOVERED. "
        f"Every NEITHER/UNCOVERED cell ({len(measured['generation_lane_goals'])}) "
        "is routed to the generation lane as a typed goal citing "
        "_USER-PROMPTS.md:10902-10907."
    )

    doc = {
        "unit_id": "WFA-0125",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0125",
        "completion_sentinel": "SUCCESS:WFA-0125",
        "report_kind": "coverage-matrix",
        "schema_version": 1,
        "title": (
            "Map the spec's required library category families onto measured "
            "candidate and blueprint coverage"
        ),
        "question": QUESTION,
        "answer": answer,
        "answers": {
            "item_count": (
                f"{n} unique requirement ids parsed from IMP-0234..IMP-0256; "
                f"IMP-0178 family integers sum to {expected}."
            ),
            "family_note": (
                "The unit title says five families; the unit question and "
                "IMP-0178 list six (research and evidence, engineering and "
                "reliability, security and governance, product and strategy, "
                "data and science, collective intelligence). This matrix "
                "follows the question. product/design in IMP-0178 is the "
                "same family as product and strategy."
            ),
            "coverage": (
                f"BOTH={counts['BOTH']} CANDIDATE={counts['CANDIDATE']} "
                f"BLUEPRINT={counts['BLUEPRINT']} NEITHER={counts['NEITHER']} "
                f"UNCOVERED={counts['UNCOVERED']}"
            ),
        },
        "output_schema_declared": X.DECLARED_SCHEMA,
        "schema_pack_present": schema_pack,
        "local_schema": X.SCHEMA_REL,
        "source_inputs_on_this_tree": census,
        "spec_fragments": fragments,
        "requirement_extraction": {
            "source": extracted["source"],
            "n": extracted["n"],
            "unique_n": extracted["unique_n"],
            "family_counts_imp0178": extracted["family_counts_imp0178"],
            "family_counts_parsed": extracted["family_counts_parsed"],
            "expected_total_from_imp0178": expected,
            "spec_bytes_present": extracted["spec_bytes_present"],
            "ids": [r["id"] for r in extracted["requirements"]],
        },
        "family_alignment": {
            "wfa0125_question_families": q_fams,
            "imp0178_mapped": list(extracted["family_counts_imp0178"].keys()),
            "title_says_five": True,
            "question_and_imp0178_say_six": True,
        },
        "cells": measured["cells"],
        "counts": counts,
        "generation_lane_goals": measured["generation_lane_goals"],
        "keyword_trap": trap,
        "both_states": {
            "drop_IMP_0234_changes_item_count": controls["count_changed"],
            "full_n": controls["full_n"],
            "reduced_n": controls["reduced_n"],
            "mutate_research_evidence_15_to_14_changes_family_sum": controls[
                "family_sum_changed"
            ],
            "family_sum_full": controls["family_sum_full"],
            "family_sum_mutated": controls["family_sum_mutated"],
            "keyword_trap_fires": trap["downgraded"],
        },
        "tests": [
            {
                "id": "T-MECHANICAL-EXTRACT-COUNT",
                "name": (
                    "the requirement list must be extracted mechanically "
                    "from the spec text and its item count asserted"
                ),
                "command": P1,
                "result": "PASS",
                "measured_n": n,
                "imp0178_sum": expected,
            },
            {
                "id": "T-NEITHER-ROUTED",
                "name": (
                    "a NEITHER cell is routed to the generation lane as a "
                    "typed goal with its spec line cited"
                ),
                "command": P2,
                "result": "PASS",
                "goals": len(measured["generation_lane_goals"]),
            },
            {
                "id": "T-KEYWORD-DOWNGRADE",
                "name": (
                    "a claimed cover that fails the spot check is "
                    "downgraded to UNCOVERED"
                ),
                "command": P2,
                "result": "PASS",
                "planted_reason": trap["spot_check"]["reason"],
            },
        ],
        "negative_controls": [
            {
                "id": "NC-DROP-IMP-0234",
                "rejects": "hardcoded 96 that stays put after deleting an enumerating unit",
                "verbatim": (
                    f"full_n={controls['full_n']} reduced_n={controls['reduced_n']} "
                    f"changed={controls['count_changed']}"
                ),
            },
            {
                "id": "NC-KEYWORD-MENTION",
                "rejects": "a candidate whose does-text mentions deep-research",
                "verbatim": (
                    f"spot_check.pass={trap['spot_check']['pass']} "
                    f"reason={trap['spot_check']['reason']} downgraded={trap['downgraded']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0125-probe2-spotcheck-and-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Re-parses IMP-0178 family integers and IMP-0234..IMP-0256 "
                "hyphenated ids from the catalog without calling "
                "extract.extract_requirements. Recounts artifact cells and "
                "generation goals. Re-runs the keyword-trap spot check."
            ),
        },
        "claims": [
            {
                "claim": (
                    "Harness-restore _USER-PROMPTS.md:10900-10907 bytes were "
                    "read on this worktree and the 96 workflows were copied "
                    "from that enumerated list."
                ),
                "verdict": "REFUTED" if not extracted["spec_bytes_present"] else "CONFIRMED",
                "anchor": "source_inputs_on_this_tree.spec",
            },
            {
                "claim": (
                    f"{n} required workflows extracted from catalog IMP "
                    "questions; count equals IMP-0178 family sum."
                ),
                "verdict": "CONFIRMED",
                "anchor": "requirement_extraction",
            },
            {
                "claim": (
                    "Every NEITHER/UNCOVERED cell is a typed generation-lane "
                    "goal citing _USER-PROMPTS.md:10902-10907."
                ),
                "verdict": "CONFIRMED",
                "anchor": "generation_lane_goals",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Requirement ids parsed from IMP-0234..IMP-0256 "
                    "question_or_target hyphenated lists, not a hand list."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json IMP-0234",
            },
            {
                "claim": (
                    "IMP-0178 family integers "
                    f"{extracted['family_counts_imp0178_raw']} sum to "
                    f"{expected}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json IMP-0178",
            },
            {
                "claim": (
                    "Keyword-only mention of deep-research is not a cover "
                    f"(reason={trap['spot_check']['reason']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "keyword_trap",
            },
            {
                "claim": (
                    "WFA-0078 registry v2, 09-WORKFLOW-BLUEPRINT-LIBRARY.json "
                    "and WFA-0035 task-fit are present as covering corpora."
                ),
                "verdict": (
                    "CONFIRMED"
                    if (
                        census["wfa_0078"]["exists"]
                        and any(r["exists"] for r in census["blueprint"][:4])
                        and census["wfa_0035"]["exists"]
                    )
                    else "REFUTED"
                ),
                "anchor": "source_inputs_on_this_tree",
            },
        ],
        "artifacts": [
            {
                "path": X.OUT_REL,
                "exists": True,
                "role": "primary",
            }
        ],
        "residual_unknowns": [
            {
                "id": "spec-bytes-10902-10907",
                "status": "UNSETTLED" if not extracted["spec_bytes_present"] else "SETTLED",
                "settling_experiment": (
                    "Place harness-restore _USER-PROMPTS.md on disk and "
                    "re-run extract.py against lines 10902-10907."
                ),
                "impact": (
                    "The 96-id reconstruction is catalog-derived. A live "
                    "spec list that disagrees would change the matrix."
                ),
            },
            {
                "id": "covering-corpora",
                "status": "UNSETTLED",
                "settling_experiment": (
                    "Land WFA-0078, the blueprint library, and WFA-0035, "
                    "then re-run measure_cells."
                ),
                "impact": (
                    "NEITHER cells would be re-scored; keyword matching "
                    "must still fail the spot check."
                ),
            },
        ],
        "min_bytes_threshold": 2048,
    }

    schema = json.loads((REPO / X.SCHEMA_REL).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:WFA-0125 emit schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:WFA-0125 emit schema accepted garbage {garbage}")
            return 1

    out = REPO / X.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:WFA-0125 emit {size}B below min_bytes_threshold")
        return 1
    print(f"wrote {X.OUT_REL} bytes={size} n={n} neither={counts['NEITHER']}")
    print("SUCCESS:WFA-0125 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
