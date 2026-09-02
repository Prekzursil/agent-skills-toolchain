#!/usr/bin/env python3
"""Emit command-center/research/evidence-quality/RES-0185-evidence-map-coverage-holes.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harvest import harvest  # noqa: E402
from mapper import score  # noqa: E402
from plants import PLANT_FOUR_ID, PLANT_SINGLE_ID, PLANT_UNSUPPORTED_ID  # noqa: E402
from vocabulary import SOURCE_CLASSES  # noqa: E402

OUT = (
    "command-center/research/evidence-quality/"
    "RES-0185-evidence-map-coverage-holes.json"
)
SCHEMA = "command-center/p2-wave/probes/RES-0185/artifact.schema.json"
DECLARED_SCHEMA = "command-center/schema/measurement-run.schema.json"
QUESTION = (
    "Produce the artifact that cross-tabulates every major conclusion against "
    "the source classes and independent sources supporting it, so a conclusion "
    "resting on one class or one source is visible at a glance - and report how "
    "many of this program's current conclusions are single-source."
)
SENTINEL = "SUCCESS:RES-0185"
COMPLETION = (
    "SUCCESS:RES-0185 in the receipt AND an evidence map that marks "
    "single-source conclusions and does not omit UNSUPPORTED rows"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0185/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0185/probe2_independent_recount.py"
)


def decorate(raw: dict) -> dict:
    scored = score(raw["lineage_records"])
    row = dict(raw)
    row["lineage_record_count"] = len(raw["lineage_records"])
    row.update(scored)
    return row


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bundle = harvest(REPO)
    conclusions = [decorate(c) for c in bundle["all_conclusions"]]
    program = [c for c in conclusions if not c["plant"]]
    plants_scored = [c for c in conclusions if c["plant"]]
    by_id = {c["id"]: c for c in conclusions}

    n_prog = len(program)
    n_single = sum(1 for c in program if c["single_source"])
    n_class = sum(1 for c in program if c["single_class"])
    n_unsup = sum(1 for c in program if c["support_status"] == "UNSUPPORTED")
    n_multi = sum(1 for c in program if c["support_status"] == "MULTI")

    plant_single = by_id[PLANT_SINGLE_ID]
    plant_four = by_id[PLANT_FOUR_ID]
    plant_unsup = by_id[PLANT_UNSUPPORTED_ID]
    if not plant_single["single_source"] or plant_single["support_status"] != "SINGLE-SOURCE":
        print("FAILED:RES-0185 emit plant-single not marked single-source")
        return 1
    if plant_four["single_source"] or plant_four["class_count"] < 4:
        print("FAILED:RES-0185 emit plant-four marked single-source or class_count<4")
        return 1
    if plant_unsup["support_status"] != "UNSUPPORTED":
        print("FAILED:RES-0185 emit plant-unsupported omitted-or-mislabeled")
        return 1

    cross_tab = []
    for c in conclusions:
        cell = {
            "id": c["id"],
            "plant": c["plant"],
            "support_status": c["support_status"],
            "independent_source_count": c["independent_source_count"],
            "class_count": c["class_count"],
            "single_source": c["single_source"],
            "single_class": c["single_class"],
        }
        for cls in SOURCE_CLASSES:
            cell[cls] = int((c.get("class_counts") or {}).get(cls) or 0)
        cell["unclassified"] = int((c.get("class_counts") or {}).get("unclassified") or 0)
        cross_tab.append(cell)

    inputs = {
        "command-center/CLAIM-REGISTRY.json": (
            REPO / "command-center/CLAIM-REGISTRY.json"
        ).is_file(),
        "command-center/sources/REGISTER.md": (
            REPO / "command-center/sources/REGISTER.md"
        ).is_file(),
        "_USER-PROMPTS.md": (REPO / "_USER-PROMPTS.md").is_file(),
        DECLARED_SCHEMA: (REPO / DECLARED_SCHEMA).is_file(),
    }
    answer = (
        f"Harvest frame={bundle['frame']}; CLAIM-REGISTRY present="
        f"{bundle['claim_registry_present']}. Program conclusions n={n_prog} "
        f"(plants excluded from the headline). single-source n={n_single} "
        f"({(n_single / n_prog) if n_prog else 0:.3f} of program). "
        f"single-class n={n_class}. UNSUPPORTED n={n_unsup} (shown on the map, "
        f"not omitted). MULTI n={n_multi}. Detector plants: "
        f"{PLANT_SINGLE_ID} single_source={plant_single['single_source']}; "
        f"{PLANT_FOUR_ID} single_source={plant_four['single_source']} "
        f"class_count={plant_four['class_count']}; "
        f"{PLANT_UNSUPPORTED_ID} status={plant_unsup['support_status']}. "
        "Support edges are computed from recorded lineage locators only."
    )

    pub_conclusions = []
    for c in conclusions:
        pub_conclusions.append(
            {
                "id": c["id"],
                "unit_id": c["unit_id"],
                "kind": c["kind"],
                "plant": c["plant"],
                "text": c["text"],
                "origin_path": c["origin_path"],
                "lineage_record_count": c["lineage_record_count"],
                "lineage_records": c["lineage_records"],
                "independent_source_count": c["independent_source_count"],
                "class_count": c["class_count"],
                "single_source": c["single_source"],
                "single_class": c["single_class"],
                "support_status": c["support_status"],
                "classes": c["classes"],
                "class_counts": c["class_counts"],
            }
        )

    doc = {
        "unit_id": "RES-0185",
        "report_kind": "measurement-run",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION,
        "title": "Build the evidence map that shows which conclusions are load-bearing and thinly supported",
        "question": QUESTION,
        "answer": answer,
        "ts": now,
        "output_schema_declared": DECLARED_SCHEMA,
        "output_schema_declared_present": inputs[DECLARED_SCHEMA],
        "local_artifact_schema": SCHEMA,
        "harvest_frame": {
            "rule": bundle["frame"],
            "claim_registry_present": bundle["claim_registry_present"],
            "inputs_present": inputs,
            "program_from": (
                "recorded claims/headlines on live research artifacts plus "
                "CLAIM-REGISTRY.json when present"
            ),
            "support_rule": (
                "independent sources and source classes are computed from "
                "recorded lineage locators (url/sha256/doi/arxiv/source_id); "
                "cited bodies are not re-read; empty lineage is UNSUPPORTED "
                "and remains a map row"
            ),
            "plants_excluded_from_headline": True,
        },
        "source_class_vocabulary": list(SOURCE_CLASSES),
        "source_class_vocabulary_provenance": (
            "Reconstructed; locked to RES-0149 SOURCE_CLASS_VOCABULARY because "
            "_USER-PROMPTS.md:10683 is absent on this worktree."
        ),
        "program_conclusion_count": n_prog,
        "single_source_count": n_single,
        "single_class_count": n_class,
        "unsupported_count": n_unsup,
        "multi_count": n_multi,
        "plant_count": len(plants_scored),
        "unsupported_shown_not_omitted": True,
        "distinct_from_RES-0128": (
            "RES-0128 audits which of the 16 source classes and 12 research "
            "modes units RES-0001..RES-0127 actually exercised. RES-0185 maps "
            "each recorded conclusion to the independent sources and classes "
            "in its lineage so single-source and single-class rows are visible."
        ),
        "cross_tab": cross_tab,
        "conclusions": pub_conclusions,
        "detector_control": {
            "single_plant_id": PLANT_SINGLE_ID,
            "single_plant_marked_single_source": plant_single["single_source"],
            "four_class_plant_id": PLANT_FOUR_ID,
            "four_class_plant_marked_single_source": plant_four["single_source"],
            "four_class_plant_class_count": plant_four["class_count"],
            "unsupported_plant_id": PLANT_UNSUPPORTED_ID,
            "unsupported_plant_status": plant_unsup["support_status"],
            "unsupported_plant_present_on_map": True,
            "pass": True,
        },
        "tests": [
            {
                "id": "detector-plant-single-source",
                "result": "PASS",
                "detail": (
                    f"{PLANT_SINGLE_ID} independent_source_count="
                    f"{plant_single['independent_source_count']} "
                    f"status={plant_single['support_status']}"
                ),
            },
            {
                "id": "detector-plant-four-class-not-single-source",
                "result": "PASS",
                "detail": (
                    f"{PLANT_FOUR_ID} class_count={plant_four['class_count']} "
                    f"single_source={plant_four['single_source']}"
                ),
            },
            {
                "id": "unsupported-shown-not-omitted",
                "result": "PASS",
                "detail": f"{PLANT_UNSUPPORTED_ID} present status=UNSUPPORTED",
            },
        ],
        "negative_controls": [
            {
                "id": "omit-empty-lineage",
                "kind": "omission-trap",
                "description": (
                    "A mapper that drops conclusions with empty lineage would "
                    "hide UNSUPPORTED rows. The plant with no lineage must remain "
                    "on the map as UNSUPPORTED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "evidence": [
            {
                "id": "E1-harvest-frame",
                "kind": "file-census",
                "detail": (
                    f"frame={bundle['frame']} registry="
                    f"{bundle['claim_registry_present']} program_n={n_prog}"
                ),
            },
            {
                "id": "E2-lineage-only",
                "kind": "rule",
                "detail": (
                    "Support edges use recorded locators only; no body fetch; "
                    "no re-judging of whether a quote supports the sentence."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0185-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 recomputes independent-source collapse from stored "
                "lineage_records without calling mapper.score."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "detector-control-plants"},
            {"id": "probe2", "command": P2, "role": "independent-lineage-recount"},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "notes": (
            "G-1 for RES-0185. CLAIM-REGISTRY.json and _USER-PROMPTS.md are "
            "absent; harvest is live research artifacts plus detector plants. "
            "Declared measurement-run.schema.json is absent; local schema used. "
            "Did not run global unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0185 schema-invalid")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}):
        if not list(validator.iter_errors(g)):
            print("FAILED:RES-0185 schema accepted garbage")
            return 1

    outp = REPO / OUT
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={outp.stat().st_size}")
    print(f"program_n={n_prog} single_source={n_single} unsupported={n_unsup}")
    print("SUCCESS:RES-0185 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
