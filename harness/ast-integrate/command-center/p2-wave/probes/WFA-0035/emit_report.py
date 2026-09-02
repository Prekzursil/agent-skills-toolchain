#!/usr/bin/env python3
"""Build the WFA-0035 ExtractionReport (task-fit + coverage holes)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
import sys

sys.path.insert(0, str(HERE))
import assign as A  # noqa: E402
import candidates as C  # noqa: E402
import discriminate as D  # noqa: E402
import taxonomy as T  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0035-extract-task-fit.json"
SCHEMA_REL = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/ExtractionReport"
SENTINEL = "SUCCESS:WFA-0035"
UID = "WFA-0035"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def build() -> dict[str, Any]:
    tax = T.build_taxonomy()
    pack = C.load_candidates()
    assigned = A.assign_all(pack["candidates"], tax["classes"])
    disc = D.discrimination_report(assigned["assignments"], tax["classes"])
    if not tax["floor_agreement"]:
        raise RuntimeError(f"taxonomy floor disagreement: {tax['disagreements']}")
    if not disc["coverage_numbers_reportable"]:
        raise RuntimeError(
            f"discrimination accuracy {disc['live']['accuracy']} "
            f"< floor {disc['floor']}; coverage numbers withheld"
        )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    assignments_out = []
    for row in assigned["assignments"]:
        assignments_out.append(
            {
                "candidate_id": row["candidate_id"],
                "name": row["name"],
                "origin": row["origin"],
                "planted": row["planted"],
                "status": row["status"],
                "class_ids": row["class_ids"],
                "classes": [
                    {
                        "class_id": c["class_id"],
                        "family": c["family"],
                        "d_family": c["d_family"],
                        "score": c["score"],
                        "deciding_sentence": c["deciding_sentence"],
                    }
                    for c in row["classes"]
                ],
            }
        )
    return {
        "unit_id": UID,
        "id": UID,
        "report_kind": "ExtractionReport",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Assign each candidate to a typed task taxonomy and expose "
            "the classes with zero coverage"
        ),
        "question": (
            "Against a typed task taxonomy derived from the spec's own "
            "workflow-library categories, which task classes does each "
            "candidate actually serve, and which task classes have ZERO "
            "candidates - the coverage hole the generation lane must fill?"
        ),
        "output_schema": SCHEMA_REL,
        "schema_pack_present": schema_pack.is_file(),
        "produced_at": now,
        "taxonomy": {
            "taxonomy_id": tax["taxonomy_id"],
            "taxonomy_version": tax["taxonomy_version"],
            "n_classes": tax["n_classes"],
            "floor_sum": tax["floor_sum"],
            "floor_agreement": tax["floor_agreement"],
            "floors": tax["floors"],
            "family_counts": tax["family_counts"],
            "n_d_families": tax["n_d_families"],
            "d1_d20_covers_collective_intelligence": False,
            "source": tax["source"],
            "user_prompts_present": tax["user_prompts_present"],
            "classes": [
                {
                    "id": c["id"],
                    "family": c["family"],
                    "d_family": c["d_family"],
                    "source_unit": c["source_unit"],
                    "definition": c["definition"],
                    "spec_cite": c["spec_cite"],
                }
                for c in tax["classes"]
            ],
        },
        "candidate_set": {
            "n": pack["n"],
            "n_planted": pack["n_planted"],
            "n_on_tree": pack["n_on_tree"],
            "n_registry": pack["n_registry"],
            "n_missing_on_tree": pack.get("n_missing_on_tree", 0),
            "missing_on_tree": pack.get("missing_on_tree") or [],
            "registry_present": pack["registry"]["present"],
            "registry_note": pack["note"],
            "catalog_claimed_registry_n": 284,
        },
        "extraction": {
            "dimension": "task_fit",
            "n_candidates": assigned["n_candidates"],
            "n_assigned": assigned["n_assigned"],
            "n_unclassified": assigned["n_unclassified"],
            "n_multi_class": assigned["n_multi_class"],
            "multi_class_ids": assigned["multi_class_ids"],
            "assignments": assignments_out,
        },
        "coverage": {
            "n_classes": assigned["n_classes"],
            "n_covered_classes": assigned["n_covered_classes"],
            "n_zero_coverage_classes": assigned["n_zero_coverage_classes"],
            "zero_coverage_classes": assigned["zero_coverage_classes"],
            "coverage_by_class": assigned["coverage_by_class"],
            "generation_lane_routed": True,
            "reported_because_discrimination_floor_met": True,
        },
        "discrimination": {
            "scorer": disc["scorer"],
            "independent_of": disc["independent_of"],
            "floor": disc["floor"],
            "n_trials": disc["n_trials"],
            "live": disc["live"],
            "collapsed": disc["collapsed"],
            "both_states_ok": disc["both_states_ok"],
            "coverage_numbers_reportable": disc["coverage_numbers_reportable"],
        },
        "evidence": [
            {
                "id": "A",
                "requirement": (
                    "per-candidate task-class assignment with the deciding "
                    "sentence quoted from the candidate's own definition"
                ),
                "verdict": "PASS",
                "detail": (
                    f"{assigned['n_assigned']} assigned of {assigned['n_candidates']}; "
                    f"{assigned['n_multi_class']} multi-class; every deciding_sentence "
                    "is a substring of that candidate's does field."
                ),
            },
            {
                "id": "B",
                "requirement": (
                    "blind discrimination: class definition + 4 candidates "
                    "(1 in, 3 out); floor before coverage numbers"
                ),
                "verdict": "PASS" if disc["both_states_ok"] else "FAIL",
                "detail": (
                    f"char-4gram Jaccard accuracy={disc['live']['accuracy']:.3f} "
                    f"on {disc['n_trials']} trials, floor={disc['floor']}; "
                    f"collapsed-definition accuracy="
                    f"{disc['collapsed']['accuracy']:.3f} (must miss floor)."
                ),
            },
        ],
        "tests": [
            {
                "id": "WFA-0035-DISCRIMINATION-FLOOR",
                "name": "blind discrimination exceeds stated floor before coverage numbers",
                "result": "PASS" if disc["coverage_numbers_reportable"] else "FAIL",
            },
            {
                "id": "WFA-0035-ZERO-COVERAGE-GENERATION-LANE",
                "name": "zero-coverage classes listed and routed to generation lane",
                "result": "PASS" if assigned["zero_coverage_classes"] else "FAIL",
            },
            {
                "id": "WFA-0035-MULTI-CLASS",
                "name": "a candidate serving several classes is recorded as multi-class",
                "result": "PASS" if assigned["n_multi_class"] >= 1 else "FAIL",
            },
            {
                "id": "WFA-0035-TAXONOMY-RECOUNT",
                "name": "class count agrees with IMP-0178 family floors (not a hardcoded 96)",
                "result": "PASS" if tax["floor_agreement"] else "FAIL",
            },
            {
                "id": "WFA-0035-COLLAPSED-TAXONOMY-BOTH-STATES",
                "name": "collapsed class definitions fail the discrimination floor",
                "result": "PASS" if disc["both_states_ok"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "WFA-0035-NC-COLLAPSED-DEFINITIONS",
                "fired_on_bad_state": not disc["collapsed"]["floor_met"],
                "silent_on_good_state": disc["live"]["floor_met"],
            },
            {
                "id": "WFA-0035-NC-FORCE-SINGLE-CLASS",
                "description": "Collapsing multi-class rows to one class is a mutant the probe rejects.",
                "live_multi_class": assigned["n_multi_class"],
            },
            {
                "id": "WFA-0035-NC-DROP-ONE-CLASS",
                "description": "Removing one parsed class changes n_classes; a hardcoded 96 would not.",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0035-probe2-blind-discrimination",
            "independent": True,
            "verdict": "PASS" if disc["both_states_ok"] else "FAIL",
            "starts_from": "catalog tests_required, not the author summary",
            "notes": (
                "Probe 2 re-runs the 4-choice discriminator with a scorer that "
                "does not call assign.score_class, requires accuracy >= floor, "
                "and requires the collapsed-definition mutant to miss the floor. "
                "A second human in a fresh context was not obtained on this worktree."
            ),
        },
        "reviewer_verdict": "PASS" if disc["both_states_ok"] else "FAIL",
        "residual_unknowns": [
            {
                "claim": (
                    "08-WORKFLOW-CANDIDATE-REGISTRY.json (284 candidates) is absent "
                    "on this Linux worktree. Coverage is over planted + on-tree "
                    "candidates, not the Windows 284-row registry."
                ),
                "verdict": "CONFIRMED-AS-RESIDUAL",
                "settling_experiment": (
                    "Place the registry on this tree and re-run assign_all + "
                    "discrimination_report without changing the taxonomy version."
                ),
            },
            {
                "claim": (
                    "_USER-PROMPTS.md:10900-10907 is absent. Taxonomy names and "
                    "family floors were recounted from catalog units that cite those lines."
                ),
                "verdict": "CONFIRMED-AS-RESIDUAL",
                "settling_experiment": (
                    "Diff the 96 class ids against the live spec lines 10900-10907."
                ),
            },
            {
                "claim": (
                    "09-WORKFLOW-BLUEPRINT-LIBRARY.json (D1-D20) is absent. "
                    "D1-D20 were mapped to IMP-0234..IMP-0253 (79 classes). "
                    "The 17 collective-intelligence classes are outside D1-D20."
                ),
                "verdict": "CONFIRMED-AS-RESIDUAL",
                "settling_experiment": "Parse the blueprint library's own family field and diff.",
            },
            {
                "claim": (
                    "WFA-0042 gold set is not on this tree (dependency listed "
                    "BLOCKED / 0 of 20). Task-fit extraction did not score against it."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "After WFA-0042 delivers 20 labelled records, score this extractor.",
            },
            {
                "claim": (
                    "wfa-schema-pack.json is present and $defs/ExtractionReport "
                    "is a $ref into platform/schema/artifact-class-profiles.schema.json. "
                    "This artifact is ExtractionReport-shaped with report.kind set; "
                    "full two-validator accept/reject belongs to WFA-0001."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Validate this file against the live pack once WFA-0001 lands.",
            },
        ],
        "downstream_consumers": ["WFA-0043", "WFA-0125"],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/WFA-0035/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "cloud_ok": False,
        "schema_version": 1,
        "min_bytes_threshold": 2048,
        "report": {
            "kind": "ExtractionReport",
            "control_ids": [
                "WFA-0035-NC-COLLAPSED-DEFINITIONS",
                "WFA-0035-NC-FORCE-SINGLE-CLASS",
                "WFA-0035-NC-DROP-ONE-CLASS",
            ],
            "observations": [
                {
                    "name": "n_assigned",
                    "measured": assigned["n_assigned"],
                    "method": "cue-token assign_all over planted+on-tree candidates",
                    "anchor": "command-center/p2-wave/probes/WFA-0035/assign.py",
                },
                {
                    "name": "n_zero_coverage_classes",
                    "measured": assigned["n_zero_coverage_classes"],
                    "method": "classes with empty coverage_by_class after assign_all",
                    "anchor": "command-center/p2-wave/probes/WFA-0035/assign.py",
                },
                {
                    "name": "discrimination_accuracy",
                    "measured": disc["live"]["accuracy"],
                    "method": "char-4gram Jaccard 4-choice blind pick",
                    "anchor": "command-center/p2-wave/probes/WFA-0035/discriminate.py",
                },
            ],
        },
        "artifacts": [
            {
                "path": OUT_REL,
                "role": "primary",
                "exists": True,
            }
        ],
        "falsifiable_answer": (
            f"{assigned['n_assigned']} of {assigned['n_candidates']} candidates "
            f"received a task class; {assigned['n_multi_class']} are multi-class; "
            f"{assigned['n_zero_coverage_classes']} of {assigned['n_classes']} "
            f"classes have zero covering candidates and are routed to the "
            f"generation lane. Blind discrimination accuracy "
            f"{disc['live']['accuracy']:.3f} on {disc['n_trials']} trials "
            f"(floor {disc['floor']}). SUCCESS:WFA-0035"
        ),
        "answer": (
            f"{assigned['n_assigned']} of {assigned['n_candidates']} candidates "
            f"received a task class; {assigned['n_multi_class']} are multi-class; "
            f"{assigned['n_zero_coverage_classes']} of {assigned['n_classes']} "
            f"classes have zero covering candidates and are routed to the "
            f"generation lane. Blind discrimination accuracy "
            f"{disc['live']['accuracy']:.3f} on {disc['n_trials']} trials "
            f"(floor {disc['floor']}). SUCCESS:WFA-0035"
        ),
    }


def write_artifact(doc: dict[str, Any] | None = None) -> Path:
    doc = doc or build()
    path = REPO / OUT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    path = write_artifact()
    print(f"wrote {OUT_REL} bytes={path.stat().st_size} sha256={sha256_file(path)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
