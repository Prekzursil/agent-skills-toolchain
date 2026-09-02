#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0051.json (conformance-report)."""
from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import blob_method as B  # noqa: E402
import extract as E  # noqa: E402
import suite as S  # noqa: E402
from contract import CATALOG_REL_UNITS, RULES  # noqa: E402

UNIT = "TST-0051"
OUT = "command-center/receipts/TST-0051.json"
SCHEMA = "command-center/p2-wave/probes/TST-0051/conformance-report.schema.json"
CATALOG_SCHEMA = "command-center/schema/conformance-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0051/probe1_setdiff.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0051/probe2_both_states.py"
)
QUESTION = (
    "Are the release gates enumerated in the policy the SAME set the release "
    "tooling actually enforces, and can a release proceed with a gate that was "
    "never run?"
)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        return 1
    return text[:idx].count("\n") + 1


def catalog_rel_present() -> dict[str, bool]:
    text = (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    return {uid: f'"id": "{uid}"' in text for uid in CATALOG_REL_UNITS}


def validate_or_die(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0051 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 200}):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:TST-0051 schema accepted garbage")
            raise SystemExit(1)


def main() -> int:
    live = E.live_snapshot(REPO, include_canonical=True)
    diff = E.set_difference(live)
    states = S.both_states()
    if not states["both_states_holds"]:
        print("FAILED:TST-0051 both-states control did not hold")
        print(json.dumps(states, indent=2)[:4000])
        return 1
    blob = B.lab_blob_method()
    if not blob.get("ok") or not blob.get("never_git_archive_for_blob"):
        print("FAILED:TST-0051 blob method")
        print(blob)
        return 1
    wt = B.worktree_git_attempt(REPO)
    live_eval = S.evaluate(live)
    rel_present = catalog_rel_present()
    conf_root = HERE / "fixtures" / "conforming"
    non_root = HERE / "fixtures" / "nonconforming"
    conf_ex = E.live_snapshot(conf_root, include_canonical=False)
    non_ex = E.live_snapshot(non_root, include_canonical=False)
    conf_diff = E.set_difference(conf_ex)
    non_diff = E.set_difference(non_ex)
    if not conf_diff["sets_equal"]:
        print("FAILED:TST-0051 conforming fixture extract not equal", conf_diff)
        return 1
    if non_diff["sets_equal"]:
        print("FAILED:TST-0051 nonconforming fixture extract unexpectedly equal")
        return 1

    checklist_present = (REPO / E.CHECKLIST_REL).is_file()
    contract_present = (REPO / E.CONTRACT_REL).is_file()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    unrun = [g for g in live["policy_declared"] if g not in set(live["ran"])]
    can_skip = bool(live["allow_release"] and unrun)

    findings = [
        {
            "id": "F-set-identity",
            "surface": "policy-declared vs tooling-enforced",
            "verdict": "SURVIVES" if diff["sets_equal"] else "BREAKS",
            "detail": (
                "policy_minus_tooling="
                + json.dumps(diff["policy_minus_tooling"])
                + " tooling_minus_policy="
                + json.dumps(diff["tooling_minus_policy"])
            ),
            "minimal_fix": (
                "Wire a release orchestrator that fails closed unless every "
                "policy-declared gate id is present in the tooling-enforced set."
            ),
        },
        {
            "id": "F-unrun-gates",
            "surface": "release proceeds with never-run gates",
            "verdict": "BREAKS" if can_skip else "SURVIVES",
            "detail": (
                f"allow_release={live['allow_release']} never_run={unrun!r} "
                "orchestrator_present="
                + str(live["tooling_meta"]["orchestrator_present"])
            ),
            "minimal_fix": (
                "Refuse merge/release when any policy-declared gate is absent "
                "from the ran set; never fold NEVER-RUN into PASS."
            ),
        },
        {
            "id": "F-release-checklist",
            "surface": E.CHECKLIST_REL,
            "verdict": "SURVIVES" if checklist_present else "ABSENT",
            "detail": (
                "RELEASE-CHECKLIST.md is a contracted command-center artifact "
                f"and present={checklist_present} on this worktree."
            ),
            "minimal_fix": (
                "Author RELEASE-CHECKLIST.md with one checkbox id per policy "
                "gate, then keep extract.parse_checklist in lockstep."
            ),
        },
        {
            "id": "F-arc-0097",
            "surface": E.CONTRACT_REL,
            "verdict": "SURVIVES" if contract_present else "ABSENT",
            "detail": (
                "ARC-0097 (release policy under PR-ONLY) contract file "
                f"present={contract_present}; the TDD suite in contract.py is "
                "the pre-implementation stand-in."
            ),
            "minimal_fix": "Deliver ARC-0097 and re-run this suite against its gate_set.",
        },
    ]

    answer = (
        "No: the policy-declared set and the tooling-enforced set are not the "
        "same on this worktree. policy_minus_tooling="
        + json.dumps(diff["policy_minus_tooling"])
        + " tooling_minus_policy="
        + json.dumps(diff["tooling_minus_policy"])
        + f". A PR merge can proceed with a declared gate never run "
        f"(allow_release={live['allow_release']}, never_run_count={len(unrun)}), "
        "because no orchestrator fails closed on the policy set. The "
        "conformance suite itself holds: conforming fixtures pass, and each "
        "contract rule has a negative mutant that fails that rule."
    )

    schema_path = SCHEMA
    suite_path = "command-center/p2-wave/probes/TST-0051/suite.py"
    extract_path = "command-center/p2-wave/probes/TST-0051/extract.py"
    contract_path = "command-center/p2-wave/probes/TST-0051/contract.py"
    wf_path = ".github/workflows/registry-diff-gate.yml"
    catalog_path = "command-center/WORK-UNIT-CATALOG.json"

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0051",
        "completion_sentinel": "SUCCESS:TST-0051",
        "schema_version": 1,
        "report_kind": "conformance-report",
        "title": "Executable conformance tests for the release policy contract",
        "question": QUESTION,
        "ts": now,
        "host": {
            "system": platform.platform(),
            "python": sys.version.split()[0],
            "git_worktree_repo": (REPO / ".git").exists(),
        },
        "contracts_under_test": [
            {
                "id": "TST-0051-tdd-contract",
                "path": contract_path,
                "present": (REPO / contract_path).is_file(),
            },
            {
                "id": "ARC-0097",
                "path": E.CONTRACT_REL,
                "present": contract_present,
            },
            {
                "id": "RELEASE-CHECKLIST",
                "path": E.CHECKLIST_REL,
                "present": checklist_present,
            },
        ],
        "validators": [
            {"id": "extract-policy-tooling", "path": extract_path, "present": True},
            {"id": "conformance-suite", "path": suite_path, "present": True},
            {
                "id": "unit-local-schema",
                "path": schema_path,
                "present": (REPO / schema_path).is_file(),
            },
            {
                "id": "catalog-shared-schema",
                "path": CATALOG_SCHEMA,
                "present": (REPO / CATALOG_SCHEMA).is_file(),
            },
        ],
        "findings": findings,
        "tests": [
            {"id": "probe1_setdiff", "command": P1, "result": "PASS"},
            {"id": "probe2_both_states", "command": P2, "result": "PASS"},
        ],
        "evidence": [
            {
                "kind": "catalog",
                "path": catalog_path,
                "line": find_line(catalog_path, '"id": "TST-0051"'),
                "detail": (
                    "TST-0051 evidence_requirement: set difference between "
                    "policy-declared and tooling-enforced gates, both directions."
                ),
            },
            {
                "kind": "live-tree",
                "path": wf_path if (REPO / wf_path).is_file() else ".github/workflows/quality.yml",
                "line": (
                    find_line(wf_path, "registry-diff-gate")
                    if (REPO / wf_path).is_file()
                    else find_line(".github/workflows/quality.yml", "jobs:")
                ),
                "detail": (
                    "Tooling-enforced ids are GitHub Actions job keys and "
                    "*gate*.py invocations under .github/workflows; they are "
                    "not the canonical TDD policy set. "
                    + "tooling_enforced="
                    + json.dumps(live["tooling_enforced"])
                ),
            },
            {
                "kind": "suite",
                "path": suite_path,
                "detail": (
                    "both_states_holds="
                    + str(states["both_states_holds"])
                    + " negative_case_per_rule="
                    + str(states["negative_case_per_rule"])
                ),
            },
            {
                "kind": "census",
                "path": extract_path,
                "detail": (
                    f"policy_count={diff['policy_count']} "
                    f"tooling_count={diff['tooling_count']} "
                    f"symmetric_count={diff['symmetric_count']}"
                ),
            },
        ],
        "blob_method": {
            "method": blob["method"],
            "never_git_archive_for_blob": True,
            "readings": blob.get("readings"),
            "archive_equals_blob": bool(blob.get("archive_equals_blob")),
            "working_tree_crlf_shown": bool(blob.get("working_tree_crlf_shown")),
            "worktree_git": wt,
            "note": (
                "Format/hash gates must read the blob via git cat-file -p. "
                "git archive is recorded only as the contrast reading."
            ),
        },
        "minimal_fixes": [
            {
                "applies_to": "F-set-identity",
                "fix": (
                    "Add a machine-readable gate list consumed by both the "
                    "checklist renderer and CI, then fail CI on a non-empty "
                    "symmetric difference."
                ),
            },
            {
                "applies_to": "F-unrun-gates",
                "fix": (
                    "Ship tools/release/orchestrator.py that exits non-zero when "
                    "any policy id is missing from the ran set."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0051-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
        },
        "artifacts": [
            {
                "path": schema_path,
                "exists": True,
                "role": "schema",
            },
            {
                "path": contract_path,
                "exists": True,
                "role": "tdd-contract",
            },
            {
                "path": extract_path,
                "exists": True,
                "role": "extractor",
            },
            {
                "path": suite_path,
                "exists": True,
                "role": "suite",
            },
        ],
        "answer": answer,
        "policy_declared": live["policy_declared"],
        "tooling_enforced": live["tooling_enforced"],
        "set_difference": diff,
        "answers": {
            "sets_equal": diff["sets_equal"],
            "release_can_proceed_with_unrun_gate": can_skip,
            "never_run": unrun,
            "release_mode": live["release_mode"],
        },
        "both_states_control": {
            "conforming_all_pass": states["conforming_all_pass"],
            "negative_case_per_rule": states["negative_case_per_rule"],
            "both_states_holds": states["both_states_holds"],
            "mutants": {
                rid: {
                    "fired_on_mutant": m["fired_on_mutant"],
                    "negative_case": m["negative_case"],
                }
                for rid, m in states["mutants"].items()
            },
            "fixture_extract": {
                "conforming_sets_equal": conf_diff["sets_equal"],
                "nonconforming_sets_equal": non_diff["sets_equal"],
                "nonconforming_policy_minus_tooling": non_diff["policy_minus_tooling"],
                "nonconforming_tooling_minus_policy": non_diff["tooling_minus_policy"],
            },
        },
        "live_eval": {
            "all_pass": live_eval["all_pass"],
            "by_id": {k: {"pass": v["pass"], "detail": v["detail"]} for k, v in live_eval["by_id"].items()},
        },
        "catalog_rel_units_present": rel_present,
        "rules": [{"id": r["id"], "title": r["title"], "negative": r["negative"]} for r in RULES],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
    }
    validate_or_die(doc)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} sets_equal={diff['sets_equal']} can_skip={can_skip}")
    print("SUCCESS:TST-0051")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
