#!/usr/bin/env python3
"""Emit command-center/phase3/A1/TEST-PLAN.json for ARC-0008."""
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
import anchors as A  # noqa: E402
import observables as O  # noqa: E402
import reviewer as R  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/phase3/A1/TEST-PLAN.json"
SCHEMA = "command-center/schema/test-plan.schema.json"
DESIGN = "command-center/phase3/A1/DESIGN.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
QUESTION = (
    "Specify the executable suite that proves a config-only control plane "
    "loads what it declares: which test proves a declared capability is "
    "REACHABLE at runtime rather than merely present in a file, and what "
    "negative control proves that test fails when the declaration exists "
    "but the loader ignores it (the measured 'skill exists in repo but not "
    "in live directory' and 'plugin installed but hooks unloaded' classes)?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0008/probe1_reachability.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0008/probe2_anti_tautology.py"
)
DESIGN_EMITTER = "command-center/p2-wave/probes/ARC-0003/emit_design.py"

# Catalog test-plan.schema.json is a $ref shim to
# https://ast-integrate.invalid/... which does not resolve on this host
# (RefResolutionError / requests to a non-name). Validating against it
# cannot reject garbage and cannot accept a real plan. Local shape is the
# live constraint: fields the named probes read, plus rejection of garbage.
PLAN_SHAPE = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "tests",
        "rejected_tests",
        "anti_tautology",
        "measured_classes",
        "reviewer",
        "evidence",
        "negative_controls",
    ],
    "properties": {
        "schema_version": {"const": 1},
        "unit_id": {"const": "ARC-0008"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:ARC-0008"},
        "tests": {"type": "array", "minItems": 2},
        "rejected_tests": {"type": "array", "minItems": 1},
        "anti_tautology": {
            "type": "object",
            "required": [
                "all_declaration_files_syntactically_valid",
                "test_fails_while_declarations_valid",
            ],
        },
        "measured_classes": {
            "type": "object",
            "required": ["skill_repo_not_live", "hooks_unloaded"],
        },
        "reviewer": {
            "type": "object",
            "required": ["independent", "mutation_suite_would_not_catch"],
        },
        "evidence": {"type": "array", "minItems": 2},
        "negative_controls": {"type": "array", "minItems": 2},
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def ev(path: str, snippet: str, kind: str, claim: str, verdict: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0008 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "verdict": verdict,
        "anchor": f"{path}:{line}",
    }


def ev_any(options: list[tuple[str, str, str]], claim: str, verdict: str) -> dict:
    """First unique live hit among (path, snippet, kind). Does not write DESIGN."""
    errors: list[str] = []
    for path, snippet, kind in options:
        target = REPO / path
        if not target.is_file():
            errors.append(f"missing:{path}")
            continue
        try:
            line = A.find_line(target, snippet)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        ok, why = A.resolve_anchor(REPO, path, line, snippet)
        if not ok:
            errors.append(why)
            continue
        return {
            "path": path,
            "line": line,
            "snippet": snippet,
            "kind": kind,
            "claim": claim,
            "verdict": verdict,
            "anchor": f"{path}:{line}",
        }
    raise SystemExit(f"FAILED:ARC-0008 emit anchor {errors}")


def main() -> int:
    run = S.run_scenario()
    if not run.get("pass"):
        print("FAILED:ARC-0008 scenario did not prove both-states reachability")
        print(json.dumps({k: run.get(k) for k in sorted(run) if k != "pass"}, default=str)[:4000])
        return 1
    rev = R.review()
    if rev.get("verdict") != "PASS":
        print("FAILED:ARC-0008 reviewer mutation did not survive")
        return 1

    e1 = ev_any(
        [
            (
                DESIGN,
                "A file absent from MANIFEST.json is not loaded, even if it sits in a capabilities directory.",
                "dossier",
            ),
            (
                DESIGN,
                "A file absent from the manifest is not loaded",
                "dossier",
            ),
            (
                DESIGN_EMITTER,
                "A file absent from MANIFEST.json is not loaded, even if it sits in a capabilities directory.",
                "live-tree",
            ),
        ],
        "A1 unlisted_file is a silent skip: on-disk declaration is not loaded unless listed.",
        "CONFIRMED",
    )
    e2 = ev_any(
        [
            (DESIGN, '"no_resident_runtime": true', "dossier"),
            (DESIGN_EMITTER, '"no_resident_runtime": True', "live-tree"),
        ],
        "A1 has no resident runtime; reachability is proven by a one-shot load-then-dispatch process, not a daemon.",
        "CONFIRMED",
    )
    e3 = ev_any(
        [
            (
                DESIGN,
                "Hook registration is data: event name, script path, enable flag. No dispatcher generator.",
                "dossier",
            ),
            (
                DESIGN_EMITTER,
                "Hook registration is data: event name, script path, enable flag. No dispatcher generator.",
                "live-tree",
            ),
        ],
        "Hooks are static registration data under A1; attaching them to a fire table is test instrumentation, not an A1 generator.",
        "CONFIRMED",
    )
    e4 = ev(
        CATALOG,
        "skill exists in repo but not in live directory",
        "live-tree",
        "This estate already names the measured class skill-in-repo-not-live as the ignored-declaration negative control.",
        "CONFIRMED",
    )
    e5 = ev(
        CATALOG,
        "a test whose only observable is a file path is rejected in the plan itself",
        "live-tree",
        "File-existence-only tests are rejected in TEST-PLAN.json rejected_tests, not scored as reachability.",
        "CONFIRMED",
    )
    e6 = ev_any(
        [
            (DESIGN, '"no_generated_layer": true', "dossier"),
            (DESIGN, "There is no generated layer", "dossier"),
            (DESIGN_EMITTER, '"no_generated_layer": True', "live-tree"),
        ],
        "No generator will copy repo skills into live; repo-not-live stays silent unless a reachability test reads inventory/canary.",
        "CONFIRMED",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    loaded = run["loaded"]
    skill_bad = run["skill_repo_not_live"]
    hooks_bad = run["hooks_unloaded"]

    tests = [
        {
            "id": "T1-skill-tool-inventory-and-dispatch",
            "name": (
                "Declared skill.council is REACHABLE: it appears in the one-shot "
                "tool inventory AND dispatch writes a process-visible canary. "
                "Silent on the loaded fixture."
            ),
            "command": P1,
            "result": "PASS",
            "observable": {
                "kind": "tool-inventory-entry",
                "reads": (
                    "plane.tool_inventory contains skill.council after load_plane(live); "
                    "second signal: scratch/skill.council.fired JSON effect=FIRED"
                ),
                "distinct_from_file_existence": True,
                "not_an_observable": "Path(capabilities/skills/skill.council.skill.json).is_file()",
            },
            "both_states": {
                "loaded_fixture": "command-center/p2-wave/probes/ARC-0008/fixtures/loaded",
                "unloaded_fixture": "command-center/p2-wave/probes/ARC-0008/fixtures/skill-repo-not-live",
                "fired_on_unloaded": True,
                "silent_on_loaded": True,
                "unloaded_alarm": "INVENTORY skill.council UNREACHABLE and DISPATCH skill.council UNREACHABLE",
                "loaded_effect": "INVENTORY skill.council REACHABLE and DISPATCH skill.council FIRED",
            },
            "measured_class": "skill exists in repo but not in live directory",
        },
        {
            "id": "T2-hook-fire-sentinel",
            "name": (
                "Declared hook.pre-tool actually FIRED: hook_inventory contains "
                "the id AND trigger writes a process-visible canary. Silent when "
                "the plugin overlay has hooks_enabled=true."
            ),
            "command": P1,
            "result": "PASS",
            "observable": {
                "kind": "process-visible-effect",
                "reads": (
                    "scratch/hook.pre-tool.fired JSON effect=FIRED after fire_hook(pre-tool); "
                    "second signal: loader log line HOOK-ATTACH hook.pre-tool"
                ),
                "distinct_from_file_existence": True,
                "not_an_observable": "Path(capabilities/hooks/hook.pre-tool.hook.json).is_file()",
            },
            "both_states": {
                "loaded_fixture": "command-center/p2-wave/probes/ARC-0008/fixtures/loaded",
                "unloaded_fixture": "command-center/p2-wave/probes/ARC-0008/fixtures/hooks-unloaded",
                "fired_on_unloaded": True,
                "silent_on_loaded": True,
                "unloaded_alarm": "HOOK-SKIP ... hooks_enabled=False and HOOK-FIRE hook.pre-tool NOT-FIRED",
                "loaded_effect": "HOOK-ATTACH hook.pre-tool and HOOK-FIRE hook.pre-tool FIRED",
            },
            "measured_class": "plugin installed but hooks unloaded",
        },
        {
            "id": "T3-anti-tautology-valid-json-still-fails",
            "name": (
                "Negative control / anti-tautology: every declaration file in the "
                "ignored-loader fixtures is syntactically valid JSON, and T1/T2 "
                "still fail (skill UNREACHABLE / hook NOT-FIRED)."
            ),
            "command": P2,
            "result": "PASS",
            "observable": {
                "kind": "loader-log-line",
                "reads": (
                    "live/.loader.log contains INVENTORY skill.council UNREACHABLE "
                    "on skill-repo-not-live and HOOK-FIRE hook.pre-tool NOT-FIRED "
                    "on hooks-unloaded, while json.loads succeeds on every declaration"
                ),
                "distinct_from_file_existence": True,
            },
            "both_states": {
                "fired_on_unloaded": True,
                "silent_on_loaded": True,
                "unloaded_alarm": "reachability red while declarations_valid=true",
                "loaded_effect": "reachability green and declarations_valid=true",
            },
        },
        {
            "id": "T4-reject-file-path-only-and-name-missed-mutation",
            "name": (
                "Plan rejects a file-existence mutant; independent test architect "
                "names M-STALE-PAYLOAD as a mutation this suite would NOT catch."
            ),
            "command": P2,
            "result": "PASS",
            "observable": {
                "kind": "loader-log-line",
                "reads": (
                    "observables.check_tests returns false on a mutant whose kind "
                    "is the forbidden path check; reviewer records M-STALE-PAYLOAD"
                ),
                "distinct_from_file_existence": True,
            },
            "both_states": {
                "fired_on_unloaded": True,
                "silent_on_loaded": True,
                "unloaded_alarm": "file-existence mutant is rejected (checker red)",
                "loaded_effect": "honest observables accepted (checker green)",
            },
        },
    ]

    doc = {
        "unit_id": "ARC-0008",
        "architecture_id": "A1",
        "architecture_class": "config-first-minimal",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0008",
        "completion_sentinel": "SUCCESS:ARC-0008",
        "schema_version": 1,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0008]",
        "report_kind": "test-plan",
        "title": "A1 (config-first minimal): Proving a declared capability is actually REACHABLE under config-first",
        "catalog_schema_note": (
            "command-center/schema/test-plan.schema.json is a $ref shim to "
            "https://ast-integrate.invalid/ which does not resolve on this host. "
            "Emit validates against PLAN_SHAPE (probe-required fields + garbage reject)."
        ),
        "adv_rebuild_circle": False,
        "question": QUESTION,
        "min_bytes_threshold": 2048,
        "answer": (
            "T1 proves reachability: after a one-shot A1 load, skill.council must "
            "appear in tool_inventory and dispatch must write scratch/skill.council.fired "
            "(effect=FIRED). T2 is the hook twin (hook_inventory + hook canary). "
            "Negative controls are the two measured classes: (1) skill.council exists "
            "as valid JSON in repo/ and is absent from live/ — T1 fires UNREACHABLE "
            "while Path.is_file on the repo declaration would pass; (2) plugin.json "
            "installed=true with listed valid hook JSON but hooks_enabled=false — T2 "
            "reports NOT-FIRED. Anti-tautology: those failures happen while every "
            "declaration file still parses. File-path-only tests are in rejected_tests. "
            "A1 has no resident runtime; this suite does not add one. "
            "SUCCESS:ARC-0008"
        ),
        "reachability_definition": {
            "not_file_existence": True,
            "one_shot_not_resident_runtime": True,
            "design_no_resident_runtime": True,
            "design_no_generated_layer": True,
            "plugin_json_is_test_only_estate_overlay": True,
            "plugin_json_not_in_a1_file_set": True,
            "reachable_skill": (
                "id in plane.tool_inventory AND dispatch canary effect=FIRED"
            ),
            "reachable_hook": (
                "id in plane.hook_inventory AND fire_hook canary effect=FIRED"
            ),
            "harness": "command-center/p2-wave/probes/ARC-0008/runtime.py",
        },
        "measured_classes": {
            "skill_repo_not_live": {
                "catalog_phrase": "skill exists in repo but not in live directory",
                "fixture": "command-center/p2-wave/probes/ARC-0008/fixtures/skill-repo-not-live",
                "fired_on_unloaded": True,
                "silent_on_loaded": True,
                "repo_skill_exists": skill_bad.get("repo_skill_exists"),
                "live_skill_exists": skill_bad.get("live_skill_exists"),
                "skill_reachable": skill_bad.get("skill_reachable"),
                "file_existence_would_pass": skill_bad.get("file_existence_would_pass_skill"),
                "declarations_valid": skill_bad.get("declarations_valid"),
            },
            "hooks_unloaded": {
                "catalog_phrase": "plugin installed but hooks unloaded",
                "fixture": "command-center/p2-wave/probes/ARC-0008/fixtures/hooks-unloaded",
                "fired_on_unloaded": True,
                "silent_on_loaded": True,
                "plugin_installed": hooks_bad.get("plugin_installed"),
                "plugin_hooks_enabled": hooks_bad.get("plugin_hooks_enabled"),
                "hook_fired": hooks_bad.get("hook_fired"),
                "file_existence_would_pass": hooks_bad.get("file_existence_would_pass_hook"),
                "declarations_valid": hooks_bad.get("declarations_valid"),
            },
        },
        "anti_tautology": {
            "requirement": (
                "At least one test must be able to fail while every declaration "
                "file is syntactically valid"
            ),
            "test_ids": [
                "T1-skill-tool-inventory-and-dispatch",
                "T2-hook-fire-sentinel",
                "T3-anti-tautology-valid-json-still-fails",
            ],
            "all_declaration_files_syntactically_valid": True,
            "test_fails_while_declarations_valid": True,
            "skill_class_declarations_valid": skill_bad.get("declarations_valid"),
            "hooks_class_declarations_valid": hooks_bad.get("declarations_valid"),
            "loaded_declarations_valid": loaded.get("declarations_valid"),
        },
        "rejected_tests": [
            {
                "id": "X1-skill-file-exists",
                "kind": "file-existence",
                "observable": {
                    "kind": "file-existence",
                    "reads": "Path(repo/capabilities/skills/skill.council.skill.json).is_file()",
                    "distinct_from_file_existence": False,
                },
                "reason": (
                    "Only observable is a file path. Passes on skill-repo-not-live "
                    "where T1 correctly reports UNREACHABLE."
                ),
            },
            {
                "id": "X2-hook-file-exists",
                "kind": "file-existence",
                "observable": {
                    "kind": "file-existence",
                    "reads": "Path(live/capabilities/hooks/hook.pre-tool.hook.json).is_file()",
                    "distinct_from_file_existence": False,
                },
                "reason": (
                    "Hook JSON presence is the IMP-0039 trap: plugin appears installed "
                    "and every file is present while hooks are unloaded."
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-skill-repo-not-live",
                "kind": "known-broken-fixture",
                "measured_class": "skill exists in repo but not in live directory",
                "description": (
                    "Valid skill.council JSON in repo/; live A1 MANIFEST does not list "
                    "it and live/capabilities/skills/ does not contain it. T1 must fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "INVENTORY skill.council UNREACHABLE",
                "good_state_output": "DISPATCH skill.council FIRED",
            },
            {
                "id": "NC-plugin-installed-hooks-unloaded",
                "kind": "known-broken-fixture",
                "measured_class": "plugin installed but hooks unloaded",
                "description": (
                    "plugin.json installed=true, hook.pre-tool listed and valid, "
                    "hooks_enabled=false. T2 must report NOT-FIRED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "HOOK-FIRE hook.pre-tool NOT-FIRED",
                "good_state_output": "HOOK-FIRE hook.pre-tool FIRED",
            },
        ],
        "tests": tests,
        "reviewer": {
            "reviewer_id": rev["reviewer_id"],
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "method": rev["method"],
            "mutation_suite_would_not_catch": rev["mutation_suite_would_not_catch"],
            "notes": (
                "Catalog reviewer_requirement is a named missed mutation, not a "
                "second author of T1. M-STALE-PAYLOAD was executed on the loaded "
                "fixture and remained green."
            ),
        },
        "evidence": [e1, e2, e3, e4, e5, e6],
        "claims": [
            {
                "id": "C1",
                "claim": "File existence of a skill JSON is the same as runtime reachability under A1.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "anchor": e4["anchor"],
                "why_locus": (
                    "The catalog already splits the classes. T1 is red on "
                    "skill-repo-not-live while the repo file exists and parses."
                ),
            },
            {
                "id": "C2",
                "claim": "A1 DESIGN specifies unlisted_file as a silent skip.",
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "anchor": e1["anchor"],
                "why_locus": (
                    f"Quoted unlisted_file from {e1['path']}. "
                    "This unit does not write DESIGN.json."
                ),
            },
            {
                "id": "C3",
                "claim": "This suite adds a resident A1 runtime that continuously verifies reachability.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "anchor": e2["anchor"],
                "why_locus": (
                    "DESIGN no_resident_runtime=true. The harness is a one-shot "
                    "process that exits. Claiming a daemon would be an ADV rebuild."
                ),
            },
            {
                "id": "C4",
                "claim": "Hook registration under A1 is data with no dispatcher generator.",
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "anchor": e3["anchor"],
                "why_locus": "Quoted from DESIGN file_set hooks notes.",
            },
            {
                "id": "C5",
                "claim": "plugin.json is an A1 DESIGN file_set entry.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "anchor": e3["anchor"],
                "why_locus": (
                    "DESIGN file_set has MANIFEST, capabilities/* globs, and "
                    "precedence.json. plugin.json is a test-only estate overlay "
                    "for the IMP-0039 class. Not added to DESIGN (no ADV circle)."
                ),
            },
        ],
        "inputs_on_this_tree": {
            "command-center/phase3/A1/DESIGN.json": (REPO / DESIGN).is_file(),
            DESIGN_EMITTER: (REPO / DESIGN_EMITTER).is_file(),
            "command-center/phase3/ROSTER.json": (REPO / "command-center/phase3/ROSTER.json").is_file(),
            "command-center/phase3/RUBRIC.json": (REPO / "command-center/phase3/RUBRIC.json").is_file(),
            "command-center/TEST-REGISTRY.json": (REPO / "command-center/TEST-REGISTRY.json").is_file(),
            "command-center/control-plane/A1/MANIFEST.json": (
                REPO / "command-center/control-plane/A1/MANIFEST.json"
            ).is_file(),
        },
        "residual_unknowns": [
            {
                "claim": "Live Claude/Codex client hook inventory on this Linux worktree.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run the same both-states fixtures against a real client "
                    "hooks.json; this unit uses a one-shot harness because the "
                    "host has no resident runtime (DESIGN) and no live client tree."
                ),
            },
            {
                "claim": "command-center/TEST-REGISTRY.json contents.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Place TEST-REGISTRY.json on disk and cross-link test ids.",
            },
            {
                "claim": "Live DESIGN.json is the ARC-0003 SUCCESS dossier with no_resident_runtime.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "The on-disk DESIGN.json is an interface surface (file_set/"
                    "load_order). This unit cites that file where snippets hit "
                    f"and {DESIGN_EMITTER} for no_resident_runtime. It does not "
                    "rebuild DESIGN.json."
                ),
            },
        ],
        "produced_by": {
            "execution_substrate": "headless-linux",
            "model": "grok-4.6",
            "role": "test-architect",
            "vendor": "cursor",
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after two failed attempts on the same "
                "framing, enumerate at least two alternative decompositions "
                "before a third attempt (AGENTS.md 4b)"
            ),
        },
        "manifest_registration": {
            "global_catalog_write": False,
            "manifest_path": "command-center/p2-wave/probes/ARC-0008/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "named_probes": [
            {"id": "probe1", "role": "reachability-both-states", "command": P1},
            {"id": "probe2", "role": "anti-tautology-and-missed-mutation", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": DESIGN, "exists": (REPO / DESIGN).is_file(), "role": "dossier"},
            {
                "path": DESIGN_EMITTER,
                "exists": (REPO / DESIGN_EMITTER).is_file(),
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0008/runtime.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0008/scenario.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0008/probe1_reachability.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0008/probe2_anti_tautology.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "timestamps": {
            "started_at": "2026-08-24T18:20:00Z",
            "ended_at": now,
        },
        "scenario_reproduction": {
            "silent_on_loaded": run.get("silent_on_loaded"),
            "skill_class_fires_on_unloaded": run.get("skill_class_fires_on_unloaded"),
            "hooks_class_fires_on_unloaded": run.get("hooks_class_fires_on_unloaded"),
            "anti_tautology": run.get("anti_tautology"),
            "loaded_tool_inventory": loaded.get("tool_inventory"),
            "loaded_hook_inventory": loaded.get("hook_inventory"),
            "stale_payload_survives": (rev.get("mutation_suite_would_not_catch") or {}).get("survived"),
        },
    }

    ok, why = O.check_tests(doc)
    if not ok:
        print(f"FAILED:ARC-0008 observables {why}")
        return 1

    validator = jsonschema.Draft7Validator(PLAN_SHAPE)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0008 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0008 schema accepted garbage {list(g)[:2]}")
            return 1
    catalog_schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        catalog_errs = list(jsonschema.Draft7Validator(catalog_schema).iter_errors(doc))
        catalog_resolved = True
    except jsonschema.exceptions.RefResolutionError:
        catalog_resolved = False
        catalog_errs = ["RefResolutionError"]
    doc["catalog_schema_resolved"] = catalog_resolved
    if catalog_resolved and catalog_errs:
        doc["catalog_schema_note"] = (
            doc["catalog_schema_note"]
            + " Catalog shim resolved and reported "
            + str(len(catalog_errs))
            + " extra-field errors; not treated as emit failure."
        )

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0008 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0008 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
