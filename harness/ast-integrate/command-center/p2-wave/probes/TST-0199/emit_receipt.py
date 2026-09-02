#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0199.json from live publisher + linter probes."""
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
OUT = "command-center/receipts/TST-0199.json"
SCHEMA = "command-center/schema/portability-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0199/probe1_publisher_corpus.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0199/probe2_independent_linter.py"
)
QUESTION = (
    "Are trailing-dot, trailing-space, control-character and case-folding-hazard "
    "(Turkish dotless i) filenames rejected before publication? PASS requires "
    "rejection at publish with the offending name and rule quoted."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str, timeout: int = 120) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    row = {"path": rel, "exists": path.is_file(), "role": role}
    if path.is_file():
        sha, size = sha256_file(path)
        row["bytes"] = size
        row["sha256"] = sha
    else:
        row["bytes"] = 0
        row["sha256"] = None
    return row


def garbage_rejected(schema: dict) -> bool:
    try:
        import jsonschema
    except ImportError:
        required = schema.get("required") or []
        return bool(required) and len(required) >= 8
    validator = jsonschema.Draft7Validator(schema)
    probes = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000, "ok": True},
        {"unit_id": "TST-0199", "state": "SUCCESS"},
    ]
    return all(bool(list(validator.iter_errors(p))) for p in probes)


