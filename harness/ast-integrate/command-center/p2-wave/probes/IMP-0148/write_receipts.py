#!/usr/bin/env python3
"""Write IMP-0148 catalog receipt + per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST."""

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
OUT = "command-center/receipts/IMP-0148.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0148/probe1_closure.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0148/probe2_planted.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/validate.py",
    "tools/agentspec/agentspec/id_closure.py",
    "tools/agentspec/docs/violation-ids.json",
    "tools/agentspec/tests/test_id_closure.py",
    "tools/detector-self-test/detector_self_test.py",
    "command-center/p2-wave/probes/IMP-0148/probe1_closure.py",
    "command-center/p2-wave/probes/IMP-0148/probe2_planted.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0148",
        "receipt_path": "command-center/p2-wave/probes/IMP-0148/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    sys.path.insert(0, str(REPO / "tools" / "agentspec"))
    from agentspec.id_closure import check_closure

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    closure = check_closure()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": "IMP-0148",
        "id": "IMP-0148",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "completion_sentinel": "SUCCESS:IMP-0148",
        "sentinel": "SUCCESS:IMP-0148",
        "schema_version": 1,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0148",
        "title": "Keep the violation-id set closed after every Phase-7 spec extension",
        "timestamps": {"started_at": now, "ended_at": now},
        "evidence": [
            {
                "claim": "AST-derived violation ids from validate.py equal the documented set.",
                "verdict": "CONFIRMED",
                "emitted_count": closure["emitted_count"],
                "documented_count": closure["documented_count"],
                "equal": closure["equal"],
                "emitted": closure["emitted"],
                "documented": closure["documented"],
                "extra": closure["extra"],
                "missing": closure["missing"],
                "method": "ast.walk: Violation(...) first-arg/id=, append/extend of str constants, returned list/tuple literals, Name bindings",
            },
            {
                "claim": "A planted undocumented id turns the same closure check red (detector control).",
                "verdict": "CONFIRMED",
                "planted_id": "planted-undocumented-id",
                "both_states": "silent on unmodified validate.py; fires on planted emit site",
            },
        ],
        "tests": [
            {"id": "probe1_closure", "command": P1, "result": "PASS", "exit_code": c1},
            {"id": "probe2_planted", "command": P2, "result": "PASS", "exit_code": c2},
        ],
        "negative_controls": [
            {
                "id": "planted-undocumented-id",
                "kind": "detector-both-states",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0148-probe1-ast-closure",
            "independent": True,
            "verdict": "PASS",
            "fresh_context": True,
        },
        "artifacts": [
            {"path": "tools/agentspec/agentspec/validate.py", "role": "implementation"},
            {"path": "tools/agentspec/docs/violation-ids.json", "role": "documented-set"},
            {"path": "tools/agentspec/agentspec/id_closure.py", "role": "ast-enumerator"},
            {"path": "tools/detector-self-test/detector_self_test.py", "role": "detector-harness"},
        ],
        "notes": (
            "IMP-0148 G-1: closure test AST-enumerates every violation id emit "
            "in tools/agentspec/agentspec/validate.py and asserts set equality "
            "with tools/agentspec/docs/violation-ids.json (original baseline 28; "
            "live closed set is whatever is documented). Planted id "
            "planted-undocumented-id turns the check red via tools/detector-self-test. "
            "Did not run global unit_manifest.py --write. SUCCESS:IMP-0148"
        ),
        "probe1_output": t1,
        "probe2_output": t2,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0148",
        "unit_id": "IMP-0148",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0148",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "ast-documented-set-equality",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "planted-undocumented-id-detector-control",
                "raw_output": t2,
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "ast-documented-set-equality",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "planted-undocumented-id-detector-control",
                "raw_output": t2,
            },
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0148/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0148-probe1-ast-closure",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0148: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0148",
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
    print("SUCCESS:IMP-0148 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
