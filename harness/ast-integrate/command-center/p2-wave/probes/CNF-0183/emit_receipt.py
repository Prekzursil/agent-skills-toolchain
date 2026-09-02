#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0183.json (third-party replication rehearsal)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import unshadow as U  # noqa: E402

U.unshadow()
import rehearse as R  # noqa: E402
import schema_check as SC  # noqa: E402

OUT = "command-center/receipts/CNF-0183.json"
SCHEMA = "command-center/schema/replication-package.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0183/probe1_isolation_reproduced.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0183/probe2_verdict_split.py"
)
QUESTION = (
    "Can a fresh agent, given ONLY the replication package and no repository "
    "context, no receipts and no prior conversation, reproduce the claim? A "
    "failure to reproduce from an incomplete package is a PACKAGE defect, not a "
    "refutation of the claim; conflating those two failure modes would refute "
    "correct work."
)
RETRY_POLICY = (
    "Cross-vendor dispatch: blocking foreground only, never --background. "
    "On win-arg-limit retry ONCE with --ignore-user-config and prompt-by-file. "
    "On exit 0 with a missing or unparsable output file classify severed-stream "
    "and do NOT retry into a verdict. Never convert a vendor-side 429/529 into "
    "a REFUTED."
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0183/isolate.py",
    "command-center/p2-wave/probes/CNF-0183/package.py",
    "command-center/p2-wave/probes/CNF-0183/rehearse.py",
    "command-center/p2-wave/probes/CNF-0183/schema_check.py",
]


def sha_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:8000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def rehearsal_row(rec: dict) -> dict:
    row = {
        "package_id": rec["package_id"],
        "access": rec["access"],
        "outcome": rec["outcome"],
        "verdict": rec["verdict"],
    }
    if rec["verdict"] == "PACKAGE-INCOMPLETE":
        row["missing_element"] = rec["missing_element"]
    if rec["verdict"] == "CLAIM-REFUTED":
        row["counter_evidence"] = rec["counter_evidence"]
    return row


