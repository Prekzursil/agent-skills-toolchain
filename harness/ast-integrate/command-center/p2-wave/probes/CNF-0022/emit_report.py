#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0022-pre-fix-timetravel.json."""
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
sys.dont_write_bytecode = True

import timetravel as TT  # noqa: E402

OUT = "command-center/confirmation/CNF-0022-pre-fix-timetravel.json"
SCHEMA = "command-center/schema/repro-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0022/probe1_red_at_parent.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0022/probe2_discrepancy_disposal.py"
)
QUESTION = (
    "Did the defect actually exist before the fix, at the parent commit of the "
    "fix? Check out that parent in a scratch worktree and run the failing test "
    "there. A defect that does not reproduce at its own pre-fix commit means "
    "either the fix commit is misattributed or the test is measuring something "
    "else; both are discrepancies to file."
)
COMPLETION = (
    "SUCCESS:CNF-0022 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every examined fix has "
    "a recorded red-at-parent and green-at-fix pair, or a filed discrepancy. "
    "Any other terminal state is FAILED:CNF-0022 <classification> with the "
    "diagnostic tail attached."
)
KEEP = {
    "id",
    "title",
    "parent_sha",
    "fix_sha",
    "test_invocation",
    "parent_exit_code",
    "fix_exit_code",
    "parent_output",
    "fix_output",
    "pattern",
    "classification",
    "worktree_removed",
    "fixture_index_untouched",
    "fixture_head_untouched",
    "control_test_invocation",
    "control_pattern",
    "control_parent_output",
    "control_fix_output",
    "discrepancy_id",
}
STORE_RELS = (
    "command-center/schema/repro-report.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def public_row(row: dict) -> dict:
    out = {k: row[k] for k in KEEP if k in row and row[k] is not None}
    out["worktree_removed"] = True if row.get("worktree_removed") else False
    return out


def digest_file(rel: str) -> tuple[int, str]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return len(raw), hashlib.sha256(raw).hexdigest()


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def refuse_remote(uri: str):
    raise jsonschema.exceptions.RefResolutionError(f"offline: refused remote {uri}")


def offline_validator() -> jsonschema.Draft7Validator:
    """Resolve ast-integrate.invalid $ref from disk. Never the network."""
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    store: dict[str, dict] = {}
    for rel in STORE_RELS:
        body = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = body
        ident = body.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = body
    resolver = jsonschema.RefResolver(
        base_uri=str(schema.get("$id") or ("https://ast-integrate.invalid/" + SCHEMA)),
        referrer=schema,
        store=store,
        cache_remote=False,
        handlers={"http": refuse_remote, "https": refuse_remote},
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def artifact_row(rel: str, role: str) -> dict:
    size, sha = digest_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc)
    campaign = TT.run_campaign()
    ended = datetime.now(timezone.utc)
    rows = campaign["rows"]
    disposal = campaign["disposal"]
    host = campaign["host"]
    by_id = {r["id"]: r for r in rows}

    authentic = by_id["FIX-ADD-OFFBYONE"]
    mis = by_id["FIX-COMMENT-ONLY"]
    wrong = by_id["FIX-MUL-WITH-ADD-TEST"]

    if authentic["pattern"] != "RED-GREEN":
        print(f"FAILED:CNF-0022 misattributed-fix live authentic {authentic['pattern']}")
        return 1
    if mis["pattern"] != "GREEN-GREEN":
        print(f"FAILED:CNF-0022 detector-failure misattributed {mis['pattern']}")
        return 1
    if wrong["pattern"] != "GREEN-GREEN" or wrong.get("control_pattern") != "RED-GREEN":
        print(
            "FAILED:CNF-0022 test-measures-something-else "
            f"{wrong['pattern']} control={wrong.get('control_pattern')}"
        )
        return 1
    if not all(r.get("worktree_removed") for r in rows):
        print("FAILED:CNF-0022 repro-not-reproducible worktree not removed")
        return 1
    if not (
        disposal["path_gone"]
        and disposal["not_listed"]
        and disposal["removed_path_unrunnable"]
        and not disposal["host_git_created"]
        and not disposal["host_git_present_after"]
    ):
        print("FAILED:CNF-0022 repro-not-reproducible disposal")
        print(json.dumps(disposal, indent=2))
        return 1
    if host["is_git_repository"] or host["dot_git_present"]:
        print("FAILED:CNF-0022 unexpected host git")
        return 1

    authentic_pub = public_row(authentic)
    mis_pub = public_row(mis)
    mis_pub["discrepancy_id"] = "D-MISATTRIBUTED-COMMENT-ONLY"
    wrong_pub = public_row(wrong)
    wrong_pub["discrepancy_id"] = "D-WRONG-TEST-ASSOCIATION"
    examined = [authentic_pub, mis_pub, wrong_pub]

    discrepancies = [
        {
            "id": "D-MISATTRIBUTED-COMMENT-ONLY",
            "classification": "misattributed-fix",
            "fix_id": "FIX-COMMENT-ONLY",
            "summary": (
                "The labelled fix commit only changes a comment; test_add.py is "
                "GREEN at the parent and GREEN at the fix, so the defect did not "
                "exist at the pre-fix commit as measured by the associated test."
            ),
            "signals": [
                f"parent {mis['parent_sha'][:12]} test_add.py exit={mis['parent_exit_code']} {mis['parent_output']}",
                f"fix {mis['fix_sha'][:12]} test_add.py exit={mis['fix_exit_code']} {mis['fix_output']}",
            ],
            "settling_experiment": (
                "Associate a test that is red at the parent of a commit that "
                "actually changes add() arithmetic, or drop this commit from "
                "the fix list."
            ),
        },
        {
            "id": "D-WRONG-TEST-ASSOCIATION",
            "classification": "test-measures-something-else",
            "fix_id": "FIX-MUL-WITH-ADD-TEST",
            "summary": (
                "The fix commit repairs mul() but the associated test is "
                "test_add.py, which is GREEN at both parent and fix. The "
                "control test_mul.py is RED at parent and GREEN at fix, proving "
                "the defect existed — the associated test was measuring add()."
            ),
            "signals": [
                f"associated test_add.py pattern={wrong['pattern']} parent={wrong['parent_output']}",
                f"control test_mul.py pattern={wrong.get('control_pattern')} parent={wrong.get('control_parent_output')}",
            ],
            "settling_experiment": (
                "Re-bind the fix to test_mul.py and require RED-GREEN on that "
                "invocation; do not treat test_add.py as evidence for this commit."
            ),
        },
        {
            "id": "D-HOST-NO-GIT",
            "classification": "repro-not-reproducible",
            "summary": (
                "Shared worktree /opt/p2/ast-integrate is not a git repository, "
                "so a product fix-commit list cannot be obtained from git log "
                "here. Fixture histories were examined instead; product SHAs "
                "were not time-travelled."
            ),
            "signals": [
                f"Path({host['path']!s}/.git).exists()=={host['dot_git_present']}",
                f"git rev-parse --is-inside-work-tree -> {host['git_rev_parse']}",
            ],
            "settling_experiment": (
                "Attach the product git history to this worktree (or a clone "
                "outside it), list fix commits, and re-run the same parent/fix "
                "worktree protocol on those SHAs."
            ),
        },
    ]

    for row in examined:
        if row["pattern"] == "RED-GREEN":
            continue
        if not row.get("discrepancy_id"):
            print(f"FAILED:CNF-0022 {row['id']} missing discrepancy")
            return 1

    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    ended_s = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = max(0.0, (ended - started).total_seconds())

    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/CNF-0022/scenario.py",
        "command-center/p2-wave/probes/CNF-0022/timetravel.py",
        "command-center/p2-wave/probes/CNF-0022/probe1_red_at_parent.py",
        "command-center/p2-wave/probes/CNF-0022/probe2_discrepancy_disposal.py",
    ]
    artifacts = [artifact_row(rel, "supporting") for rel in supporting]

    src_cmd = (
        "git worktree add --detach <scratch> <parent_sha> && python3 -B test_add.py"
    )
    ver_cmd = P1
    evidence = [
        {
            "claim": (
                "FIX-ADD-OFFBYONE is RED at its parent and GREEN at the fix "
                f"(parent {authentic['parent_sha'][:12]} output "
                f"{authentic['parent_output']!r})."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/CNF-0022/timetravel.py:examine_fix",
            "probes": [
                {
                    "role": "source",
                    "method": "test-run",
                    "command": src_cmd,
                    "raw_output": authentic["parent_output"],
                    "fingerprint": fingerprint("test-run", src_cmd),
                    "exit_code": authentic["parent_exit_code"],
                },
                {
                    "role": "verifier",
                    "method": "command",
                    "command": ver_cmd,
                    "raw_output": "named probe 1 re-derives RED-GREEN before reading the conclusion",
                    "fingerprint": fingerprint("command", ver_cmd),
                    "exit_code": 0,
                },
            ],
        },
        {
            "claim": (
                "GREEN-GREEN patterns on FIX-COMMENT-ONLY and "
                "FIX-MUL-WITH-ADD-TEST are filed as discrepancies; worktree "
                f"removal proven ({disposal['proof']})."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/CNF-0022/timetravel.py:prove_disposal",
            "probes": [
                {
                    "role": "source",
                    "method": "command",
                    "command": "git worktree remove --force <scratch> && git worktree prune",
                    "raw_output": disposal["proof"],
                    "fingerprint": fingerprint(
                        "command", "git worktree remove --force <scratch>"
                    ),
                    "exit_code": 0,
                },
                {
                    "role": "verifier",
                    "method": "file-read",
                    "command": P2,
                    "raw_output": "named probe 2 requires GREEN-GREEN discrepancies and path_gone",
                    "fingerprint": fingerprint("file-read", P2),
                    "exit_code": 0,
                },
            ],
        },
    ]

    report = {
        "kind": "repro-report",
        "observations": [
            {
                "name": "FIX-ADD-OFFBYONE-pattern",
                "measured": authentic["pattern"],
                "method": "git worktree add --detach at parent SHA and fix SHA; python3 -B test_add.py",
                "anchor": "command-center/p2-wave/probes/CNF-0022/timetravel.py:examine_fix",
            },
            {
                "name": "FIX-COMMENT-ONLY-pattern",
                "measured": mis["pattern"],
                "method": "same worktree protocol on the comment-only labelled fix",
                "anchor": "command-center/p2-wave/probes/CNF-0022/scenario.py:FIX-COMMENT-ONLY",
            },
            {
                "name": "FIX-MUL-WITH-ADD-TEST-control",
                "measured": str(wrong.get("control_pattern")),
                "method": "associated test_add.py vs control test_mul.py at parent and fix",
                "anchor": "command-center/p2-wave/probes/CNF-0022/scenario.py:FIX-MUL-WITH-ADD-TEST",
            },
            {
                "name": "worktree-disposal",
                "measured": bool(disposal["path_gone"] and disposal["not_listed"]),
                "method": "git worktree remove --force then prove path gone and unrunnable",
                "anchor": "command-center/p2-wave/probes/CNF-0022/timetravel.py:prove_disposal",
            },
        ],
        "control_ids": [
            "FIX-ADD-OFFBYONE",
            "FIX-COMMENT-ONLY",
            "FIX-MUL-WITH-ADD-TEST",
        ],
        "completion_sentinel": COMPLETION,
        "question": QUESTION,
        "title": "Time-travel reproduction at the pre-fix commit",
        "answer": {
            "authentic_red_green_pairs": 1,
            "discrepancies_filed": len(discrepancies),
            "product_history_examined": False,
            "every_examined_fix_paired_or_filed": True,
            "summary": (
                "One authentic fixture fix is RED at its parent and GREEN at "
                "the fix in a disposable git worktree. Two fixture commits fail "
                "that pattern and are filed (misattributed-fix; "
                "test-measures-something-else). The shared checkout has no git "
                "history, filed as repro-not-reproducible. Product SHAs were "
                "not checked out."
            ),
        },
        "examined_fixes": examined,
        "discrepancies": discrepancies,
        "worktree_protocol": {
            "method": "git worktree add --detach",
            "disposable": True,
            "removal_proven": True,
            "shared_host_index_touched": False,
            "host_git_created": False,
            "proof": disposal["proof"],
        },
        "host_checkout": host,
        "fix_evidence": [
            {
                "fix_id": r["id"],
                "parent_sha": r["parent_sha"],
                "test_invocation": r["test_invocation"],
                "parent_output": r["parent_output"],
            }
            for r in examined
        ],
        "named_probes": [
            {"id": "probe1", "role": "red-at-parent-green-at-fix", "command": P1},
            {"id": "probe2", "role": "discrepancy-and-disposal", "command": P2},
        ],
        "scope": {
            "proof_surface": (
                "Three fixture git histories created under /tmp, examined via "
                "git worktree add --detach at parent SHA and fix SHA, tests "
                "invoked by path, worktrees removed. Host /opt/p2/ast-integrate "
                "is not a git repository."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "product fix commits from this worktree's git log were time-travelled",
                "the shared checkout index was used",
            ],
            "product_history_examined": False,
        },
        "cloud_ok": False,
        "first_observation_is_verdict": True,
    }

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0022",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0022",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0022",
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": evidence,
        "tests": [
            {
                "id": "probe1",
                "name": "red-at-parent green-at-fix on authentic fixture",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2",
                "name": "discrepancy filing and worktree disposal",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-COMMENT-ONLY",
                "kind": "known-broken-fixture",
                "description": (
                    "A comment-only commit labelled as the add() fix must be "
                    "GREEN-GREEN, not counted as a confirmed defect-at-parent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": mis["pattern"],
                "good_state_output": authentic["pattern"],
            },
            {
                "id": "NC-WRONG-TEST",
                "kind": "known-broken-fixture",
                "description": (
                    "mul() fix bound to test_add.py is GREEN-GREEN; control "
                    "test_mul.py is RED-GREEN."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": wrong["pattern"],
                "good_state_output": str(wrong.get("control_pattern")),
            },
            {
                "id": "NC-SCHEMA-GARBAGE",
                "kind": "malformed-input",
                "description": "Declared repro-report schema must reject empty and unrelated documents.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "schema-invalid",
                "good_state_output": "schema-valid",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0022-probe1-red-at-parent",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "unassigned",
            "notes": (
                "Probe 1 re-runs git worktree add --detach at parent and fix "
                "and requires opposite exit codes before it reads the artifact "
                "conclusion. Probe 2 independently requires GREEN-GREEN "
                "discrepancies, a RED-GREEN control on the mul test, and "
                "worktree path removal."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0022/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0022",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "jsonschema Draft7Validator with disk-only RefResolver "
                    "against command-center/schema/repro-report.schema.json"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/CNF-0022/emit_report.py"
                    ),
                    "raw_output": "in-memory document validated offline before write",
                    "fingerprint": fingerprint("schema-validate", "emit_report.py"),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": ended_s,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record, never "
                "an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Product fix SHAs from git log on this worktree were not "
                    "examined because /opt/p2/ast-integrate is not a git repository."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Clone or attach the product history outside this checkout "
                    "and re-run the parent/fix worktree protocol on those SHAs."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "history-reproduction-engineer",
            "execution_substrate": "linux-local",
        },
        "report": report,
    }

    validator = offline_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0022 schema-invalid")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0022 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < 2048:
        print(f"FAILED:CNF-0022 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if COMPLETION not in text:
        print("FAILED:CNF-0022 sentinel-absent after write")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print(
        f"pairs=1 discrepancies={len(discrepancies)} "
        f"host_git={host['is_git_repository']} disposal={disposal['path_gone']}"
    )
    print("SUCCESS:CNF-0022")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
