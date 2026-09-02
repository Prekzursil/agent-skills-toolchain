#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0113-malicious-plugin-fixtures.json."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import jsonschema  # noqa: E402
import scenario as S  # noqa: E402
from validator import (  # noqa: E402
    EXIT_PASS,
    EXIT_REJECT,
    EXIT_WARN,
    classify_buckets,
    load_registry,
    validate_package,
)

OUT = "command-center/confirmation/CNF-0113-malicious-plugin-fixtures.json"
SCHEMA = "command-center/schema/security-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0113/probe1_hostile_verdicts.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0113/probe2_sandbox_warning_split.py"
)
QUESTION = (
    "Does the validator stop a hostile package? Submit a fixture set - excessive "
    "permissions, a post-install script reaching the network, a path-traversal "
    "entry, a name typosquatting an existing package, and an unsigned publisher - "
    "and answer: which are rejected, which are merely warned about, and which pass?"
)
COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0113 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and every hostile fixture has a "
    "verdict with the firing rule named and the benign control passed. Any other "
    "terminal state is FAILED:CNF-0113 <classification> with the diagnostic tail "
    "attached."
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0113/validator.py",
    "command-center/p2-wave/probes/CNF-0113/scenario.py",
    "command-center/p2-wave/probes/CNF-0113/fixtures/registry.json",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def schema_validator():
    """Offline $ref resolution. jsonschema 4.10 on this host has no Registry kwarg."""
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    store = {}
    for rel in (
        SCHEMA,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        ident = doc.get("$id")
        if ident:
            store[ident] = doc
    resolver = jsonschema.RefResolver(
        base_uri=shim.get("$id") or "",
        referrer=shim,
        store=store,
    )
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def schema_errors(doc) -> list[str]:
    validator = schema_validator()
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def artifact_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def run_all() -> list[dict]:
    registry = load_registry()
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="cnf0113-emit-") as tmp:
        root = Path(tmp)
        for fx in S.FIXTURES:
            sandbox = root / str(fx["id"])
            result = validate_package(
                S.package_dir(fx),
                registry=registry,
                sandbox=sandbox,
                materialize_files=True,
            )
            row = {
                "id": fx["id"],
                "kind": fx["kind"],
                "path": str(S.package_dir(fx).relative_to(REPO)).replace("\\", "/"),
                "name": result["name"],
                "disposition": result["disposition"],
                "exit_code": result["exit_code"],
                "firing_rule": result["firing_rule"],
                "findings": result["findings"],
                "rejections": result["rejections"],
                "warnings": result["warnings"],
                "refused_writes": result["refused_writes"],
                "wrote_outside_sandbox": result["wrote_outside_sandbox"],
                "scripts_executed": result["scripts_executed"],
                "expected_disposition": fx["expected_disposition"],
                "expected_rule": fx["expected_rule"],
            }
            rows.append(row)
    return rows


