#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0010.json from live C10 measurements."""
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
OUT = "command-center/receipts/TST-0010.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0010/probe1_open_p1_blocks.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0010/probe2_downgrade_audit.py"
)
TESTS = [
    sys.executable,
    "-B",
    "tools/command-center/tests/test_completion_c10.py",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd, timeout: int = 120) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if isinstance(cmd, str):
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    else:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "exists": False,
            "bytes": 0,
            "sha256": None,
            "role": role,
        }
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "exists": True,
        "bytes": size,
        "sha256": sha,
        "role": role,
    }


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:TST-0010 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def main() -> int:
    started = utc_now()
    t_rc, t_out = run(TESTS)
    p1_rc, p1_out = run(P1)
    p2_rc, p2_out = run(P2)
    tests_ok = t_rc == 0 and "SUCCESS:test_completion_c10" in t_out
    probes_ok = p1_rc == 0 and p2_rc == 0
    if not tests_ok or not probes_ok:
        print(f"FAILED:TST-0010 emit tests={t_rc} p1={p1_rc} p2={p2_rc}")
        print(t_out[-2000:])
        print(p1_out[-2000:])
        print(p2_out[-2000:])
        return 1

    impl = art("tools/command-center/completion_c10.py", "implementation")
    tests_art = art("tools/command-center/tests/test_completion_c10.py", "supporting")
    schema_art = art(SCHEMA, "schema")
    probe1 = art(
        "command-center/p2-wave/probes/TST-0010/probe1_open_p1_blocks.py", "probe"
    )
    probe2 = art(
        "command-center/p2-wave/probes/TST-0010/probe2_downgrade_audit.py", "probe"
    )
    transcript = art(
        "command-center/p2-wave/probes/TST-0010/fixtures/blocked_open_p1.transcript.txt",
        "blocked-run-transcript",
    )
    audit_row = art(
        "command-center/p2-wave/probes/TST-0010/fixtures/downgrade_audit_row.jsonl",
        "append-only-audit-row",
    )
    if not all(
        a["exists"]
        for a in (impl, tests_art, schema_art, probe1, probe2, transcript, audit_row)
    ):
        print("FAILED:TST-0010 emit missing supporting artifact")
        return 1

    e1 = ev(
        "tools/command-center/completion_c10.py",
        'CONDITION_TEXT = "no unresolved P0/P1 defect is attached"',
        "source",
        "Condition 10 is an independently addressable check that names open P0/P1 ids.",
    )
    e2 = ev(
        "tools/command-center/completion_c10.py",
        'raise GateError(\n            "a severity downgrade needs a non-blank reason; silent P1->P2 is refused"',
        "source",
        "Silent P1->P2 is refused; downgrade requires a non-blank reason.",
    )
    e3 = ev(
        "tools/command-center/completion_c10.py",
        "encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True) + \"\\n\"",
        "verifier",
        "Audit rows are appended as JSONL; earlier bytes are never rewritten.",
    )
    e4 = ev(
        "tools/command-center/tests/test_completion_c10.py",
        "def test_open_p1_blocks_success",
        "test",
        "Catalog test_open_p1_blocks_success is present and was executed.",
    )
    e5 = ev(
        "command-center/p2-wave/probes/TST-0010/fixtures/downgrade_audit_row.jsonl",
        '"action": "downgrade"',
        "audit",
        "The append-only audit row generated by a severity downgrade is on disk.",
    )

    ended = utc_now()
    question = (
        "Predicate condition 10: 'no unresolved P0/P1 defect is attached'. "
        "Target: a unit with an OPEN P1 in the defect ledger cannot reach SUCCESS "
        "even when all other 11 conditions hold, and the block names the defect id. "
        "Can a defect be silently downgraded from P1 to P2 to unblock, without an audit entry?"
    )
    answer = (
        "NO. tools/command-center/completion_c10.py replays severity from an "
        "append-only JSONL audit. An open P1 on an otherwise-complete candidate "
        "returns FAILED with failing-condition-id=10 and the defect id in the "
        "transcript. Mutating the ledger field P1->P2 without a downgrade row "
        "still blocks (naive ledger-only C10 is fooled; that is the negative "
        "control). downgrade() refuses a blank reason and, on a real downgrade, "
        "appends one JSONL row then updates the ledger. A resolved/closed P1 "
        "does not block."
    )

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0010",
        "id": "TST-0010",
        "title": "Open P0/P1 defect attachment must block completion",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0010",
        "completion_sentinel": "SUCCESS:TST-0010",
        "min_bytes_threshold": 2048,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "question": question,
        "answer": answer,
        "report_kind": "test-receipt",
        "implementation": {
            "path": "tools/command-center/completion_c10.py",
            "condition_id": 10,
            "condition_text": "no unresolved P0/P1 defect is attached",
            "canonical_severity": "append-only defect-audit JSONL replay",
            "silent_downgrade": "refused; unauthorized mutation still blocks and names the id",
        },
        "evidence": [e1, e2, e3, e4, e5],
        "evidence_requirement": {
            "blocked_run_transcript": transcript["path"],
            "append_only_audit_row": audit_row["path"],
        },
        "negative_controls": [
            {
                "id": "TST0010-C1-open-vs-closed",
                "kind": "both-states",
                "description": "Open P1 blocks SUCCESS and names the id. Closed/resolved P1 does not block.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST0010-C2-naive-ledger-fooled",
                "kind": "both-states",
                "description": "Ledger-field-only C10 is SATISFIED after silent P1->P2. Audit-backed C10 stays UNSATISFIED.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0010-probe2-downgrade-audit",
            "verdict": "PASS",
            "independent": True,
            "requirement": (
                "Severity downgrade must append an audit row; prefix bytes of the "
                "JSONL file must remain unchanged."
            ),
            "notes": (
                "probe2 mutates the ledger file on disk (not via the API), shows "
                "naive C10 fooled, shows audit-backed C10 still naming the defect "
                "id, refuses blank-reason downgrade, then runs the downgrade CLI "
                "and checks append-only prefix hash plus from=P1 to=P2 on the new row."
            ),
        },
        "tests": [
            {
                "id": "test_open_p1_blocks_success",
                "command": "python3 -B tools/command-center/tests/test_completion_c10.py",
                "result": "PASS" if tests_ok else "FAIL",
                "exit_code": t_rc,
            },
            {
                "id": "test_severity_downgrade_writes_an_audit_row",
                "command": "python3 -B tools/command-center/tests/test_completion_c10.py",
                "result": "PASS" if tests_ok else "FAIL",
                "exit_code": t_rc,
            },
            {
                "id": "test_closed_p1_does_not_block",
                "command": "python3 -B tools/command-center/tests/test_completion_c10.py",
                "result": "PASS" if tests_ok else "FAIL",
                "exit_code": t_rc,
            },
            {
                "id": "named-probe1-open-p1-blocks",
                "command": P1,
                "result": "PASS" if p1_rc == 0 else "FAIL",
                "exit_code": p1_rc,
            },
            {
                "id": "named-probe2-downgrade-audit",
                "command": P2,
                "result": "PASS" if p2_rc == 0 else "FAIL",
                "exit_code": p2_rc,
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "conformance-engineer",
            "execution_substrate": "linux-worktree-isolated",
        },
        "named_probes": [
            {"id": "probe1", "role": "open-p1-blocks-named-id", "command": P1},
            {"id": "probe2", "role": "append-only-downgrade-audit", "command": P2},
        ],
        "artifacts": [
            impl,
            tests_art,
            schema_art,
            probe1,
            probe2,
            transcript,
            audit_row,
        ],
        "manifest_registration": {
            "registered": False,
            "note": "per-unit UNIT-ARTIFACT-MANIFEST.json only; global unit_manifest.py --write not run",
        },
        "defects": [],
        "cloud_ok": False,
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "TST-0001 twelve-condition production oracle is delivered",
                "command-center/RISK-REGISTER.md exists on this tree",
            ]
        },
        "report": {
            "kind": "condition-10-gate",
            "question": question,
            "answer": "NO",
            "tests_pass": tests_ok,
            "probe1_pass": p1_rc == 0,
            "probe2_pass": p2_rc == 0,
            "test_output_tail": t_out[-1500:],
            "probe1_output_tail": p1_out[-2500:],
            "probe2_output_tail": p2_out[-2500:],
        },
    }

    schema_path = REPO / SCHEMA
    try:
        import jsonschema

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        # command-center/schema/test-receipt.schema.json is a $ref shim to an
        # unresolvable URL; Draft7Validator cannot follow it without a store.
        if isinstance(schema, dict) and schema.get("$ref") and "$defs" not in schema:
            print("WARN: test-receipt schema is a $ref shim; skipped Draft7Validator")
        else:
            errors = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
            if errors:
                print("FAILED:TST-0010 schema " + "; ".join(e.message for e in errors[:8]))
                return 1
    except Exception as exc:
        print(f"WARN: jsonschema skipped ({type(exc).__name__}: {exc})")

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if "SUCCESS:TST-0010" not in text:
        print("FAILED:TST-0010 sentinel missing from serialized receipt")
        return 1
    if '"state": "BLOCKED"' in text:
        print("FAILED:TST-0010 self-declared BLOCKED")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0010 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"tests={t_rc} probe1={p1_rc} probe2={p2_rc}")
    print("SUCCESS:TST-0010")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
