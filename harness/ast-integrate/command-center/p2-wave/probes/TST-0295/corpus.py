"""Assemble the TST-0295 benchmark case corpus.

Each case is a self-contained JSON file under command-center/bench/cases/.
Oracles live in command-center/bench/oracle.py. A vacuous always-pass oracle
is assembled as a negative control and must be stripped before write.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "bench"))
sys.path.insert(0, str(HERE))

from oracle import evaluate, sanity  # noqa: E402
from seeded_classes import CLASSES, SOURCE_CITATION, SOURCE_STATUS, assert_complete  # noqa: E402

CASES_DIR = REPO / "command-center" / "bench" / "cases"
INDEX_PATH = REPO / "command-center" / "bench" / "INDEX.json"
SCHEMA_REL = "command-center/schema/bench-case.schema.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

FC_MATCH: dict[str, dict] = {
    "FC-11301": {"live_writable": True, "repo_writable": True},
    "FC-11302": {"unknown_field_present": True, "parser_accepted": True},
    "FC-11303": {"plugin_present": True, "hooks_loaded": False},
    "FC-11304": {"os": "windows", "bare_sh": True, "wrapper": False},
    "FC-11305": {"sha_repo": "aaa", "sha_live": "bbb"},
    "FC-11306": {"cache_sha": "old", "package_sha": "new"},
    "FC-11307": {"includes_dot_git": True},
    "FC-11308": {"path_a": "Rules.md", "path_b": "rules.md"},
    "FC-11309": {"original_path": "/c/proj", "rewritten_path": "C:\\proj"},
    "FC-11310": {"key_a": "Id", "key_b": "id", "folded_collision": True},
    "FC-11311": {"argv_bytes": 32768, "limit_bytes": 8191},
    "FC-11312": {"exit_code": 0, "artifact_bytes": 0},
    "FC-11313": {"artifact_bytes": 12, "sentinel": ""},
    "FC-11314": {"predicate_a": "SUCCESS", "predicate_b": "FAILED"},
    "FC-11315": {"process_dead": True, "mtime_changing": True, "stall_detected": False},
    "FC-11316": {"path_len": 300, "mtime_stall_coupled": True},
    "FC-11317": {"unit_hung": True, "batch_blocked": True},
    "FC-11318": {"http_status": 429, "backoff": False},
    "FC-11319": {"harvest_empty": True, "reported_success": True},
    "FC-11320": {"merge_collision": True, "permission_ok": False},
    "FC-11321": {"expected_remote": "origin-a", "actual_remote": "origin-b"},
    "FC-11322": {"behind_main": True, "would_revert": True},
    "FC-11323": {"prose_only": True, "detector_fired": True},
    "FC-11324": {"defect_present": True, "detector_fired": False},
    "FC-11325": {"mutation_present": True, "tests_green": True},
    "FC-11326": {"sessions": 2, "mcp_procs": 8},
    "FC-11327": {"nproc_at_limit": True, "create_failed": True},
    "FC-11328": {"killed_shared_service": True},
    "FC-11329": {"skill_in_repo": True, "skill_in_live": False},
    "FC-11330": {"skill_installed": True, "router_selected": False},
    "FC-11331": {"superior_exists": True, "used_superior": False},
    "FC-11332": {"source_caps": ["edit", "search", "browser"], "fused_caps": ["edit", "search"]},
    "FC-11333": {"fused_score": 0.2, "min_source_score": 0.6},
    "FC-11334": {"accepted": True, "only_reason": "stage_count"},
    "FC-11335": {"loop_without_stop": True},
    "FC-11336": {"trigger": True, "threshold": None},
    "FC-11337": {"stop_rule": ""},
    "FC-11338": {"rounds": 1, "min_rounds": 3, "stopped": True},
    "FC-11339": {"idea_count": 100, "unique_normalized": 8},
    "FC-11340": {"dissent_in": True, "dissent_out": False},
    "FC-11341": {"minority_present": True, "attributed": False},
    "FC-11342": {"corruption_threshold": None},
    "FC-11343": {"nested_complete_agree": False},
    "FC-11344": {"later_stage_contains_instruction": True},
    "FC-11345": {"secret_in_artifact": True},
    "FC-11346": {"excessive_permissions": True},
    "FC-11347": {"user_file_removed_on_rollback": True},
}

WF_CAPS = {
    "FC-11331": ["workflow-scout"],
    "FC-11332": ["fusion", "capability-diff"],
    "FC-11333": ["fusion", "benchmark"],
    "FC-11334": ["fusion", "vanity-guard"],
}

B02_SPEC: list[tuple[str, str, dict]] = [
    ("AUD-0001", "easy", {"ancestry_ahead": True, "content_equal": True}),
    ("AUD-0002", "medium", {"unique_to_worktree": True, "preserved_elsewhere": False}),
    ("AUD-0003", "medium", {"pr_merged_or_closed": True, "content_on_main": False}),
    ("AUD-0004", "medium", {"stash_untracked_only": True, "reported_populated": True}),
    ("AUD-0005", "easy", {"tag_exists": True, "release_assets": 0}),
    ("AUD-0006", "medium", {"authored_module": True, "scratch_looking_path": True, "classified_scratch": True}),
    ("AUD-0007", "easy", {"fetchless_remote": True, "probe_reports_no_remote": True}),
    ("AUD-0009", "easy", {"gitfile_submodule": True, "finder_missed": True}),
    ("AUD-0011", "medium", {"eol_only_diff": True, "reported_content_diff": True}),
    ("AUD-0012", "medium", {"one_byte_change_trees": 1, "reported_changed_trees": 0}),
    ("AUD-0013", "easy", {"orphan_hook": True, "named": False}),
    ("AUD-0020", "easy", {"lockfile_pin_out_of_range": True}),
    ("AUD-0021", "easy", {"integrity_hash_corrupt": True, "checker_exit_zero": True}),
    ("AUD-0024", "medium", {"declared_license": "MIT", "license_file": "AGPL"}),
    ("AUD-0030", "medium", {"planted_cycle_len": 2, "reported_cycles": 0}),
    ("AUD-0092", "hard", {"backup_contains_secret": True}),
    ("AUD-0093", "hard", {"manifest_says_reversible": True, "action_reversible": False}),
]


def split_for(cid: str) -> str:
    n = int(hashlib.sha256(cid.encode("utf-8")).hexdigest(), 16) % 10
    if n < 5:
        return "dev"
    if n < 8:
        return "test"
    return "held-out-shadow"


def invert_fixed(match: dict) -> dict:
    out: dict = {}
    for key, value in match.items():
        if isinstance(value, bool):
            out[key] = not value
        elif value is None:
            out[key] = "specified"
        elif isinstance(value, int):
            out[key] = 0 if value else 1
        elif isinstance(value, float):
            out[key] = 1.0 if value < 0.5 else 0.0
        elif isinstance(value, str):
            out[key] = value + "-fixed"
        elif isinstance(value, list):
            out[key] = list(value)
        else:
            out[key] = value
    if "source_caps" in match and "fused_caps" in match:
        out["fused_caps"] = list(match["source_caps"])
        out["source_caps"] = list(match["source_caps"])
    if match.get("sha_repo") and match.get("sha_live") and match["sha_repo"] != match["sha_live"]:
        out["sha_repo"] = "same"
        out["sha_live"] = "same"
    if match.get("cache_sha") and match.get("package_sha") and match["cache_sha"] != match["package_sha"]:
        out["cache_sha"] = "new"
        out["package_sha"] = "new"
    if "path_a" in match and "path_b" in match:
        out["path_a"] = "Rules.md"
        out["path_b"] = "Rules.md"
    if "key_a" in match and "key_b" in match:
        out["key_a"] = "id"
        out["key_b"] = "id"
        out["folded_collision"] = False
    if match.get("declared_license") and match.get("license_file"):
        out["declared_license"] = "MIT"
        out["license_file"] = "MIT"
    return out


def make_case(
    cid: str,
    instruction: str,
    *,
    oracle: dict,
    good: dict,
    bad: dict,
    provenance: dict,
    stratum: str,
    task_extra: dict | None = None,
    capabilities: list[str] | None = None,
) -> dict:
    case: dict = {
        "id": cid,
        "task_input": {"instruction": instruction, **(task_extra or {})},
        "oracle": oracle,
        "known_good_solution": good,
        "known_bad_solution": bad,
        "provenance": provenance,
        "difficulty_stratum": stratum,
        "split": split_for(cid),
    }
    if capabilities:
        case["workflow_capabilities"] = capabilities
    check = sanity(case)
    if not check["ok"]:
        raise SystemExit(f"FAILED:TST-0295 assemble sanity {cid} {check}")
    return case


def both_states_case(
    cid: str,
    instruction: str,
    match: dict,
    provenance: dict,
    stratum: str,
    capabilities: list[str] | None = None,
) -> dict:
    broken = dict(match)
    broken["marker"] = f"{cid}-BROKEN"
    fixed = invert_fixed(match)
    fixed["marker"] = f"{cid}-FIXED"
    return make_case(
        cid,
        instruction,
        oracle={
            "kind": "both_states_detector",
            "oracle_type": "deterministic",
            "expect_broken": True,
            "expect_fixed": False,
        },
        good={"detector": "pattern_match", "match": match},
        bad={"detector": "always_true"},
        provenance=provenance,
        stratum=stratum,
        task_extra={"broken": broken, "fixed": fixed},
        capabilities=capabilities,
    )


def load_b02_titles() -> dict[str, str]:
    titles: dict[str, str] = {}
    if not CATALOG.is_file():
        return titles
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        if uid.startswith("AUD-") and unit.get("bucket") == "B02":
            titles[uid] = str(unit.get("title") or uid)
    return titles


def fc_cases() -> list[dict]:
    assert_complete()
    if set(FC_MATCH) != {row["id"] for row in CLASSES}:
        missing = {row["id"] for row in CLASSES} - set(FC_MATCH)
        extra = set(FC_MATCH) - {row["id"] for row in CLASSES}
        raise SystemExit(f"FAILED:TST-0295 FC_MATCH mismatch missing={missing} extra={extra}")
    out: list[dict] = []
    for row in CLASSES:
        fid = row["id"]
        prov = {
            "source": f"{SOURCE_CITATION}; reconstructed {fid} spec line {row['spec']}",
            "source_kind": "seeded-failure-class",
            "derived_from_real_defect": False,
            "source_file_present": False,
            "notes": (
                f"_USER-PROMPTS.md source {SOURCE_STATUS}. Class name reconstructed: {row['name']}"
            ),
        }
        out.append(
            both_states_case(
                f"CASE-{fid}",
                (
                    f"Detect failure class {fid}: {row['name']}. "
                    "Fire on the broken fixture, stay silent on the fixed fixture."
                ),
                FC_MATCH[fid],
                prov,
                row["stratum"],
                WF_CAPS.get(fid),
            )
        )
    return out


def b02_cases() -> list[dict]:
    titles = load_b02_titles()
    out: list[dict] = []
    for uid, stratum, match in B02_SPEC:
        title = titles.get(uid, uid)
        live = REPO / "command-center" / "audit" / f"{uid}.json"
        present = live.is_file()
        prov = {
            "source": f"command-center/WORK-UNIT-CATALOG.json id={uid} bucket=B02 title={title}",
            "source_kind": "b02-catalog-unit",
            "derived_from_real_defect": True,
            "live_artifact_present": present,
            "notes": (
                "Derived from B02 catalog tests_required as a machine-checkable both-states "
                "fixture. Live AUD artifact absent on this worktree."
                if not present
                else "Live AUD artifact present."
            ),
        }
        out.append(
            both_states_case(
                f"CASE-B02-{uid}",
                f"Detect the B02 defect encoded by {uid} ({title}).",
                match,
                prov,
                stratum,
            )
        )
    return out


def workflow_cases() -> list[dict]:
    prov = {
        "source": (
            "command-center/WORK-UNIT-CATALOG.json TST-0295.inputs "
            "workflow benchmark cases implied at :10741; _USER-PROMPTS.md absent"
        ),
        "source_kind": "workflow-benchmark",
        "derived_from_real_defect": False,
        "source_file_present": False,
        "notes": (
            "Reconstructed pairing/complementarity cases so later fusion comparisons "
            "cannot use a union or fold unique capabilities into the head-to-head."
        ),
    }
    shared = ["edit", "search"]
    fusion_only = ["browser"]
    a_cases = [f"c-a{i}" for i in range(6)]
    b_ok = [f"c-a{i}" for i in range(2, 8)]
    b_thin = ["c-a5"]
    return [
        make_case(
            "CASE-WF-CAP-PARTITION",
            "Partition fusion capabilities: head-to-head may only use capabilities every source has.",
            oracle={"kind": "capability_partition", "oracle_type": "deterministic"},
            good={"head_to_head": shared, "complementarity": fusion_only},
            bad={"head_to_head": shared + fusion_only, "complementarity": []},
            provenance=prov,
            stratum="hard",
            task_extra={
                "shared_capabilities": shared,
                "fusion_only_capabilities": fusion_only,
            },
            capabilities=["fusion", "capability-diff"],
        ),
        make_case(
            "CASE-WF-INTERSECT-OK",
            "Pair fusion vs sources on the intersection of runnable cases, not the union.",
            oracle={"kind": "intersection_gate", "oracle_type": "deterministic"},
            good={"intersection": sorted(set(a_cases) & set(b_ok)), "blocked": False},
            bad={"intersection": sorted(set(a_cases) | set(b_ok)), "blocked": False},
            provenance=prov,
            stratum="medium",
            task_extra={
                "source_a_cases": a_cases,
                "source_b_cases": b_ok,
                "minimum_intersection": 3,
            },
            capabilities=["fusion", "matched-cases"],
        ),
        make_case(
            "CASE-WF-INTERSECT-BELOW-MIN",
            "A comparison whose intersection is below the minimum size must be blocked.",
            oracle={"kind": "intersection_gate", "oracle_type": "deterministic"},
            good={"intersection": sorted(set(a_cases) & set(b_thin)), "blocked": True},
            bad={"intersection": sorted(set(a_cases) & set(b_thin)), "blocked": False},
            provenance=prov,
            stratum="hard",
            task_extra={
                "source_a_cases": a_cases,
                "source_b_cases": b_thin,
                "minimum_intersection": 5,
            },
            capabilities=["fusion", "matched-cases"],
        ),
        make_case(
            "CASE-WF-UNION-GAMING",
            "Reporting the union as the comparison set is forbidden.",
            oracle={"kind": "intersection_gate", "oracle_type": "deterministic"},
            good={"intersection": sorted(set(a_cases) & set(b_ok)), "blocked": False},
            bad={"intersection": sorted(set(a_cases) | set(b_ok)), "blocked": False},
            provenance=prov,
            stratum="hard",
            task_extra={
                "source_a_cases": a_cases,
                "source_b_cases": b_ok,
                "minimum_intersection": 2,
            },
            capabilities=["fusion", "matched-cases"],
        ),
        make_case(
            "CASE-WF-SOURCE-A-ONLY",
            "Cases only source A can run must be excluded from head-to-head.",
            oracle={"kind": "intersection_gate", "oracle_type": "deterministic"},
            good={"intersection": ["shared-1"], "blocked": False},
            bad={"intersection": ["a-only", "shared-1"], "blocked": False},
            provenance=prov,
            stratum="medium",
            task_extra={
                "source_a_cases": ["a-only", "shared-1"],
                "source_b_cases": ["shared-1", "b-only"],
                "minimum_intersection": 1,
            },
            capabilities=["fusion", "matched-cases"],
        ),
        make_case(
            "CASE-WF-ASYMMETRIC-COMPLEMENT",
            "Fusion-only capabilities stay in complementarity, never in head-to-head.",
            oracle={"kind": "capability_partition", "oracle_type": "deterministic"},
            good={"head_to_head": ["lint"], "complementarity": ["deploy"]},
            bad={"head_to_head": ["lint", "deploy"], "complementarity": []},
            provenance=prov,
            stratum="medium",
            task_extra={
                "shared_capabilities": ["lint"],
                "fusion_only_capabilities": ["deploy"],
            },
            capabilities=["fusion", "complementarity"],
        ),
        make_case(
            "CASE-WF-FUSION-CAP-LOSS",
            "A fusion that drops a source capability must fail the capability-partition oracle.",
            oracle={"kind": "capability_partition", "oracle_type": "deterministic"},
            good={"head_to_head": ["edit", "search"], "complementarity": []},
            bad={"head_to_head": ["edit"], "complementarity": []},
            provenance=prov,
            stratum="hard",
            task_extra={
                "shared_capabilities": ["edit", "search"],
                "fusion_only_capabilities": [],
            },
            capabilities=["fusion", "capability-diff"],
        ),
        make_case(
            "CASE-WF-EMPTY-INTERSECT-BLOCK",
            "Empty intersection blocks the comparison.",
            oracle={"kind": "intersection_gate", "oracle_type": "deterministic"},
            good={"intersection": [], "blocked": True},
            bad={"intersection": [], "blocked": False},
            provenance=prov,
            stratum="easy",
            task_extra={
                "source_a_cases": ["only-a"],
                "source_b_cases": ["only-b"],
                "minimum_intersection": 1,
            },
            capabilities=["fusion", "matched-cases"],
        ),
    ]


def judged_cases() -> list[dict]:
    prov = {
        "source": (
            "TST-0295 requires tagging model-judgement oracles so downstream analysis "
            "can separate them from deterministic checks"
        ),
        "source_kind": "judged-proxy",
        "derived_from_real_defect": False,
        "source_file_present": False,
        "notes": (
            "Runnable rubric is a span-presence proxy, not a live model judge. "
            "oracle_type=judged."
        ),
    }
    return [
        make_case(
            "CASE-J-STEELMAN",
            "Judged: a steelman must precede the rebuttal.",
            oracle={
                "kind": "judged_rubric",
                "oracle_type": "judged",
                "required_spans": ["STEELMAN:", "REBUTTAL:"],
                "forbidden_spans": ["STEELMAN-SKIPPED"],
            },
            good={"text": "STEELMAN: the strongest contrary case is X.\nREBUTTAL: it fails because Y."},
            bad={"text": "REBUTTAL: they are wrong."},
            provenance=prov,
            stratum="hard",
            capabilities=["council", "steelman"],
        ),
        make_case(
            "CASE-J-DISSENT-ATTR",
            "Judged: dissent must be quoted and attributed.",
            oracle={
                "kind": "judged_rubric",
                "oracle_type": "judged",
                "required_spans": ["DISSENT-QUOTE:", "ATTRIBUTED-TO:"],
                "forbidden_spans": ["DISSENT-DROPPED"],
            },
            good={"text": "DISSENT-QUOTE: keep the held-out split.\nATTRIBUTED-TO: seat-skeptic"},
            bad={"text": "The council agreed unanimously."},
            provenance=prov,
            stratum="hard",
            capabilities=["council", "dissent"],
        ),
        make_case(
            "CASE-J-MATERIAL-COMPLEMENT",
            "Judged: complementarity must not be folded into the head-to-head score.",
            oracle={
                "kind": "judged_rubric",
                "oracle_type": "judged",
                "required_spans": ["COMPLEMENTARITY:", "NOT-HEAD-TO-HEAD:"],
                "forbidden_spans": ["FOLDED-INTO-SCORE"],
            },
            good={
                "text": (
                    "COMPLEMENTARITY: browser cases only fusion can run.\n"
                    "NOT-HEAD-TO-HEAD: excluded from paired score."
                )
            },
            bad={"text": "Fusion wins 12-8. FOLDED-INTO-SCORE"},
            provenance=prov,
            stratum="hard",
            capabilities=["fusion", "complementarity"],
        ),
        make_case(
            "CASE-J-IDEA-NOVELTY",
            "Judged: wording variants do not count as 100 unique ideas.",
            oracle={
                "kind": "judged_rubric",
                "oracle_type": "judged",
                "required_spans": ["UNIQUE-IDEAS:", "NORMALIZED-COUNT:"],
                "forbidden_spans": ["VARIANT-PADDING"],
            },
            good={"text": "UNIQUE-IDEAS: 14 distinct mechanisms.\nNORMALIZED-COUNT: 14"},
            bad={"text": "100 ideas. VARIANT-PADDING"},
            provenance=prov,
            stratum="hard",
            capabilities=["council", "count-gaming"],
        ),
    ]


def vacuous_control_case() -> dict:
    return {
        "id": "CASE-VACUOUS-ALWAYS-PASS",
        "task_input": {"instruction": "Vacuous oracle control — must be stripped."},
        "oracle": {"kind": "always_pass", "oracle_type": "deterministic"},
        "known_good_solution": {"anything": True},
        "known_bad_solution": {"anything": False},
        "provenance": {
            "source": "assembler negative control",
            "source_kind": "seeded-failure-class",
            "derived_from_real_defect": False,
        },
        "difficulty_stratum": "easy",
        "split": "dev",
    }


def assemble() -> tuple[list[dict], dict]:
    cases = fc_cases() + b02_cases() + workflow_cases() + judged_cases()
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise SystemExit("FAILED:TST-0295 duplicate case ids")
    vacuous = vacuous_control_case()
    vac_check = sanity(vacuous)
    if vac_check["ok"] or not vac_check["vacuous"]:
        raise SystemExit(f"FAILED:TST-0295 vacuous control did not vacuate {vac_check}")
    stripped = [vacuous["id"]]
    for case in cases:
        if case["id"] in stripped:
            raise SystemExit("FAILED:TST-0295 vacuous id leaked into corpus")
        if not evaluate(case, case["known_good_solution"]):
            raise SystemExit(f"FAILED:TST-0295 known-good silent {case['id']}")
        if evaluate(case, case["known_bad_solution"]):
            raise SystemExit(f"FAILED:TST-0295 known-bad accepted {case['id']}")
    return cases, {
        "vacuous_rejected": stripped,
        "vacuous_reason": "oracle accepted both known-good and known-bad",
    }


def write_corpus(cases: list[dict]) -> dict:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    for old in CASES_DIR.glob("CASE-*.json"):
        old.unlink()
    for case in cases:
        path = CASES_DIR / f"{case['id']}.json"
        path.write_text(json.dumps(case, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    by_split: dict[str, int] = {}
    by_stratum: dict[str, int] = {}
    by_oracle: dict[str, int] = {}
    for case in cases:
        by_split[case["split"]] = by_split.get(case["split"], 0) + 1
        by_stratum[case["difficulty_stratum"]] = by_stratum.get(case["difficulty_stratum"], 0) + 1
        ot = case["oracle"]["oracle_type"]
        by_oracle[ot] = by_oracle.get(ot, 0) + 1
    n = len(cases)
    index = {
        "schema": SCHEMA_REL,
        "cases_dir": "command-center/bench/cases",
        "n": n,
        "ids": [c["id"] for c in cases],
        "counts_by_split": by_split,
        "counts_by_stratum": by_stratum,
        "counts_by_oracle_type": by_oracle,
        "deterministic_fraction": by_oracle.get("deterministic", 0) / n,
        "judged_fraction": by_oracle.get("judged", 0) / n,
    }
    INDEX_PATH.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index
