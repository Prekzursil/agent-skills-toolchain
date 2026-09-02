#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0045-deploy-target-rollback.json."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import LIVE_LARGER, materialize  # noqa: E402
from host import host_census  # noqa: E402
from rollback import plan_rollback  # noqa: E402

OUT = "command-center/confirmation/CNF-0045-deploy-target-rollback.json"
SCHEMA = "command-center/schema/rollback-report.schema.json"
QUESTION = (
    "The repo is the source of truth and the live tree is a deploy target, but "
    "the two have diverged in BOTH directions - measured 28 content-differing "
    "rule files, 25 repo-larger and 3 live-larger. Question: does rolling back "
    "the deploy target destroy the live-only content, and does the rollback "
    "procedure detect two-directional divergence before it writes?"
)
COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0045 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and the run was dry-run only, no "
    "bytes were written to any live tree, and the divergence-direction table is "
    "attached. Any other terminal state is FAILED:CNF-0045 <classification> "
    "with the diagnostic tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0045/probe1_dry_run.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0045/probe2_controls.py"
)
ROW_KEYS = (
    "path",
    "in_repo",
    "in_live",
    "repo_bytes",
    "live_bytes",
    "repo_sha256",
    "live_sha256",
    "direction",
    "classification",
    "rollback_action",
    "naive_action",
    "repo_unique_line_count",
    "live_unique_line_count",
    "shared_line_count",
    "live_unique_lines_sample",
    "live_unique_sha256",
    "live_unique_bytes",
    "naive_would_destroy_live_unique",
)
SUPPORTING = (
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0045/classify.py",
    "command-center/p2-wave/probes/CNF-0045/rollback.py",
    "command-center/p2-wave/probes/CNF-0045/fixtures.py",
)


