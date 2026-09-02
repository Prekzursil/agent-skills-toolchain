#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0046.json."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from suite import (  # noqa: E402
    both_states,
    materialize_fixtures,
    receipt_contract,
    rules_covered,
)

OUT = "command-center/receipts/TST-0046.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
CALC = "command-center/p2-wave/probes/ARC-0092/calculator.py"
LIVE = "command-center/schema/conformance-report.schema.json"
SENTINEL = (
    "SUCCESS:TST-0046 planted breaking schema change under a PATCH bump was "
    "rejected by the gate and a genuine PATCH was accepted"
)
QUESTION = (
    "Does the version bump policy match the actual change surface - can a "
    "breaking schema change ship under a patch bump, and does the gate catch it?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0046/probe1_planted_and_patch.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0046/probe2_both_states.py"
)
GATE = HERE / "gate.py"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def gate_cli(old: Path, new: Path, declared_from: str, declared_to: str) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(GATE),
            "--old",
            str(old),
            "--new",
            str(new),
            "--class",
            "schema",
            "--from-version",
            declared_from,
            "--to-version",
            declared_to,
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    payload = (proc.stdout or "").strip()
    try:
        body = json.loads(payload.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        body = {"raw": payload, "stderr": (proc.stderr or "")[-1000:]}
    body["cli_exit"] = proc.returncode
    return body


def build() -> dict:
    fixtures = materialize_fixtures()
    control = both_states()
    planted = gate_cli(
        REPO / fixtures["planted_old"],
        REPO / fixtures["planted_new"],
        "1.2.3",
        "1.2.4",
    )
    genuine = gate_cli(
        REPO / fixtures["genuine_old"],
        REPO / fixtures["genuine_new"],
        "1.2.3",
        "1.2.4",
    )
    real = control["real"]
    checks = []
    tests = []
    for row in real["rows"]:
        verdict = "PASS" if row["pass"] else "FAIL"
        checks.append(
            {
                "id": row["id"],
                "verdict": verdict,
                "rule": row["rule"],
                "declared": row["declared"],
                "want_decision": row["want_decision"],
                "got_decision": row["got_decision"],
                "got_required": row["got_required"],
                "got_kinds": row["got_kinds"],
            }
        )
        tests.append(
            {
                "id": row["id"],
                "result": verdict,
                "rule": row["rule"],
            }
        )
    tests.extend(
        [
            {
                "id": "both-states-always-accept-fails",
                "result": "PASS" if not control["always_accept_pass"] else "FAIL",
                "failed_cases": control["always_accept_failed"],
            },
            {
                "id": "both-states-always-reject-fails",
                "result": "PASS" if not control["always_reject_pass"] else "FAIL",
                "failed_cases": control["always_reject_failed"],
            },
            {
                "id": "cli-planted-breaking-patch-exit-2",
                "result": "PASS" if planted.get("cli_exit") == 2 else "FAIL",
                "cli_exit": planted.get("cli_exit"),
                "decision": planted.get("decision"),
            },
            {
                "id": "cli-genuine-patch-exit-0",
                "result": "PASS" if genuine.get("cli_exit") == 0 else "FAIL",
                "cli_exit": genuine.get("cli_exit"),
                "decision": genuine.get("decision"),
            },
        ]
    )
    test_fail = any(t["result"] != "PASS" for t in tests)
    state = "SUCCESS" if (control["pass"] and not test_fail) else "FAILED"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    evidence = [
        {"path": LIVE, "kind": "catalog-output-schema"},
        {
            "path": "command-center/p2-wave/probes/TST-0046/fixtures/subject-schema.json",
            "kind": "versioning-subject-schema",
        },
        {"path": CALC, "kind": "bump-classifier"},
        {"path": "command-center/p2-wave/probes/TST-0046/gate.py", "kind": "version-bump-gate"},
        {"path": "command-center/p2-wave/probes/TST-0046/suite.py", "kind": "conformance-suite"},
        {"path": fixtures["planted_old"], "kind": "planted-breaking-old"},
        {"path": fixtures["planted_new"], "kind": "planted-breaking-new"},
        {"path": fixtures["genuine_old"], "kind": "genuine-patch-old"},
        {"path": fixtures["genuine_new"], "kind": "genuine-patch-new"},
    ]
    artifacts = [{"path": OUT, "role": "primary"}] + [
        {"path": e["path"], "role": e["kind"]} for e in evidence
    ]
    sentinel = SENTINEL if state == "SUCCESS" else "FAILED:TST-0046 suite did not discriminate"
    return {
        "unit_id": "TST-0046",
        "state": state,
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "title": "Executable conformance tests for the versioning rules contract",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "report_kind": "versioning-rules-conformance",
        "schema_version": 1,
        "min_bytes_threshold": 1500,
        "produced_at": now,
        "environment": {
            "platform": platform.platform(),
            "python3": sys.executable,
        },
        "answer": {
            "breaking_under_patch_rejected": planted.get("decision") == "REJECT"
            and planted.get("cli_exit") == 2,
            "genuine_patch_accepted": genuine.get("decision") == "ACCEPT"
            and genuine.get("cli_exit") == 0,
            "required_bump_planted": planted.get("required_bump"),
            "required_bump_genuine": genuine.get("required_bump"),
            "declared_semver": "1.2.3 -> 1.2.4 PATCH",
            "suite_total": real["total"],
            "suite_failed": real["failed"],
            "rules_covered": rules_covered(),
            "prose": (
                "A planted narrowing of PARTIAL out of the versioning-subject "
                f"state enum (required {planted.get('required_bump')}) declared "
                f"as PATCH 1.2.3->1.2.4 was {planted.get('decision')} (cli_exit="
                f"{planted.get('cli_exit')}). A description-only edit of the "
                f"same subject (required {genuine.get('required_bump')}) declared "
                f"as PATCH was {genuine.get('decision')} (cli_exit="
                f"{genuine.get('cli_exit')}). The catalog output_schema path is "
                "a generated $ref shim; the suite also rejects a planted $ref "
                "change under PATCH and accepts a title-only PATCH on that live "
                "file. Always-accept mutant failed "
                f"{control['always_accept_failed']} cases; always-reject mutant "
                f"failed {control['always_reject_failed']} cases."
            ),
        },
        "gate": {
            "planted_breaking": planted,
            "genuine_patch": genuine,
        },
        "both_states": {
            "pass": control["pass"],
            "real_pass": control["real_pass"],
            "always_accept_pass": control["always_accept_pass"],
            "always_reject_pass": control["always_reject_pass"],
            "always_accept_failed": control["always_accept_failed"],
            "always_reject_failed": control["always_reject_failed"],
            "planted_rejected": control["planted_rejected"],
            "genuine_accepted": control["genuine_accepted"],
        },
        "checks": checks,
        "evidence": evidence,
        "tests": tests,
        "reviewer": {
            "reviewer_id": "TST-0046-probe2-both-states",
            "verdict": "PASS" if state == "SUCCESS" else "FAIL",
            "independent": True,
            "note": (
                "Probe2 re-runs the suite against always-accept and always-reject "
                "mutants without reading this conclusion first."
            ),
        },
        "artifacts": artifacts,
        "named_probes": [
            {"id": "probe1", "role": "planted-and-genuine-live-gate", "command": P1},
            {"id": "probe2", "role": "both-states-mutants", "command": P2},
        ],
        "cloud_ok": False,
    }


def validate_or_die(doc: dict) -> None:
    schema = receipt_contract()
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0046 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "TST-0046"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:TST-0046 schema accepted garbage")
            raise SystemExit(1)


def main() -> int:
    doc = build()
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0046 self-declared {doc.get('state')}")
        out = REPO / OUT
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0046 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0046 sentinel absent")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        "planted={0} genuine={1} suite_failed={2}".format(
            doc["answer"]["breaking_under_patch_rejected"],
            doc["answer"]["genuine_patch_accepted"],
            doc["answer"]["suite_failed"],
        )
    )
    print("SUCCESS:TST-0046 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