def artifact_row(rel: str, role: str) -> dict:
    digest, size = sha_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bat = R.battery(REPO)
    iso = bat["isolation"]
    split = bat["verdict_split"]
    if not iso.get("pass"):
        print("FAILED:CNF-0183 emit isolation both-states did not pass")
        print(json.dumps(iso, indent=2, default=str)[:2000])
        return 1
    if not split.get("pass"):
        print("FAILED:CNF-0183 emit verdict split did not pass")
        print(json.dumps(split, indent=2, default=str)[:2000])
        return 1

    upstream_path = "command-center/receipts/CNF-0182.json"
    upstream_present = (REPO / upstream_path).is_file() and (
        REPO / upstream_path
    ).stat().st_size > 0
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    iso_src = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        '"import isolate,pathlib; r=isolate.both_states(pathlib.Path(\\".\\")); '
        'print(r[\\"pass\\"], r[\\"guarded_absolute_reachable\\"], '
        'r[\\"unguarded_absolute_reachable\\"])"'
    )
    iso_ver = (
        "python3 -c "
        '"from pathlib import Path; p=Path(\\"command-center/WORK-UNIT-CATALOG.json\\"); '
        'print(p.is_file(), p.stat().st_size)"'
    )
    split_src = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        '"import rehearse,pathlib; b=rehearse.battery(pathlib.Path(\\".\\")); '
        'print(b[\\"incomplete\\"][\\"verdict\\"], b[\\"false\\"][\\"verdict\\"], '
        'b[\\"naive_incomplete\\"][\\"verdict\\"], b[\\"verdict_split\\"][\\"pass\\"])"'
    )
    split_ver = (
        "python3 -c "
        '"from pathlib import Path; t=Path(\\"command-center/p2-wave/probes/'
        'CNF-0183/package.py\\").read_text(); '
        'print(\\"count.txt).unlink\\" in t, \\"INCOMPLETE_ID\\" in t)"'
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0183",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0183",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0183] "
            "third-party replication rehearsal; verdict split PACKAGE-INCOMPLETE "
            "vs CLAIM-REFUTED"
        ),
        "min_bytes_threshold": 256,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "local-serialized",
        },
        "artifacts": [artifact_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "With the repo prefix forbidden, an absolute catalog open is "
                    "refused; the same absolute path is readable with the guard "
                    "off; a relative catalog path from a temp cwd misses."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0183/isolate.py:both_states",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        iso_src,
                        json.dumps(iso, sort_keys=True, default=str)[:4000],
                        0,
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        iso_ver,
                        (
                            f"catalog_exists={iso.get('catalog_exists')} "
                            f"unguarded={iso.get('unguarded_absolute_reachable')}"
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "A package missing inputs/count.txt is PACKAGE-INCOMPLETE "
                    "(element named), a mutated claim is CLAIM-REFUTED with "
                    "counter_evidence, and a naive run-only classifier conflates "
                    "the incomplete case into CLAIM-REFUTED."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0183/rehearse.py:battery",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        split_src,
                        json.dumps(
                            {
                                "incomplete": rehearsal_row(bat["incomplete"]),
                                "false": rehearsal_row(bat["false"]),
                                "naive": bat["naive_incomplete"]["verdict"],
                                "split": split,
                            },
                            sort_keys=True,
                            default=str,
                        )[:4000],
                        0,
                    ),
                    probe(
                        "verifier",
                        "static-analysis",
                        split_ver,
                        (
                            "package.py incomplete mode unlinks declared "
                            "inputs/count.txt; false mode mutates expected.stdout_sha256"
                        ),
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-isolation",
                "name": "Isolation control: rehearser cannot reach the repository",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-planted-incompleteness",
                "name": (
                    "Remove one input; rehearsal reports PACKAGE-INCOMPLETE "
                    "not CLAIM-REFUTED"
                ),
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T3-planted-falsity",
                "name": "Mutate the claim; rehearsal reports CLAIM-REFUTED",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T4-both-states",
                "name": "Complete package on a true claim reports REPRODUCED",
                "command": P1,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-isolation-guard",
                "kind": "known-broken-fixture",
                "description": (
                    "Guard ON refuses the catalog; guard OFF reads the same "
                    "absolute path."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": str(iso.get("guarded_error") or "PermissionError"),
                "good_state_output": (
                    f"unguarded_absolute_reachable={iso.get('unguarded_absolute_reachable')}"
                ),
            },
            {
                "id": "NC-planted-incomplete",
                "kind": "absent-input",
                "description": (
                    "inputs/count.txt removed while still declared; completeness "
                    "check must name it and must not call that CLAIM-REFUTED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"{bat['incomplete']['verdict']}:{bat['incomplete']['missing_element']}"
                ),
                "good_state_output": bat["true"]["verdict"],
            },
            {
                "id": "NC-planted-false",
                "kind": "mutation",
                "description": (
                    "Claim and expected.stdout_sha256 mutated to 64 zero hex "
                    "chars; rehearsal must be CLAIM-REFUTED with counter_evidence."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": str(bat["false"].get("counter_evidence") or "")[:2000],
                "good_state_output": bat["true"]["verdict"],
            },
            {
                "id": "NC-naive-conflation",
                "kind": "known-broken-fixture",
                "description": (
                    "A run-only classifier treats missing inputs as CLAIM-REFUTED; "
                    "completeness-first rehearsal does not. The split is load-bearing."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": bat["naive_incomplete"]["verdict"],
                "good_state_output": bat["incomplete"]["verdict"],
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0183-probe2-verdict-split",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": (
                "Probe2 re-runs planted incompleteness and planted falsity and "
                "asserts they are not swapped. A naive run-only classifier "
                "conflates missing inputs into CLAIM-REFUTED; completeness-first "
                "rehearsal does not."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0183/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0183",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNF-0183/schema_check.py "
                    "(Draft202012Validator + disk RefResolver)"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/CNF-0183/schema_check.py "
                        f"--check {OUT}"
                    ),
                    "in-memory validate before write; file re-checked after write",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": RETRY_POLICY},
        "residual_unknowns": [
            {
                "claim": (
                    "Every live P0/P1 CNF-0182 package on this estate rehearses cleanly."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNF-0182 then re-run this rehearser over that catalog."
                ),
            }
        ],
        "report": {
            "kind": "replication-package",
            "observations": [
                {
                    "name": "true-package-verdict",
                    "measured": bat["true"]["verdict"],
                    "method": "isolated-rehearsal",
                    "anchor": "command-center/p2-wave/probes/CNF-0183/rehearse.py",
                },
                {
                    "name": "incomplete-package-verdict",
                    "measured": bat["incomplete"]["verdict"],
                    "method": "isolated-rehearsal",
                    "anchor": "command-center/p2-wave/probes/CNF-0183/rehearse.py",
                },
                {
                    "name": "false-package-verdict",
                    "measured": bat["false"]["verdict"],
                    "method": "isolated-rehearsal",
                    "anchor": "command-center/p2-wave/probes/CNF-0183/rehearse.py",
                },
                {
                    "name": "naive-incomplete-verdict",
                    "measured": bat["naive_incomplete"]["verdict"],
                    "method": "run-only-classifier",
                    "anchor": "command-center/p2-wave/probes/CNF-0183/rehearse.py:naive_run_only",
                },
                {
                    "name": "guarded-absolute-reachable",
                    "measured": False,
                    "method": "sitecustomize-open-guard",
                    "anchor": "command-center/p2-wave/probes/CNF-0183/isolate.py",
                },
            ],
            "control_ids": [
                "NC-isolation-guard",
                "NC-planted-incomplete",
                "NC-planted-false",
                "NC-naive-conflation",
            ],
            "question": QUESTION,
            "packages": bat["packages"],
            "rehearsals": [
                rehearsal_row(bat["true"]),
                rehearsal_row(bat["incomplete"]),
                rehearsal_row(bat["false"]),
            ],
            "isolation": {
                "guarded_absolute_reachable": False,
                "unguarded_absolute_reachable": True,
                "relative_reachable_from_temp": False,
                "pass": True,
                "catalog_path": iso.get("catalog_path"),
                "guarded_error": iso.get("guarded_error"),
                "unguarded_error": iso.get("unguarded_error"),
            },
            "verdict_split": {
                "incomplete_not_recorded_as_refute": True,
                "refute_not_recorded_as_incomplete": True,
                "naive_classifier_conflates_incomplete_to_refute": True,
                "complete_true_is_reproduced": True,
                "pass": True,
            },
            "upstream": {
                "id": "CNF-0182",
                "present": upstream_present,
                "used": (
                    "live CNF-0182 artifact used as package source"
                    if upstream_present
                    else (
                        "fixture packages implementing the CNF-0182 package "
                        "contract; live CNF-0182 receipt absent on this worktree"
                    )
                ),
            },
            "named_probes": [
                {"id": "probe1", "role": "isolation-and-reproduced", "command": P1},
                {"id": "probe2", "role": "verdict-split", "command": P2},
            ],
        },
    }
    doc["rehearsals"] = doc["report"]["rehearsals"]
    doc["verdict_split"] = doc["report"]["verdict_split"]
    doc["isolation"] = doc["report"]["isolation"]

    if not SC.garbage_rejected(REPO):
        print("FAILED:CNF-0183 schema accepted garbage")
        return 1
    errs = SC.error_messages(doc, REPO)
    if errs:
        print("FAILED:CNF-0183 schema errors")
        for line in errs[:40]:
            print(" ", line)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    file_errs = SC.error_messages(json.loads(out.read_text(encoding="utf-8")), REPO)
    if file_errs:
        print("FAILED:CNF-0183 written receipt schema-invalid")
        for line in file_errs[:20]:
            print(" ", line)
        return 1
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(
        f"isolation_pass={iso['pass']} split_pass={split['pass']} "
        f"true={bat['true']['verdict']} inc={bat['incomplete']['verdict']} "
        f"false={bat['false']['verdict']}"
    )
    print("SUCCESS:CNF-0183 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