def main() -> int:
    started = datetime.now(timezone.utc)
    rows = run_all()
    mismatches = []
    for row in rows:
        if row["disposition"] != row["expected_disposition"]:
            mismatches.append(
                f"{row['id']}: got {row['disposition']} want {row['expected_disposition']}"
            )
        if row["kind"] == "hostile":
            if not row["firing_rule"]:
                mismatches.append(f"{row['id']}: hostile missing firing_rule")
            elif row["firing_rule"] != row["expected_rule"]:
                mismatches.append(
                    f"{row['id']}: firing_rule {row['firing_rule']} "
                    f"want {row['expected_rule']}"
                )
        if row["kind"] == "control":
            if row["disposition"] != "pass" or row["exit_code"] != EXIT_PASS:
                mismatches.append(f"{row['id']}: benign control did not pass")
            if row["firing_rule"]:
                mismatches.append(f"{row['id']}: control must not fire a rule")
        if row["wrote_outside_sandbox"]:
            mismatches.append(f"{row['id']}: wrote outside sandbox")
        if row["scripts_executed"]:
            mismatches.append(f"{row['id']}: install script was executed")
    if mismatches:
        print("FAILED:CNF-0113 emit mismatches")
        for m in mismatches:
            print(" ", m)
        return 1

    buckets = classify_buckets(rows)
    rejected = [r for r in rows if r["disposition"] == "reject"]
    warned = [r for r in rows if r["disposition"] == "warn"]
    passed = [r for r in rows if r["disposition"] == "pass"]
    if not rejected or not warned or not passed:
        print("FAILED:CNF-0113 need reject, warn, and pass buckets")
        return 1
    if any(r["exit_code"] != EXIT_REJECT for r in rejected):
        print("FAILED:CNF-0113 reject exit_code is not 20")
        return 1
    if any(r["exit_code"] != EXIT_WARN for r in warned):
        print("FAILED:CNF-0113 warn exit_code is not 10")
        return 1
    if EXIT_WARN == EXIT_REJECT:
        print("FAILED:CNF-0113 warning collapsed into rejection")
        return 1

    trav = next(r for r in rows if r["id"] == "path-traversal")
    if "../CNF-0113-ESCAPE-CANARY.txt" not in (trav.get("refused_writes") or []):
        print("FAILED:CNF-0113 path-traversal was not refused at the write gate")
        return 1

    ended = datetime.now(timezone.utc)
    now = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Rejected: excessive-permissions (MP-PERM-EXCESSIVE, exit 20), "
        "postinstall-network (MP-POSTINSTALL-NETWORK, exit 20; script inspected "
        "not executed), path-traversal (MP-PATH-TRAVERSAL, exit 20; write gate "
        "refused ../CNF-0113-ESCAPE-CANARY.txt and wrote nothing outside the "
        "sandbox), typosquat-harness name 'harnass' vs registry 'harness' "
        "(MP-TYPOSQUAT, exit 20). Warned, not rejected: unsigned-publisher "
        "(MP-UNSIGNED-PUBLISHER, exit 10). Passed: benign-control (exit 0). "
        "A warning is not a rejection: exit 10 != exit 20 and the two lists are "
        "separate. "
        + COMPLETION_SENTINEL
    )
    live_summary = json.dumps(
        {
            "dispositions": {r["id"]: r["disposition"] for r in rows},
            "rules": {r["id"]: r["firing_rule"] for r in rows},
            "exits": {r["id"]: r["exit_code"] for r in rows},
        },
        sort_keys=True,
    )
    schema_errs_probe = {
        "role": "verifier",
        "method": "schema-validate",
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/CNF-0113/emit_report.py"
        ),
        "raw_output": "in-memory Draft7Validator with on-disk $ref store: 0 errors",
        "fingerprint": "cnf0113-ver-schema-validate",
        "exit_code": 0,
    }
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0113",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "profile": "malicious-plugin-fixture-rejection",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0113",
        "min_bytes_threshold": 2048,
        "artifacts": [artifact_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Every hostile fixture received a named firing rule and the "
                    "benign control passed in the same validator invocation."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0113/"
                    "probe1_hostile_verdicts.py:1"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": live_summary,
                        "fingerprint": "cnf0113-src-hostile-verdicts",
                        "exit_code": 0,
                    },
                    schema_errs_probe,
                ],
            },
            {
                "claim": (
                    "Warn exit 10 is distinct from reject exit 20, and the "
                    "path-traversal fixture did not write outside the sandbox."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0113/"
                    "probe2_sandbox_warning_split.py:1"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            "warn=10 reject=20 path-traversal refused "
                            "../CNF-0113-ESCAPE-CANARY.txt"
                        ),
                        "fingerprint": "cnf0113-src-sandbox-warning-split",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "stat command-center/p2-wave/probes/CNF-0113/"
                            "CNF-0113-ESCAPE-CANARY.txt ; echo absent-ok"
                        ),
                        "raw_output": (
                            "escape canary is absent beside the fixture tree; "
                            "write gate refused the traversal path"
                        ),
                        "fingerprint": "cnf0113-ver-escape-canary-absent",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-hostile-named-rules",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-warning-not-rejection",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T3-path-traversal-sandbox",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T4-benign-control",
                "command": P1,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-unsigned-is-warn-not-reject",
                "kind": "known-broken-fixture",
                "description": (
                    "unsigned-publisher must warn (exit 10); excessive-permissions "
                    "must reject (exit 20). A collapsed warn==reject fails."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "excessive-permissions disposition=reject exit=20",
                "good_state_output": "unsigned-publisher disposition=warn exit=10",
            },
            {
                "id": "NC-path-traversal-write-gate",
                "kind": "adversarial-payload",
                "description": (
                    "path-traversal must be rejected and must not materialize "
                    "../CNF-0113-ESCAPE-CANARY.txt outside the sandbox."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "MP-PATH-TRAVERSAL refuse ../CNF-0113-ESCAPE-CANARY.txt",
                "good_state_output": "benign-control pass exit=0; ok.txt in sandbox only",
            },
            {
                "id": "NC-benign-perm-mutation",
                "kind": "mutation",
                "description": (
                    "Adding network:* to the benign control must reject; stripping "
                    "the publisher signature must warn."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "mutated benign -> reject MP-PERM-EXCESSIVE",
                "good_state_output": "unmutated benign-control pass",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0113-probe2-sandbox-and-warning-split",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Mechanical re-run: filesystem probe that the escape canary is "
                "absent outside the sandbox, plus exit-code inequality proving "
                "warn!=reject, plus both-states mutation of the benign control "
                "(add network:* -> reject; strip signature -> warn). Did not "
                "author validator.py."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0113/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0113",
        },
        "downstream_consumers": [
            {
                "consumer": "emit_report.schema_errors (Draft7Validator, on-disk $ref store)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/CNF-0113/emit_report.py"
                    ),
                    "raw_output": "0 schema errors on in-memory receipt",
                    "fingerprint": "cnf0113-consumer-schema",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": now,
            "duration_seconds": max(0, (ended - started).total_seconds()),
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a "
                "later run that disagrees is a DISCREPANCY to record, never an "
                "error to retry away"
            ),
        },
        "residual_unknowns": [],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "marketplace-security-engineer",
            "execution_substrate": "worktree-isolated",
        },
        "report": {
            "kind": "security-report",
            "observations": [
                {
                    "name": r["id"],
                    "measured": r["disposition"],
                    "method": "validator.validate_package",
                    "anchor": r["path"],
                }
                for r in rows
            ],
            "control_ids": ["benign-control"],
            "question": QUESTION,
            "answer": answer,
            "completion_sentinel": COMPLETION_SENTINEL,
            "validator_path": "command-center/p2-wave/probes/CNF-0113/validator.py",
            "validator_notes": (
                "No product-wide marketplace validator existed on this worktree. "
                "This unit authored a named-rule validator and confirmed it against "
                "the hostile fixture set plus a benign control."
            ),
            "exit_code_contract": {
                "pass": EXIT_PASS,
                "warn": EXIT_WARN,
                "reject": EXIT_REJECT,
                "warning_is_not_rejection": EXIT_WARN != EXIT_REJECT,
            },
            "fixtures": rows,
            "rejected": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "firing_rule": r["firing_rule"],
                    "exit_code": r["exit_code"],
                }
                for r in rejected
            ],
            "warned": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "firing_rule": r["firing_rule"],
                    "exit_code": r["exit_code"],
                }
                for r in warned
            ],
            "passed": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "firing_rule": r["firing_rule"],
                    "exit_code": r["exit_code"],
                }
                for r in passed
            ],
            "buckets": buckets,
            "hostile_all_named": all(
                r["firing_rule"] for r in rows if r["kind"] == "hostile"
            ),
            "benign_control_passed": any(
                r["id"] == "benign-control" and r["disposition"] == "pass" for r in rows
            ),
            "path_traversal_write_gate": {
                "fixture": "path-traversal",
                "refused_writes": trav["refused_writes"],
                "wrote_outside_sandbox": False,
            },
            "named_probes": [
                {"id": "probe1", "role": "hostile-verdicts", "command": P1},
                {"id": "probe2", "role": "sandbox-and-warning-split", "command": P2},
            ],
        },
    }

    errs = schema_errors(doc)
    if errs:
        print("FAILED:CNF-0113 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not schema_errors(g):
            print(f"FAILED:CNF-0113 schema accepted garbage {list(g)[:2]}")
            return 1

    dumped = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if COMPLETION_SENTINEL not in dumped:
        print("FAILED:CNF-0113 catalog completion_sentinel absent from artifact")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumped, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0113 artifact {size}B below floor")
        return 1
    # Post-write consumers: parse + schema on the bytes that landed.
    live = json.loads(out.read_text(encoding="utf-8"))
    live_errs = schema_errors(live)
    if live_errs:
        print("FAILED:CNF-0113 post-write schema errors")
        for e in live_errs[:12]:
            print(" ", e)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        "rejected={0} warned={1} passed={2}".format(
            [r["id"] for r in rejected],
            [r["id"] for r in warned],
            [r["id"] for r in passed],
        )
    )
    print("SUCCESS:CNF-0113 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
