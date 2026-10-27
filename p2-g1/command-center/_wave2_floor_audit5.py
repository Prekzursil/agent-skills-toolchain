#!/usr/bin/env python
"""Pass 5: correct the two pass-4 sub-detectors that were WRONG, and stamp the final verdicts.

Pass-4 detector failures, recorded not deleted:
  * `completion_sentinel_not_naming_own_unit` returned 0 by checking `id in sentinel`.
    The shipped rule SEM-002 (semantics.py:85-99) requires the LITERAL `SUCCESS:<own-id>`.
    Mine was WEAKER, so its 0 was not a refutation of SEM-002's 96 -- it measured a different,
    easier question. Correct answer: 96.
  * `assigned_model_vendor_role` polarity was INVERTED. work-unit.schema.json says the OBJECT
    form is canonical (1,879 units) and the slash-triple STRING form (128) is the odd one.
    Pass 4 called the 1,879 object-form units non-canonical. Correct answer: 128.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
CC = REPO / "command-center"
sys.path.insert(0, str(CC))
from _wave2_floor_audit import load_json_safe  # noqa: E402

OUT = CC / "WAVE2-FLOOR-AUDIT.json"


def main() -> int:
    prev, e = load_json_safe(OUT)
    if e:
        print("cannot read:", e)
        return 1
    doc, e2 = load_json_safe(CC / "WORK-UNIT-CATALOG.json")
    units = doc["work_units"]

    obj = sum(1 for x in units if isinstance(x.get("assigned_model_vendor_role"), dict))
    stri = sum(1 for x in units if isinstance(x.get("assigned_model_vendor_role"), str))
    sem002 = [
        x["id"]
        for x in units
        if f"SUCCESS:{x.get('id')}" not in str(x.get("completion_sentinel", ""))
    ]

    c7 = prev["check7_catalog_defect_deltas"]
    c7["CORRECTED"] = {
        "completion_sentinel_not_naming_own_unit": len(sem002),
        "completion_sentinel_rule": "SEM-002 (platform/lib/wfdsl/semantics.py:85-99) requires the LITERAL 'SUCCESS:<own-id>' substring",
        "completion_sentinel_sample_actual": [
            str(next(y for y in units if y["id"] == i).get("completion_sentinel"))[:70]
            for i in sem002[:3]
        ],
        "assigned_model_vendor_role_object_form_CANONICAL": obj,
        "assigned_model_vendor_role_string_triple_NONCANONICAL": stri,
        "canonicality_source": "platform/schema/work-unit.schema.json $comment on assigned_model_vendor_role: object form (1,879) canonical; slash-triple string (128) accepted here, strict profile requires the object",
    }
    c7["PASS4_DETECTOR_FAILURES_RECORDED"] = [
        "completion_sentinel check used `id in sentinel` (weaker than SEM-002) and returned 0; SEM-002's 96 is correct",
        "assigned_model_vendor_role polarity inverted: pass 4 called the 1,879 canonical object-form units non-canonical",
    ]

    prev["pass"] = 5
    prev["generated_at_utc"] = _dt.datetime.now(_dt.UTC).isoformat()

    prev["VERDICTS"] = {
        "floor_1_blueprints_ge_96": {
            "floor": 96,
            "measured_top_level_blueprints": prev["check1b_distinctness_real_set"]["blueprints_top_level"],
            "measured_all_blueprint_shaped_docs": prev["check1_blueprints"]["blueprint_docs"],
            "schema_valid": f"{prev['check1_blueprints']['schema_valid']}/{prev['check1_blueprints']['blueprint_docs']}",
            "semantic_violation_files": prev["check1_blueprints"]["semantic_violation_files"],
            "materially_distinct": prev["check1b_distinctness_real_set"]["materially_distinct_count"],
            "verdict": "MET",
            "caveat": "distinctness is CARRIED BY ONE AXIS: stages 97/97 distinct, but roles only 32 distinct, gates 43, and stopping_rules just 2 across all 97. 5 pairs are identical on 3 of the 4 axes.",
        },
        "floor_2_flagship_ge_40": {
            "floor": 40,
            "measured": prev["check2_flagship_mapping"]["flagship_declared"],
            "with_dedicated_test": prev["check2_flagship_mapping"]["strict_exact_filename_match"]
            + prev["check2_flagship_mapping"]["relaxed_prefix_match_only"],
            "pytest": prev["check2b_flagship_pytest"]["last_line"],
            "verdict": "MET",
        },
        "floor_3_architecture_9_plus_verdict": {
            "architectures": prev["check3_architecture"]["architecture_md_count"],
            "tournament_verdict": prev["check3_architecture"]["tournament_verdict_present"],
            "minority_report": True,
            "verdict": "MET",
            "basis": "TOURNAMENT-VERDICT.md:219 '## 4. MINORITY REPORT', 10 x 'dissent', named dissents M1-M5 carried into the G2/G7/G9/G10 gate rows. Dissent was NOT dropped.",
        },
        "floor_4_scout_forge_executable": {
            "scout_ran": True,
            "forge_ran": True,
            "forge_can_REJECT": True,
            "forge_can_CERTIFY": True,
            "verdict": "MET",
            "basis": "union strategy -> 'VERDICT: REJECTED / gratuitous-cost: 9 grafted stage(s) change NO axis'; tournament -> 5 of 7 strategies CERTIFIED. Both states proven, so it is neither a no-op gate nor an always-reject gate.",
        },
        "floor_5_substrate": {
            "cc_schema_dir_exists": prev["check5_substrate"]["cc_schema_dir_exists"],
            "cc_schema_files": prev["check5_substrate"]["cc_schema_file_count"],
            "cc_schema_tokens_resolving": f"{prev['check5b_substrate_reconcile']['cc_schema_tokens_resolving']}/{prev['check5b_substrate_reconcile']['cc_schema_distinct_tokens']}",
            "all_path_tokens_resolving": f"{prev['check5_substrate']['tokens_resolving_on_disk']}/{prev['check5_substrate']['distinct_path_TOKENS_extracted']}",
            "unresolved_tokens": prev["check5_substrate"]["tokens_NOT_resolving"],
            "verdict": "PARTIAL",
            "basis": "the command-center/schema/ namespace is FULLY closed (233/233 tokens, 1,859 refs). 36 tokens remain unresolved -- all under tools/marketplace/schema/ (20), tools/plugin/schema/ (14) and .claude-plugin/ (2); neither tools/marketplace nor tools/plugin exists as a directory.",
        },
        "floor_6_no_test_regression": {
            "wave1_baseline_rerun": "444 passed in 77.90s",
            "full_suite": "2767 passed, 14 skipped in 135.48s",
            "failures": 0,
            "verdict": "MET - ZERO REGRESSION",
            "basis": "the exact Wave-1 module set (wfdsl 97 + councilspec 112 + council_protocols 111 + completion_predicate 65 + receipt_schema_gate 59) re-runs at exactly 444 passed / 0 failed.",
        },
    }
    prev["OPEN_DEFECTS"] = [
        {
            "severity": "P1",
            "id": "WAVE2-UNCOMMITTED",
            "claim": "ZERO of Wave 2's deliverables are git-tracked: 612 files across platform/workflows (129), platform/architecture (103), platform/lib/workflows (134), platform/lib/foundry (13), command-center/schema (233) all report git_tracked=0.",
            "consequence": "a git clean -xfd, a checkout, or a worktree reset destroys the whole wave. Wave 1 is committed; Wave 2 exists only in the working tree.",
            "evidence": "git ls-files <dir> returns 0 lines for each; repo-wide git status --porcelain -uall = 618 entries; HEAD = main edcf9f5b",
        },
        {
            "severity": "P2",
            "id": "FORGED-ID-COLLISION",
            "claim": "three files in platform/workflows/forged/ carry the identical id fused.dc5b5f0b10f7 - the certified 9-stage fusion, the tournament winner (9 stages) and the REJECTED 18-stage union.",
            "consequence": "a loader keyed on workflow id cannot distinguish the REJECTED artifact from the CERTIFIED one.",
            "evidence": "check9_forged_id_collision.colliding_ids",
        },
        {
            "severity": "P2",
            "id": "STOPPING-RULE-BOILERPLATE",
            "claim": "stopping_rules take only 2 distinct normalised values across all 97 blueprints (clusters of 55 and 42), so the spec's 'distinct by stopping rule' axis contributes almost no discrimination.",
            "consequence": "the 97/97 materially-distinct figure rests on stage topology alone; roles (32 distinct) and gates (43) also cluster heavily.",
            "evidence": "check1b_distinctness_real_set.per_axis.stopping",
        },
        {
            "severity": "P3",
            "id": "FORGE-COST-LABEL",
            "claim": "forge fuse prints 'cost (NOT an axis): {stage_count: 8}' which is cost_delta_vs_largest_source, while the fused document actually has 18 stages.",
            "consequence": "an unlabelled delta reads as an absolute; a reader can conclude the union shrank the workflow when it grew it by 8 stages.",
            "evidence": "console output of forge fuse --strategy union vs certification.fused.cost.stage_count=18 in the report JSON",
        },
        {
            "severity": "INFO",
            "id": "CATALOG-DEFECTS-UNMOVED",
            "claim": "four of the five pinned catalog defects are unchanged: output_schema pattern failures 159 -> 159, unresolvable dependency refs 41 -> 41, completion sentinels not naming own unit 96 -> 96, non-canonical assigned_model_vendor_role 128 -> 128. Profiles unchanged: structural 2007/2007, normative 1790/2007, strict 1679/2007.",
            "consequence": "Wave 2 closed the schema-substrate P1 but did not touch the catalog conformance defects.",
            "evidence": "check7_catalog_defect_deltas + platform/lib/wfdsl/validate.py catalog output",
        },
    ]
    OUT.write_text(json.dumps(prev, indent=1), encoding="utf-8")
    print(json.dumps(prev["VERDICTS"], indent=1))
    print("\nOPEN DEFECTS:", len(prev["OPEN_DEFECTS"]))
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
