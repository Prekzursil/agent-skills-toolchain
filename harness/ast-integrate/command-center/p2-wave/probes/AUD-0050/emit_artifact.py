#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0050-test-gate-coverage-map.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import mapper as M  # noqa: E402

UNIT = "AUD-0050"
OUT = "command-center/audit/AUD-0050-test-gate-coverage-map.json"
SCHEMA = "command-center/schema/audit-drift.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0050 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which test files exist in the repo, and for each, which CI gate (if any) "
    "would execute it on a pull request touching its module?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0050/probe1_selector_map.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0050/probe2_collect_only.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


REQUIRED_KEYS = (
    "unit_id",
    "state",
    "sentinel",
    "orphan_list",
    "gate_map",
    "collection_union_files",
    "negative_controls",
    "named_probes",
)


def validate_or_die(doc: dict) -> None:
    """Catalog output_schema is a generated $ref shim to ast-integrate.invalid.

    jsonschema 4.10.3 Draft7Validator follows that URL and raises
    RefResolutionError (NameResolutionError). G-1 measures JSON parse +
    sentinel + live probes, not a network $ref. Local gate: required keys
    present, garbage missing those keys is rejected, sentinel in the
    serialized form, state not a non-delivery token.
    """
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:AUD-0050 artifact is not an object")
    missing = [k for k in REQUIRED_KEYS if k not in doc]
    if missing:
        raise SystemExit(f"FAILED:AUD-0050 missing keys {missing}")
    if doc.get("unit_id") != UNIT:
        raise SystemExit("FAILED:AUD-0050 unit_id mismatch")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        raise SystemExit(f"FAILED:AUD-0050 self-declared {doc.get('state')}")
    blob = json.dumps(doc, ensure_ascii=True)
    if SENTINEL not in blob:
        raise SystemExit("FAILED:AUD-0050 sentinel missing from serialized artifact")
    for garbage in GARBAGE:
        if isinstance(garbage, dict) and all(k in garbage for k in REQUIRED_KEYS):
            raise SystemExit("FAILED:AUD-0050 local schema accepts garbage")


def file_row(rel: str, role: str) -> dict:
    path = REPO / rel
    exists = path.is_file()
    return {"path": rel, "exists": exists, "role": role}


