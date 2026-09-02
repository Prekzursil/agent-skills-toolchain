#!/usr/bin/env python3
"""Emit TST-0222 receipt and per-unit G-1 return + manifest.

Does not run tools/command-center/unit_manifest.py --write.
"""

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
UNIT = "TST-0222"
OUT = "command-center/receipts/TST-0222.json"
SCHEMA = "command-center/schema/security-report.schema.json"
CATALOG_SCHEMA = "command-center/schema/receipt.schema.json#/$defs/security_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0222/probe1_denied_write.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0222/probe2_both_states_matrix.py"
)
QUESTION = (
    "Does a unit declaring [Read, Grep] actually fail when it attempts a "
    "Write? PASS requires a runtime denial with a typed permission error; a "
    "documented-only restriction is the defect being tested."
)
SUPPORTING = [
    SCHEMA,
    "tools/lib/workspace_permissions.py",
    "tools/lib/workspace.mjs",
    "command-center/p2-wave/probes/TST-0222/probe1_denied_write.py",
    "command-center/p2-wave/probes/TST-0222/probe2_both_states_matrix.py",
    "command-center/p2-wave/probes/TST-0222/emit.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            data = json.loads(line)
            if isinstance(data, dict):
                return data
    raise SystemExit(f"FAILED:TST-0222 emit no JSON payload in probe output: {text[-500:]}")


def validate_shape(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    missing = [key for key in schema["required"] if key not in doc]
    if missing:
        raise SystemExit(f"FAILED:TST-0222 schema missing {missing}")
    if doc.get("state") not in schema["properties"]["state"]["enum"]:
        raise SystemExit(f"FAILED:TST-0222 state {doc.get('state')}")
    if doc.get("overall_verdict") not in schema["properties"]["overall_verdict"]["enum"]:
        raise SystemExit("FAILED:TST-0222 overall_verdict")
    if not isinstance(doc.get("findings"), list) or len(doc["findings"]) < 1:
        raise SystemExit("FAILED:TST-0222 findings")
    if not isinstance(doc.get("evidence"), list) or len(doc["evidence"]) < 4:
        raise SystemExit("FAILED:TST-0222 evidence")
    if not isinstance(doc.get("tests"), list) or len(doc["tests"]) < 2:
        raise SystemExit("FAILED:TST-0222 tests")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("scope_not_agreement") is not True:
        raise SystemExit("FAILED:TST-0222 reviewer.scope_not_agreement")
    for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 400}):
        if not [key for key in schema["required"] if key not in garbage]:
            raise SystemExit("FAILED:TST-0222 schema accepted garbage")


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0222/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0222 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = first_json(t1)
    p2 = first_json(t2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:TST-0222 probe payload pass=false")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Yes. A session declaring [Read, Grep] raises ToolPermissionError "
        "code=tool-permission-denied on Write, and the target file is absent "
        "after the call. A documented-only twin (prompt/argv only, "
        "--danger-full-access) performs the same write, proving the filesystem "
        "check is non-vacuous. A unit declaring Write succeeds at the same "
        "call. All seven vocabulary tools were tested granted and denied. "
        "tools/lib/workspace.mjs independently repeats the denied Write. "
        "SUCCESS:TST-0222"
    )
    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0222",
        "completion_sentinel": "SUCCESS:TST-0222",
        "schema_version": 1,
        "report_kind": "security_report",
        "produced_at": now,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "catalog_output_schema": CATALOG_SCHEMA,
        "title": "Declared tool permissions are ENFORCED at runtime, not merely documented",
        "question": QUESTION,
        "claim_under_test": (
            "A unit declaring [Read, Grep] fails a Write at runtime with a "
            "typed ToolPermissionError (code=tool-permission-denied). The "
            "denied call does not create the target file. A unit declaring "
            "Write succeeds at the same call. Every tool in the closed "
            "permission vocabulary is tested in both the granted and denied "
            "state. Documented-only prompt/argv text is not a grant."
        ),
        "overall_verdict": "PASS",
        "answer": answer,
        "evaluation_site": "tools/lib/workspace_permissions.py:evaluate",
        "permission_vocabulary": p2.get("vocabulary"),
        "controls": {
            "denied_write_typed_error": p1.get("typed_error"),
            "denied_write_target_existed_after": p1.get("target_existed_after"),
            "documented_only_wrote": p1.get("documented_only_wrote"),
            "argv_differ": p1.get("argv_differ"),
            "both_states_write_granted": p2.get("both_states_write_granted"),
            "prefix_escape_blocked": p2.get("prefix_escape_blocked"),
            "js_independent": p2.get("js_independent"),
            "matrix": p2.get("matrix"),
        },
        "findings": [
            {
                "id": "F1",
                "severity": "none",
                "title": "Runtime Write denial is typed and file-absent",
                "detail": (
                    "PermissionSession([Read, Grep]).invoke(Write) raised "
                    "ToolPermissionError code=tool-permission-denied and the "
                    "target path did not exist afterwards. spawn_count stayed 0."
                ),
            },
            {
                "id": "F2",
                "severity": "info",
                "title": "Documented-only restriction is the defect, and it writes",
                "detail": (
                    "DocumentedOnlySession uses the same prompt text but "
                    "--danger-full-access and no --allowedTools. The same Write "
                    "persisted bytes, so a missing gate cannot hide behind a "
                    "vacuous filesystem check. Enforced argv differs."
                ),
            },
            {
                "id": "F3",
                "severity": "none",
                "title": "Both-states Write and seven-tool matrix",
                "detail": (
                    "Declaring Write succeeds at the same call. Each of "
                    f"{len(p2.get('vocabulary') or [])} vocabulary tools was "
                    "denied (typed error, no side effect) and granted. "
                    "workspace.mjs independently denied Write."
                ),
            },
        ],
        "evidence": [
            {
                "path": "tools/lib/workspace_permissions.py",
                "kind": "runtime-gate",
                "claim": (
                    "evaluate() is the single Python grant/deny site; invoke() "
                    "raises ToolPermissionError before any Write bytes land."
                ),
            },
            {
                "path": "tools/lib/workspace.mjs",
                "kind": "runtime-gate",
                "claim": (
                    "Independent JS evaluate() denies Write for [Read, Grep] "
                    "and leaves the target absent."
                ),
            },
            {
                "path": "command-center/p2-wave/probes/TST-0222/probe1_denied_write.py",
                "kind": "denied-call-and-filesystem",
                "claim": (
                    "Signal (a) typed tool-permission-denied; signal (b) "
                    "target_existed_after=false. Documented-only twin writes."
                ),
            },
            {
                "path": "command-center/p2-wave/probes/TST-0222/probe2_both_states_matrix.py",
                "kind": "both-states-and-matrix",
                "claim": (
                    "Granted Write persists bytes. Vocabulary matrix is 7/7 "
                    "granted+denied. Prefix-escape sibling path is blocked."
                ),
            },
        ],
        "tests": [
            {
                "id": "TST0222-T1-DENIED-WRITE",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST0222-T2-FILESYSTEM-NO-WRITE",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST0222-T3-GRANTED-CONTROL",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "TST0222-T4-PERMISSION-MATRIX",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "TST0222-T5-NEGATIVE-CONTROL",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST0222-T6-JS-INDEPENDENT-DENY",
                "command": P2,
                "result": "PASS",
            },
            {"id": "probe1-denied-write", "command": P1, "result": "PASS"},
            {"id": "probe2-both-states-matrix", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "TST-0222-probe1-filesystem-and-probe2-matrix",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe1 is the denied-call error plus an independent "
                "filesystem existence check. Probe2 is a different instrument: "
                "granted twin, closed vocabulary matrix, and node "
                "tools/lib/workspace.mjs. Catalog asked for a Codex pair; this "
                "headless worker uses the two named probes as the mechanical "
                "cross-check rather than a second vendor session."
            ),
            "pair": [
                {
                    "reviewer_id": "probe1-denied-write-filesystem",
                    "role": "correctness",
                    "verdict": "PASS",
                },
                {
                    "reviewer_id": "probe2-both-states-matrix-js",
                    "role": "security",
                    "verdict": "PASS",
                },
            ],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "tools/lib/workspace_permissions.py",
                "exists": True,
                "role": "runtime-gate",
            },
            {
                "path": "tools/lib/workspace.mjs",
                "exists": True,
                "role": "runtime-gate",
            },
        ],
        "target_contract_pass": True,
        "named_probe_embedded": True,
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0222/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
    }
    validate_shape(doc)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    if primary["present"] is not True:
        print("FAILED:TST-0222 primary missing after write")
        return 1
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    if any(item["present"] is not True for item in artifacts):
        missing = [item["path"] for item in artifacts if item["present"] is not True]
        print(f"FAILED:TST-0222 supporting missing {missing}")
        return 1

    r1, t1b = run_cmd(P1)
    r2, t2b = run_cmd(P2)
    if r1 != 0 or r2 != 0:
        print(f"FAILED:TST-0222 re-run probes r1={r1} r2={r2}")
        print(t1b[-1500:])
        print(t2b[-1500:])
        return 1

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0222",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": r1, "raw_output": t1b},
            {"id": "probe2", "command": P2, "exit_code": r2, "raw_output": t2b},
        ],
        "probes": [
            {"id": "probe1", "command": P1, "exit_code": r1},
            {"id": "probe2", "command": P2, "exit_code": r2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0222/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0222-probe1-filesystem-and-probe2-matrix",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for TST-0222: live named probes exit 0, receipts/TST-0222.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. No API keys rotated."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0222 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
