#!/usr/bin/env python3
"""Emit the CNL-0043 council design note (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import family as F  # noqa: E402
import runtime as R  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0043-executable-runtime-semantics-for-the-5-forecasting-protoco.md"
)
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/CNL-0043/council-design-note.schema.json"
)
CATALOG_SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0043/probe1_family_schedules.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0043/probe2_both_states.py"
)
QUESTION = (
    "Ranging over exactly these 5 records, named so no member can fall through "
    "a family mis-assignment (P33 prediction-tournament, P34 scenario-planning, "
    "P35 reference-class-planning-poker, P36 calibration-tournament, P37 "
    "pairwise-comparison): For each of the 5 FORECASTING protocol records, what "
    "is the resolution criterion and the scoring rule, and which forecasts in "
    "the catalogue are unresolvable as written?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    cen = F.census()
    if not cen["ok"]:
        print("FAILED:CNL-0043 emit census", cen["disagreements"])
        return 1
    table = R.family_schedule_table("FORECASTING")
    if table["n"] != 5 or table["not_executable"]:
        print("FAILED:CNL-0043 emit schedules", table)
        return 1
    bs = R.both_states()
    fam_bs = R.family_count_both_states("FORECASTING")
    if not bs["pass"] or not fam_bs["pass"]:
        print("FAILED:CNL-0043 emit both-states")
        return 1
    classified = R.classify_forecasts()
    recs = [r for r in R.load_protocols() if r.get("family") == "FORECASTING"]
    by_sched = {row["id"]: row for row in table["rows"]}
    protocols = []
    for rec in recs:
        pid = rec["id"]
        protocols.append(
            {
                "id": pid,
                "slug": rec.get("slug"),
                "family": "FORECASTING",
                "record_id": pid,
                "as_written": rec.get("as_written"),
                "schedule": by_sched[pid],
                "resolution_criterion": rec["designed_resolution"]["criterion"],
                "scoring_rule": rec["designed_scoring"]["statement"],
                "scoring_id": rec["designed_scoring"]["id"],
                "turn_schedule": rec["designed_turn_schedule"],
            }
        )
    scored = [
        R.score_forecast(f)
        for f in R.load_forecasts()["forecasts"]
        if not f.get("planted_bad")
    ]
    if any(not s.get("scored") for s in scored):
        print("FAILED:CNL-0043 emit known-good scoring", scored)
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    unres_ids = classified["unresolvable_ids"]
    answer = (
        "FORECASTING family n=5 confirmed by two independent counts (catalog "
        "named-member clause and fixture family field); live "
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree so "
        "library bytes were not invented. As written (inherited DISCOVERY "
        "status, null resolution_criterion and scoring_rule on every family "
        "record) all five protocols are not executable and every attached "
        "forecast is unresolvable. This note supplies the runtime. "
        "P33 prediction-tournament: resolve by looking up observable_id at "
        "resolution_time from resolution_source into outcome_space; score Brier. "
        "P34 scenario-planning: narratives do not resolve; attached signposts "
        "resolve as P33 and score Brier; scoring the narrative is forbidden. "
        "P35 reference-class-planning-poker: resolve when item_status is "
        "completed via actual_accessor; score CRPS on the histogram; abandoned "
        "items are unresolvable, not scored as zero. "
        "P36 calibration-tournament: per-item P33 resolution; rank by mean "
        "Brier; report ECE; drop unresolvable items from both. "
        "P37 pairwise-comparison: a pair resolves from observed_choice or "
        "ground_truth_winner; score Bradley-Terry log loss; a pair with neither "
        "is unresolvable. "
        "Forecasts in the fixture catalogue that remain unresolvable after this "
        f"design: {unres_ids} (missing source, narrative-as-forecast, incomplete "
        "item, missing resolution_time, pair without ground truth or choice). "
        "SUCCESS:CNL-0043"
    )
    doc = {
        "unit_id": "CNL-0043",
        "kind": "council-design-note",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0043",
        "completion_sentinel": "SUCCESS:CNL-0043",
        "title": "Executable runtime semantics for the 5 FORECASTING protocols",
        "question": QUESTION,
        "claim_under_test": (
            "The five catalog-named FORECASTING records (P33–P37) have executable "
            "resolution criteria and scoring rules, and the fixture catalogue's "
            "unresolvable forecasts are exactly the five planted-bad records."
        ),
        "answer": answer,
        "family_census": {
            "family": "FORECASTING",
            "expected_n": 5,
            "ok": True,
            "signal1_catalog_named": cen["signal1_catalog_named"],
            "signal2_fixture": cen["signal2_fixture"],
            "signal3_live_library": cen["signal3_live_library"],
            "disagreements": [],
        },
        "protocols": protocols,
        "unresolvable_as_written": {
            "protocol_fields": {
                "ids": ["P33", "P34", "P35", "P36", "P37"],
                "all_five_lack_resolution_and_scoring": True,
                "basis": (
                    "Fixture as_written.resolution_criterion and scoring_rule are "
                    "null. R-A09 catalogue evidence records status "
                    "'DISCOVERY - no protocol here has been executed' for the "
                    "inherited 58 protocol records. Live library file absent; this "
                    "is not a claim that those bytes were read."
                ),
            },
            "forecast_ids": unres_ids,
            "forecast_count": classified["unresolvable_count"],
            "resolvable_after_this_design": classified["resolvable_ids"],
            "issues_by_id": {
                r["id"]: r["issues"]
                for r in classified["rows"]
                if not r["resolvable"]
            },
        },
        "scored_known_good": scored,
        "both_states": {
            "resolvability": {
                "silent_on_good": bs["silent_on_good"],
                "fires_on_bad": bs["fires_on_bad"],
                "good_ids": bs["good"]["resolvable_ids"],
                "bad_ids": bs["bad"]["unresolvable_ids"],
            },
            "family_misassignment": {
                "silent_on_good": fam_bs["silent_on_good"],
                "fires_on_bad": fam_bs["fires_on_bad"],
                "flipped_id": fam_bs["flipped_id"],
                "good_n": fam_bs["good_n"],
                "bad_n": fam_bs["bad_n"],
            },
        },
        "evidence": [
            {
                "anchor": cen["signal1_catalog_named"]["anchor"],
                "mechanism": "regex P-id extraction from catalog question_or_target",
                "snippet": cen["signal1_catalog_named"]["snippet"],
                "claim": "Catalog question names P33–P37 so family membership cannot fall through a mis-assignment.",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": cen["signal2_fixture"]["path"],
                "mechanism": "count records where family==FORECASTING; compare id set to catalog named set",
                "claim": "Fixture FORECASTING count is 5 and the id set equals the catalog named set; a GENERATIVE distractor is present so counting all records would not equal 5.",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": cen["r_a09_discovery_anchor"],
                "mechanism": "read R-A09 evidence field; do not invent library bytes",
                "snippet": cen["r_a09_discovery_snippet"],
                "claim": "Inherited catalogue status is DISCOVERY; as-written resolution_criterion and scoring_rule are therefore treated as null, not as fields we pretended to read from an absent file.",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/CNL-0043/runtime.py",
                "mechanism": "forecast_issues() + score_forecast() on fixtures",
                "claim": "Resolvability check is silent on five known-good forecasts and fires on five planted-bad forecasts; scoring actually returns numeric Brier/CRPS/log-loss on the known-good set.",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/ARC-0003/samples.json",
                "mechanism": "Path.is_file on library candidates plus prior ARC sample on_this_tree=false",
                "claim": "Library file 12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from disk on this worktree.",
                "verdict": "REFUTED",
                "snippet": "on_this_tree: false",
            },
        ],
        "tests": [
            {
                "id": "T1-family-schedules",
                "name": "Every FORECASTING record has an executable turn schedule; count equals family n",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-both-states-unresolvable",
                "name": "Resolvability FIRES on planted-bad and is SILENT on known-good; independent recount agrees",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-planted-unresolvable-forecasts",
                "on_state": (
                    "planted-bad forecast fixture (missing source/time, narrative "
                    "as forecast, incomplete item, pair without ground truth)"
                ),
                "observed": bs["negative_control"],
            },
            {
                "id": "NC-family-misassignment",
                "on_state": "FORECASTING member relabelled so it falls out of the family count",
                "observed": fam_bs["negative_control"],
            },
        ],
        "strongest_surviving_counterargument": (
            "The five named P-ids come from the work-unit question, not from a "
            "live read of 12-COUNCIL-PROTOCOLS-AND-PRESETS.json. If that file is "
            "later placed on disk and its FORECASTING set differs from "
            "{P33,P34,P35,P36,P37}, signal 3 must fail closed and this note must "
            "be rewritten from those bytes. Until then, refusing to invent library "
            "records is the honest move; the catalog anti-misassignment clause is "
            "the membership list this unit is allowed to range over."
        ),
        "reviewer": {
            "reviewer_id": "CNL-0043-probe2-retabulation",
            "verdict": "PASS",
            "independent": True,
            "control_executed": True,
            "scope_not_agreement": True,
            "method": (
                "Mechanical: regex-extract P-ids from catalog question_or_target; "
                "count fixture records with family==FORECASTING; apply "
                "runtime.forecast_issues to the forecast fixture without reading "
                "the author's answer string. Disagreement in either number blocks. "
                "Both-states: SILENT on known-good, FIRES on planted-bad, recorded "
                "verbatim in probe2-both-states.raw.json."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "family-census-and-schedules", "command": P1},
            {"id": "probe2", "role": "both-states-resolvability", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0043/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "timestamps": {"ended_at": now},
        "min_bytes_threshold": 8000,
        "cloud_ok": False,
        "adv_rebuild_circle": False,
        "required_fix": None,
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from this worktree",
            "the five protocols have been executed outside this fixture runtime",
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "supporting"},
            {"path": CATALOG_SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0043/fixtures/protocols.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0043/fixtures/forecasts.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "schema_note": (
            "Catalog output_schema is a GENERATED SHIM whose $ref points at "
            "https://ast-integrate.invalid/...; validating against it tries the "
            "network and does not constrain this note. This unit validates "
            "against the per-unit schema. Overwriting the shared catalog schema "
            "would be a sibling rebuild circle."
        ),
    }

    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0043 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:CNL-0043 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0043 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0043 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