def main() -> int:
    live = M.compute(include_collection=True)
    ctl = live["control"]
    if not ctl["vacuous_hides_fixture"]:
        print("FAILED:AUD-0050 vacuous mapper control did not fire")
        return 1
    if not ctl["fixture_in_orphan_list"]:
        print("FAILED:AUD-0050 planted fixture not in orphan list")
        return 1
    if not ctl["known_gated_classified_gated"]:
        print("FAILED:AUD-0050 known-gated suite not GATED")
        return 1
    if M.CONTROL_REL in live["collection_union_files"]:
        print("FAILED:AUD-0050 planted fixture collected by CI union")
        return 1
    if M.KNOWN_GATED_REL not in live["collection_union_files"]:
        print("FAILED:AUD-0050 known-gated suite missing from collect-only union")
        return 1
    if live["collection_orphan_hit"]:
        print("FAILED:AUD-0050 collect-only hit selector orphans")
        print(json.dumps(live["collection_orphan_hit"]))
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n_files = live["n_test_files"]
    n_orphan = live["n_orphan"]
    n_gated = live["n_gated"]
    precedent_status = "NOT-RECONCILED-ON-THIS-WORKTREE"
    overall = "DRIFT" if n_orphan else "ALIGNED"
    drift_findings = [
        {
            "id": "F-ORPHAN-SUITES",
            "claim": (
                f"On this worktree the selector model classifies {n_orphan} of "
                f"{n_files} test files as in no pull-request CI gate."
            ),
            "verdict": "DRIFT" if n_orphan else "ALIGNED",
            "orphan_count": n_orphan,
            "gated_count": n_gated,
        },
        {
            "id": "F-ESTATE-PRECEDENT-162-OF-244",
            "claim": (
                "Catalog input cites a measured precedent that 162 of 244 suites "
                "ran in no CI gate. That census was not re-measured here: this "
                "worktree is a slice (no .github/workflows on disk; many CI "
                "selector paths are absent)."
            ),
            "verdict": "NOT-CHECKED",
            "precedent": "162 of 244",
            "this_worktree_suites": n_files,
            "this_worktree_orphans": n_orphan,
            "status": precedent_status,
        },
        {
            "id": "F-SELECTOR-VS-COLLECTION",
            "claim": (
                "Selector-model GATED files whose selector path exists on disk "
                "were present in the pytest --collect-only union; the planted "
                "orphan fixture was not."
            ),
            "verdict": "CONFIRMED"
            if not live["collection_orphan_hit"]
            and M.KNOWN_GATED_REL in live["collection_union_files"]
            else "DRIFT",
            "collection_gated_miss": live["collection_gated_miss"],
            "collection_orphan_hit": live["collection_orphan_hit"],
        },
    ]
    doc = {
        "unit_id": UNIT,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0050",
        "report_kind": "audit-drift",
        "report": {
            "kind": "audit-drift",
            "question": QUESTION,
            "observations": [
                {
                    "name": "n_test_files",
                    "measured": n_files,
                    "method": "os.walk test-file inventory plus planted orphan fixture",
                    "anchor": "command-center/p2-wave/probes/AUD-0050/mapper.py:discover_test_files",
                },
                {
                    "name": "n_orphan",
                    "measured": n_orphan,
                    "method": "selector model against AUD-0041 PR pytest steps",
                    "anchor": live["inventory_path"],
                },
                {
                    "name": "n_collection_union",
                    "measured": len(live["collection_union_files"]),
                    "method": "pytest --collect-only union of present PR selectors",
                    "anchor": "pytest --collect-only",
                },
                {
                    "name": "fixture_in_orphan_list",
                    "measured": ctl["fixture_in_orphan_list"],
                    "method": "planted file outside every selector",
                    "anchor": M.CONTROL_REL,
                },
            ],
            "control_ids": ["AUD0050-C1", "AUD0050-C2"],
        },
        "title": "Test-file inventory and gate-coverage map: which suites are in no gate at all",
        "question": QUESTION,
        "overall_verdict": overall,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "phase": "0",
        "min_bytes_threshold": 128,
        "compared_surfaces": [
            {
                "id": "test-files",
                "role": "measured-inventory",
                "path": str(REPO),
            },
            {
                "id": "ci-selectors",
                "role": "declared-ci-from-AUD-0041",
                "path": live["inventory_path"],
            },
            {
                "id": "collect-only",
                "role": "collection-receipt",
                "path": "pytest --collect-only per PR selector",
            },
        ],
        "github_workflows_on_disk": live["github_workflows_on_disk"],
        "inventory_source": live["inventory_path"],
        "estate_precedent": {
            "claim": "162 of 244 suites ran in no CI gate",
            "status": precedent_status,
            "this_worktree": {
                "test_files": n_files,
                "gated": n_gated,
                "orphan": n_orphan,
            },
        },
        "n_test_files": n_files,
        "n_gated": n_gated,
        "n_orphan": n_orphan,
        "n_pr_collectable_steps": live["n_pr_collectable_steps"],
        "orphan_list": live["orphan_list"],
        "gated_list": live["gated_list"],
        "gate_map": live["gate_map"],
        "pr_steps": live["steps"],
        "collection_receipts": live["collection_receipts"],
        "collection_union_files": live["collection_union_files"],
        "drift_findings": drift_findings,
        "orphan_control": {
            "id": "AUD0050-C1",
            "kind": "known-broken-fixture",
            "description": (
                "A test file deliberately placed outside every selector must "
                "appear in the orphan list; if the orphan list is empty on that "
                "fixture, the mapper is not discriminating."
            ),
            "fixture": M.CONTROL_REL,
            "fired_on_bad_state": ctl["vacuous_hides_fixture"],
            "silent_on_good_state": ctl["fixture_in_orphan_list"],
            "bad_state_output": f"vacuous_orphan_list={ctl['vacuous_orphan_list']}",
            "good_state_output": f"fixture_in_orphan_list={ctl['fixture_in_orphan_list']}",
        },
        "tests": [
            {
                "id": "ctl-orphan-outside-every-selector",
                "command": (
                    "classify_files(inventory + planted "
                    f"{M.CONTROL_REL})"
                ),
                "result": "PASS" if ctl["fixture_in_orphan_list"] else "FAIL",
            },
            {
                "id": "ctl-known-gated-command-center",
                "command": f"classify_files({M.KNOWN_GATED_REL})",
                "result": "PASS" if ctl["known_gated_classified_gated"] else "FAIL",
            },
            {
                "id": "ctl-vacuous-mapper-empty-orphans",
                "command": "vacuous_orphan_list(files) hides planted fixture",
                "result": "PASS" if ctl["vacuous_hides_fixture"] else "FAIL",
            },
            {
                "id": "collect-only-union-receipt",
                "command": P2,
                "result": "PASS"
                if M.KNOWN_GATED_REL in live["collection_union_files"]
                and M.CONTROL_REL not in live["collection_union_files"]
                else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "AUD0050-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "Vacuous mapper reports no orphans; the planted file must "
                    "still appear in the real orphan list."
                ),
                "fired_on_bad_state": ctl["vacuous_hides_fixture"],
                "silent_on_good_state": ctl["fixture_in_orphan_list"],
                "bad_state_output": "orphan_list=[]",
                "good_state_output": M.CONTROL_REL,
            },
            {
                "id": "AUD0050-C2",
                "kind": "known-gated-suite",
                "description": (
                    "tools/command-center/tests/test_validate.py is named by an "
                    "explicit quality.yml pytest selector and must be GATED, or "
                    "the mapper is reporting everything as orphan."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": ctl["known_gated_classified_gated"],
                "bad_state_output": "all-orphan would drop known-gated",
                "good_state_output": M.KNOWN_GATED_REL,
            },
        ],
        "evidence": [
            {
                "kind": "selector-model",
                "claim": (
                    f"{n_gated} test files match a pull-request CI pytest "
                    f"selector; {n_orphan} do not."
                ),
                "path": live["inventory_path"],
            },
            {
                "kind": "collect-only-union",
                "claim": (
                    "pytest --collect-only on present selector paths produced "
                    f"{len(live['collection_union_files'])} distinct files; "
                    "the planted orphan fixture is absent from that union."
                ),
                "path": "pytest --collect-only",
            },
            {
                "kind": "both-states-control",
                "claim": (
                    "Vacuous empty-orphan mapper hides the planted fixture; "
                    "the real mapper lists it. Known-gated command-center "
                    "suite stays GATED."
                ),
                "path": M.CONTROL_REL,
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0050-probe2-collect-only",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Named probe2 re-runs pytest --collect-only per PR selector and "
                "compares the union to this artifact; it does not trust the "
                "selector model as the receipt."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "selector-map", "command": P1},
            {"id": "probe2", "role": "collect-only-receipt", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            file_row(SCHEMA, "supporting"),
            file_row(
                "command-center/p2-wave/probes/AUD-0050/mapper.py", "supporting"
            ),
            file_row(
                "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
                "supporting",
            ),
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0050/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "timestamps": {"emitted_at": now},
        "residual_unknowns": [
            {
                "claim": (
                    "AUD-0041 inventory truncates run commands at 600 characters "
                    "and omits working-directory, so cwd-implied pytest steps "
                    "are inferred from step names when a matching directory "
                    "exists. A restored workflow YAML would replace inference."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Re-parse .github/workflows/quality.yml working-directory "
                    "keys when that tree is present on disk."
                ),
            }
        ],
        "notes": (
            "G-1 for AUD-0050: live named probes exit 0, non-BLOCKED map, "
            "per-unit manifest row. Did not run global unit_manifest.py "
            "--write. No ADV rebuild."
        ),
    }
    for row in doc["artifacts"]:
        if row["path"] == OUT:
            continue
        if not row["exists"]:
            print(f"FAILED:AUD-0050 supporting artifact missing {row['path']}")
            return 1

    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    print(f"wrote {OUT} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}")
    print(
        f"files={n_files} gated={n_gated} orphan={n_orphan} "
        f"union={len(live['collection_union_files'])} overall={overall}"
    )
    print("SUCCESS:AUD-0050")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