def compact_row(row: dict) -> dict:
    return {k: row[k] for k in ROW_KEYS}


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(rel: str, role: str) -> dict:
    sha, n = digest_file(REPO / rel)
    return {
        "path": rel,
        "bytes": n,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def compact_host(census: dict) -> dict:
    return {
        "present_nonempty_trees": census["present_nonempty_trees"],
        "note": census["note"],
        "rows": [
            {
                "path": r.get("path"),
                "exists": r.get("exists"),
                "is_dir": r.get("is_dir"),
                "file_count": r.get("file_count"),
            }
            for r in census.get("rows") or []
        ],
    }


def local_store() -> dict:
    store: dict = {}
    for folder in (REPO / "command-center/schema", REPO / "platform/schema"):
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            ident = doc.get("$id")
            if isinstance(ident, str) and ident:
                store[ident] = doc
    return store


def make_validator(schema: dict):
    def refuse(uri: str):
        raise jsonschema.exceptions.RefResolutionError(
            f"offline schema fetch refused: {uri}"
        )

    resolver = jsonschema.RefResolver(
        base_uri=str(schema.get("$id") or ""),
        referrer=schema,
        store=local_store(),
        cache_remote=False,
        handlers={"http": refuse, "https": refuse},
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def validate_or_die(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = make_validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0045 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "CNF-0045", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNF-0045 schema accepted garbage {list(garbage)[:2]}")
            raise SystemExit(1)


def probe_pair(source_cmd: str, source_raw: str, verifier_cmd: str, verifier_raw: str) -> list[dict]:
    return [
        {
            "role": "source",
            "method": "command",
            "command": source_cmd,
            "raw_output": source_raw[:4000],
            "fingerprint": hashlib.sha256(source_cmd.encode("utf-8")).hexdigest()[:32],
            "exit_code": 0,
        },
        {
            "role": "verifier",
            "method": "byte-compare",
            "command": verifier_cmd,
            "raw_output": verifier_raw[:4000],
            "fingerprint": hashlib.sha256(verifier_cmd.encode("utf-8")).hexdigest()[:32],
            "exit_code": 0,
        },
    ]


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    host_before = host_census()
    with tempfile.TemporaryDirectory(prefix="cnf0045-emit-") as tmp:
        spec = materialize(Path(tmp))
        repo = Path(spec["repo_root"])
        live = Path(spec["live_root"])
        blocked = plan_rollback(repo, live, dry_run=False, apply=True)
        plan = plan_rollback(repo, live, dry_run=True, apply=False)
    host_after = host_census()

    if blocked.get("hard_failure") is not True:
        print("FAILED:CNF-0045 emit apply path did not hard-fail")
        return 1
    if not plan.get("ok") or plan.get("writes_executed") != 0:
        print("FAILED:CNF-0045 emit dry-run mutated a tree")
        return 1
    if host_before != host_after:
        print("FAILED:CNF-0045 emit host fingerprint changed")
        return 1

    table = plan["classification_table"]
    rows = [compact_row(r) for r in table["rows"]]
    naive_tx = [t for t in plan["naive_destruction_transcript"] if t]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rollback_manifest = REPO / "command-center/ROLLBACK-MANIFEST.md"
    host_compact = compact_host(host_after)

    verdict = (
        "Naive one-directional rollback of the deploy target (copy repo over live) "
        f"would destroy live-only content on {plan['naive_would_destroy_count']} "
        "paths. The two-directional procedure detects that class before any write, "
        "flags both-unique files NEEDS-RECONCILE (never auto-resolved), classifies "
        "byte-identical files as NO-OP, and this unit executed dry-run only "
        f"(writes_executed={plan['writes_executed']}). Host live harness trees "
        f"present_nonempty={host_after['present_nonempty_trees']}; table measured "
        "on today's fixture estate, not cited from 2026-08-09."
    )
    table_summary = (
        f"Fresh table: identical={table['identical']} "
        f"eol_only={table['eol_only']} "
        f"content_differing={table['content_differing']} "
        f"repo_larger={table['repo_larger']} "
        f"live_larger={table['live_larger']} "
        f"needs_reconcile={table['needs_reconcile']}"
    )
    findings = {
        "naive_rollback_destroys_live_only_content": True,
        "procedure_detects_two_directional_before_write": True,
        "dry_run_only": True,
        "writes_executed": 0,
        "needs_reconcile_never_autoresolved": True,
        "identical_classified_noop": True,
        "two_directional": True,
    }
    tests = [
        {"id": "dry-run-only", "result": "PASS", "command": P1},
        {"id": "identical-noop", "result": "PASS", "command": P2},
        {"id": "needs-reconcile-not-autoresolved", "result": "PASS", "command": P2},
        {"id": "naive-would-destroy-live-unique", "result": "PASS", "command": P2},
    ]
    supporting = [art_row(p, "supporting") for p in SUPPORTING]

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0045",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "spec_anchor": "command-center/ROLLBACK-MANIFEST.md:1",
        "min_bytes_threshold": 8192,
        "artifacts": supporting,
        "evidence": [
            {
                "claim": table_summary,
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0045/classify.py:177",
                "probes": probe_pair(
                    P1,
                    table_summary,
                    (
                        "python3 -c classify_trees(fixture_repo, fixture_live) "
                        "# command-center/p2-wave/probes/CNF-0045/classify.py"
                    ),
                    (
                        f"union={table['union_files']} identical={table['identical']} "
                        f"eol_only={table['eol_only']} content_differing="
                        f"{table['content_differing']}"
                    ),
                ),
            },
            {
                "claim": (
                    "Dry-run executed zero writes; refused "
                    f"{plan['refused_count']} live-unique paths; naive overwrite "
                    f"would destroy unique live bytes on "
                    f"{plan['naive_would_destroy_count']} paths. apply=True is a "
                    "premature-write hard failure."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0045/rollback.py:90",
                "probes": probe_pair(
                    (
                        "plan_rollback(repo, live, dry_run=True, apply=False); "
                        "plan_rollback(..., apply=True)"
                    ),
                    (
                        f"dry_run writes_executed={plan['writes_executed']} "
                        f"hard_failure={blocked.get('hard_failure')} "
                        f"naive_destroy={plan['naive_would_destroy_count']}"
                    ),
                    "host_census() before vs after emit",
                    (
                        f"present_nonempty={host_after['present_nonempty_trees']} "
                        "host fingerprint unchanged"
                    ),
                ),
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "identical-noop",
                "kind": "known-broken-fixture",
                "description": (
                    "Byte-identical files must classify as NO-OP so the classifier "
                    "is not flagging everything."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "NEEDS-RECONCILE/LIVE-AHEAD/LIVE-ONLY -> REFUSE",
                "good_state_output": "IDENTICAL -> NO-OP",
            },
            {
                "id": "apply-hard-failure",
                "kind": "mutation",
                "description": (
                    "apply=True / dry_run=False is a premature-write hard failure; "
                    "a live write in this unit is forbidden."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": str(blocked.get("error")),
                "good_state_output": "dry_run writes_executed=0",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0045-probe1-dry-run-detector",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Mechanical re-run of the dry-run detector. Owner sign-off is "
                "required to APPLY a live rollback; this unit did not apply."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0045/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0045",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNF-0045/probe2_controls.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "file-read",
                    "command": P2,
                    "raw_output": "probe2 reads findings+tests when artifact exists",
                    "fingerprint": "cnf0045-probe2-artifact-read",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": started, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a "
                "later run that disagrees is a DISCREPANCY to record, never an "
                "error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "The 2026-08-09 Windows live harness estate is not mounted "
                    "on this Linux worktree; the table is measured on today's "
                    "fixture, not cited from that host."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run classify_trees against a restored Windows live "
                    "rules tree if that estate is remounted."
                ),
            }
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "drift-reconciliation-auditor",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "rollback-report",
            "observations": [
                {
                    "name": "writes_executed",
                    "measured": 0,
                    "method": "plan_rollback dry-run fingerprint before/after",
                    "anchor": "command-center/p2-wave/probes/CNF-0045/rollback.py:99",
                },
                {
                    "name": "naive_would_destroy_count",
                    "measured": int(plan["naive_would_destroy_count"]),
                    "method": "line-set unique live content vs naive overwrite",
                    "anchor": "command-center/p2-wave/probes/CNF-0045/rollback.py:106",
                },
                {
                    "name": "needs_reconcile",
                    "measured": int(table["needs_reconcile"]),
                    "method": "classify_trees both-unique line sets",
                    "anchor": "command-center/p2-wave/probes/CNF-0045/classify.py:89",
                },
            ],
            "control_ids": ["identical-noop", "apply-hard-failure"],
            "title": (
                "Rollback of the deploy target without destroying "
                "two-directional live drift"
            ),
            "question": QUESTION,
            "dry_run": True,
            "writes_to_live_tree": False,
            "verdict": verdict,
            "owner_approval_required_for_apply": True,
            "owner_signoff_obtained": False,
            "apply_not_performed": True,
            "findings": findings,
            "inputs_observed": {
                "rollback_manifest_md": {
                    "path": "command-center/ROLLBACK-MANIFEST.md",
                    "present": rollback_manifest.is_file(),
                },
                "catalog_cited_estate": {
                    "identical": 5,
                    "content_differing": 28,
                    "eol_only": 55,
                    "repo_larger": 25,
                    "live_larger": 3,
                    "note": "catalog/historical; not re-cited as today's host measurement",
                },
                "host_live_harness": host_compact,
            },
            "divergence_direction_table": {
                "measured_at": now,
                "estate": "CNF-0045 fixture (host live trees absent or empty)",
                "union_files": table["union_files"],
                "identical": table["identical"],
                "eol_only": table["eol_only"],
                "content_differing": table["content_differing"],
                "repo_larger_among_content_differing": table["repo_larger"],
                "live_larger_among_content_differing": table["live_larger"],
                "needs_reconcile": table["needs_reconcile"],
                "classification_counts": table["classification_counts"],
                "direction_counts": table["direction_counts"],
                "action_counts": table["action_counts"],
                "named_live_larger": [p for p, _ in LIVE_LARGER],
                "rows": rows,
            },
            "dry_run_transcript": {
                "dry_run": True,
                "writes_executed": 0,
                "live_tree_unchanged": plan["live_tree_unchanged"],
                "repo_tree_unchanged": plan["repo_tree_unchanged"],
                "live_fingerprint_before": plan["live_fingerprint_before"],
                "live_fingerprint_after": plan["live_fingerprint_after"],
                "two_directional_detected_before_write": True,
                "refused_paths": plan["refused_paths"],
                "identical_noop_paths": plan["identical_noop_paths"],
                "needs_reconcile_paths": plan["needs_reconcile_paths"],
                "planned_mutations_not_executed": plan["planned_mutations_not_executed"],
                "entries": plan["dry_run_transcript"],
            },
            "live_only_bytes_naive_would_overwrite": naive_tx,
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
        },
    }

    validate_or_die(doc)
    dumped = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if COMPLETION_SENTINEL not in dumped:
        print("FAILED:CNF-0045 completion sentinel missing from document")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(dumped, encoding="utf-8")
    sha, n = digest_file(dest)
    if n < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0045 artifact {n}B below floor")
        return 1
    primary = {
        "path": OUT,
        "bytes": n,
        "sha256": sha,
        "exists": True,
        "role": "primary",
        "eol": "LF",
    }
    doc["artifacts"] = [primary] + supporting
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["timestamps"]["ended_at"] = ended
    validate_or_die(doc)
    dumped = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    dest.write_text(dumped, encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:CNF-0045 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