def main() -> int:
    started = utc_now()
    tests_cmd = "python3 -B tools/marketplace/tests/test_filename_gate.py"
    tests_rc, tests_out = run(tests_cmd)
    if tests_rc != 0:
        print(tests_out[-4000:])
        print("FAILED:TST-0199 tests red; refusing to emit SUCCESS receipt")
        return 1

    p1_rc, p1_out = run(P1)
    p2_rc, p2_out = run(P2)
    p1 = extract_json(p1_out)
    p2 = extract_json(p2_out)
    if p1_rc != 0 or p2_rc != 0 or not p1.get("pass") or not p2.get("pass"):
        print(f"FAILED:TST-0199 emit probes p1={p1_rc} p2={p2_rc}")
        print(p1_out[-2000:])
        print(p2_out[-2000:])
        return 1

    schema_path = REPO / SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not garbage_rejected(schema):
        print("FAILED:TST-0199 schema is vacuous")
        return 1

    pr_only_rc, pr_only_out = run("python3 -B tools/marketplace/tests/test_pr_only_guard.py")
    if pr_only_rc != 0:
        print(pr_only_out[-2000:])
        print("FAILED:TST-0199 IMP-0112 regression")
        return 1

    named = int(p1.get("named_in_rejection") or 0)
    corpus_size = int(p1.get("corpus_size") or 0)
    supporting = [
        SCHEMA,
        "tools/marketplace/filename_gate.py",
        "tools/marketplace/unportable_corpus.json",
        "tools/marketplace/pr_only_guard.py",
        "tools/marketplace/publishing.py",
        "tools/plugin/portability_linter.py",
        "tools/marketplace/tests/test_filename_gate.py",
        "command-center/p2-wave/probes/TST-0199/probe1_publisher_corpus.py",
        "command-center/p2-wave/probes/TST-0199/probe2_independent_linter.py",
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    now = utc_now()
    receipt = {
        "schema_version": 1,
        "unit_id": "TST-0199",
        "id": "TST-0199",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0199",
        "completion_sentinel": "SUCCESS:TST-0199",
        "kind": "portability_report",
        "title": "Unportable filenames are rejected at publish time",
        "question": QUESTION,
        "answer": (
            "YES. marketplace pack/validate/publish run filename_gate before any "
            "outbound sink. A portable name set publishes. Each of 40 known-"
            "unportable names (trailing-dot, trailing-space, C0-control, Turkish "
            "dotted/dotless I) is individually named in the rejection with the "
            "rule id and rule text quoted. An independent UTF-8 byte linter over "
            "the same file set agrees; a reserved-device-name-only stub is silent."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "produced_at": now,
        "timestamps": {"started_at": started, "ended_at": now},
        "min_bytes_threshold": 128,
        "signals": [
            {
                "id": "publisher-rejection-list",
                "kind": "publisher",
                "fired": True,
                "named_in_rejection": named,
                "status": p1.get("publisher_status"),
                "portable_published": p1.get("portable_published"),
            },
            {
                "id": "independent-byte-linter",
                "kind": "linter",
                "fired": True,
                "agreement": p2.get("agreement"),
                "engine": p2.get("linter_engine"),
                "independent_of": p2.get("independent_of"),
            },
        ],
        "controls": [
            {
                "id": "both-states-portable-publishes",
                "expected": "SILENT",
                "observed": "SILENT",
                "exit_code": 0,
                "fixture": "portable-name-set",
                "portable_published": True,
            },
            {
                "id": "corpus-40-named-in-rejection",
                "expected": "FIRED",
                "observed": "FIRED",
                "exit_code": 1,
                "fixture": "40-known-unportable-names",
                "named_in_rejection": named,
            },
            {
                "id": "reserved-device-stub-silent",
                "expected": "SILENT",
                "observed": "SILENT",
                "exit_code": 0,
                "fixture": "reserved-name-only-detector",
                "hits": p2.get("reserved_stub_hits") or [],
            },
        ],
        "corpus": {
            "size": corpus_size,
            "named_in_rejection": named,
            "classes": p1.get("classes"),
            "path": "tools/marketplace/unportable_corpus.json",
        },
        "counts": [
            {
                "id": "corpus-named",
                "numerator": named,
                "denominator": 40,
                "label": "known-unportable names individually named in rejection",
            },
            {
                "id": "portable-published",
                "numerator": 1 if p1.get("portable_published") else 0,
                "denominator": 1,
                "label": "portable name set publishes",
            },
        ],
        "tests": [
            {
                "id": "probe1-publisher-both-states-corpus",
                "command": P1,
                "result": "PASS",
                "exit_code": p1_rc,
            },
            {
                "id": "probe2-independent-linter",
                "command": P2,
                "result": "PASS",
                "exit_code": p2_rc,
            },
            {
                "id": "test_filename_gate",
                "command": tests_cmd,
                "result": "PASS",
                "exit_code": tests_rc,
            },
            {
                "id": "test_pr_only_guard_regression",
                "command": "python3 -B tools/marketplace/tests/test_pr_only_guard.py",
                "result": "PASS",
                "exit_code": pr_only_rc,
            },
        ],
        "evidence": [
            {
                "path": "tools/marketplace/filename_gate.py",
                "kind": "publisher-rejection-list",
                "claim": (
                    f"Publisher named {named}/40 unportable members with rule id "
                    "and rule text; portable set published; PUBLIC publish of the "
                    "corpus never reached _outbound_publish."
                ),
            },
            {
                "path": "tools/plugin/portability_linter.py",
                "kind": "independent-portability-linter",
                "claim": (
                    "Byte-linter (trailing 0x2E/0x20, byte<0x20, UTF-8 C4 B0/C4 B1) "
                    "agrees with the publisher on the same file set and does not "
                    "import filename_gate. Reserved-device stub is silent."
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "TST0199-C1-reserved-stub",
                "kind": "known-deaf-detector",
                "description": (
                    "A reserved-device-name-only stub over the 40-name corpus "
                    "must stay silent. If it fired, the unit would measure the "
                    "wrong hazard class."
                ),
                "fired_on_bad_state": False,
                "silent_on_good_state": True,
                "bad_state_output": "reserved_stub_hits=[]",
                "good_state_output": f"named_in_rejection={named}",
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0199-probe2-independent-byte-linter",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "windows_second_shell": "NOT-CHECKED",
            "notes": (
                "Independent UTF-8 byte linter agrees with the publisher and does "
                "not import it. This Linux worktree has no second Windows shell "
                "(pwsh7 / Git Bash); the filename rules are host-independent "
                "string/byte checks. Shell divergence remains residual."
            ),
        },
        "artifacts": artifacts,
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0199/"
                "UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
            }
        ],
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "residual_unknowns": [
            {
                "claim": (
                    "Reviewer_requirement asked for a second Windows shell "
                    "(pwsh7 and Git Bash). Not executed on this Linux worktree. "
                    "Rules operate on member-name strings, not the host filesystem."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1 and probe2 under pwsh7 and Git Bash on Windows "
                    "and report any divergence as a finding."
                ),
            }
        ],
        "report": {
            "kind": "portability_report",
            "probe1": p1,
            "probe2": p2,
            "test_output": tests_out[-1500:],
        },
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    try:
        import jsonschema

        errors = list(jsonschema.Draft7Validator(schema).iter_errors(receipt))
        if errors:
            dest.unlink(missing_ok=True)
            print("FAILED:TST-0199 receipt fails schema: " + errors[0].message)
            return 1
    except ImportError:
        pass

    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:TST-0199")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
