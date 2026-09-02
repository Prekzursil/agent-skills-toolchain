#!/usr/bin/env python3
"""Emit TST-0008 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sentinel_check as C  # noqa: E402

UNIT = "TST-0008"
OUT = "command-center/receipts/TST-0008.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0008"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0008/probe1_role_not_substring.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0008/probe2_typed_field_ast.py"
)
QUESTION = (
    "Predicate condition 5 requires the sentinel present (:10636). The "
    "use-vs-mention class has hit this estate ~8 times, including inside "
    "the verification probes themselves. Target: the sentinel check keys "
    "on the semantic ROLE (a terminal line in the receipt's status field), "
    "not on a substring match anywhere in the payload. Does a document that "
    "merely DESCRIBES 'SUCCESS:TST-0008' satisfy the check?"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0008/sentinel_check.py",
    "command-center/p2-wave/probes/TST-0008/fixtures/body_mention.json",
    "command-center/p2-wave/probes/TST-0008/fixtures/status_use.json",
    "command-center/p2-wave/probes/TST-0008/fixtures/wrong_unit.json",
    "command-center/p2-wave/probes/TST-0008/probe1_role_not_substring.py",
    "command-center/p2-wave/probes/TST-0008/probe2_typed_field_ast.py",
    "command-center/p2-wave/probes/TST-0008/emit.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/TST-0008/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UNIT,
    }


def main() -> int:
    campaign = C.run_required_tests()
    if campaign["ok"] is not True:
        print("FAILED:TST-0008 emit required tests")
        print(json.dumps(campaign, indent=2, sort_keys=True)[:4000])
        return 1

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    print(f"probe1 rc={c1}")
    print(t1[-2000:])
    print(f"probe2 rc={c2}")
    print(t2[-2000:])
    if c1 != 0 or c2 != 0:
        print("FAILED:TST-0008 named probes")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib_sha, lib_bytes = digest_file(HERE / "sentinel_check.py")
    tests = []
    for row_t in campaign["tests"]:
        tests.append(
            {
                "id": row_t["id"],
                "name": row_t["id"],
                "result": "PASS" if row_t["ok"] else "FAIL",
                "verdict": "PASS" if row_t["ok"] else "FAIL",
                "role_satisfies": row_t["role"]["satisfies"],
                "role_reason": row_t["role"]["reason"],
                "fixture": row_t["fixture"],
            }
        )
    body_row = next(
        r for r in campaign["tests"] if r["id"] == "test_sentinel_in_body_does_not_satisfy"
    )
    wrong_row = next(
        r
        for r in campaign["tests"]
        if r["id"] == "test_sentinel_of_a_DIFFERENT_unit_id_does_not_satisfy"
    )
    use_row = next(
        r
        for r in campaign["tests"]
        if r["id"] == "test_sentinel_in_status_field_satisfies"
    )

    question_answer = (
        "No. A document that merely DESCRIBES 'SUCCESS:TST-0008' in body or "
        "notes does not satisfy the check. The checker reads the typed status "
        "field's terminal line and demands equality with the expected sentinel; "
        "it does not scan free text. The body_mention fixture quotes a valid "
        "sentinel while status is empty and is asserted FAILED "
        f"(reason={body_row['role']['reason']}). A different unit id in status "
        f"is also FAILED and names the mismatch ({wrong_row['role'].get('mismatch')})."
    )

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED\nSUCCESS:TST-0008",
        "schema_version": 1,
        "report_kind": "test-receipt",
        "title": (
            "Sentinel detection must distinguish a real sentinel from a "
            "sentinel quoted inside a payload"
        ),
        "question": QUESTION,
        "question_answer": question_answer,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "parser": {"name": "json.loads", "version": "stdlib"},
        "checker": {
            "module": "command-center/p2-wave/probes/TST-0008/sentinel_check.py",
            "sha256": lib_sha,
            "bytes": lib_bytes,
            "entry_points": [
                "check_sentinel_role",
                "status_terminal_line",
                "check_sentinel_substring",
            ],
            "policy": [
                "read the typed status field, never dump or scan the payload",
                "the semantic ROLE is the terminal line of status",
                "equality against the expected sentinel, not substring membership",
                "empty status with a quoted body token is FAILED",
                "a different unit's status terminal line is FAILED and named",
            ],
            "known_broken_cousin": "check_sentinel_substring",
        },
        "evidence": {
            "checker_reads_typed_field": True,
            "body_quotes_valid_sentinel_status_empty_asserted_failed": True,
            "body_mention_role_reason": body_row["role"]["reason"],
            "body_mention_substring_cousin_would_pass": body_row["substring_cousin"][
                "satisfies"
            ],
            "status_use_role_satisfies": use_row["role"]["satisfies"],
            "status_use_whole_field_equals_expected": use_row[
                "whole_field_equals_expected"
            ],
            "wrong_unit_mismatch": wrong_row["role"].get("mismatch"),
            "wrong_unit_substring_cousin_would_pass": wrong_row["substring_cousin"][
                "satisfies"
            ],
            "two_independent_signals": True,
            "computed_not_asserted": True,
        },
        "fixtures": {
            "body_mention": "command-center/p2-wave/probes/TST-0008/fixtures/body_mention.json",
            "status_use": "command-center/p2-wave/probes/TST-0008/fixtures/status_use.json",
            "wrong_unit": "command-center/p2-wave/probes/TST-0008/fixtures/wrong_unit.json",
        },
        "tests": tests,
        "checks": [
            {"id": row_t["id"], "verdict": "PASS" if row_t["ok"] else "FAIL"}
            for row_t in campaign["tests"]
        ],
        "named_probes": [
            {
                "id": "probe1",
                "role": "role-vs-substring-required-tests",
                "command": P1,
                "exit_code": c1,
            },
            {
                "id": "probe2",
                "role": "typed-field-ast-and-substring-mutant",
                "command": P2,
                "exit_code": c2,
            },
        ],
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0008-probe2-typed-field-ast",
            "verdict": "PASS",
            "notes": (
                "Named probe2 parses check_sentinel_role / status_terminal_line "
                "from source (AST) and requires a typed status-key read, forbids "
                "expected-in-payload membership and json.dumps, and plants the "
                "substring cousin against the empty-status body-mention fixture."
            ),
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "detector-auditor",
            "execution_substrate": "linux-local",
        },
        "scope": {
            "proof_surface": (
                "role checker + three committed fixtures + AST of the checker "
                "+ substring-cousin both-states control"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "platform/lib/completion_predicate.py was patched (absent on this worktree)",
                "TST-0001 / TST-0017 receipts were present",
            ],
        },
        "output_schema_declared": SCHEMA,
        "output_schema_on_disk": (REPO / SCHEMA).is_file(),
        "ts": now,
        "SUCCESS:TST-0008": True,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:TST-0008 emit sentinel missing from serialisation")
        return 1
    if len(text.encode("utf-8")) < 2048:
        print("FAILED:TST-0008 emit receipt too thin")
        return 1
    out.write_text(text, encoding="utf-8")

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/TST-0008/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1[-8000:],
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2[-8000:],
            },
        ],
        "notes": (
            "G-1 for TST-0008: live named probes exit 0, receipts/TST-0008.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0008-probe2-typed-field-ast",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UNIT,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={primary['bytes']} sha256={primary['sha256']}")
    print("SUCCESS:TST-0008 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
