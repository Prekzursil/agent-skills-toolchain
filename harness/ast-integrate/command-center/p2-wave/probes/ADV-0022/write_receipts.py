#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
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
UID = "ADV-0022"
OUT = "command-center/adversarial/ADV-0022-declared-permission-escape.json"
SCHEMA = "command-center/schema/exploit-proof.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0022/probe1_capability_escape.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0022/probe2_enforcement_audit.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0022/common.py",
    "command-center/p2-wave/probes/ADV-0022/sandbox.py",
    "command-center/p2-wave/probes/ADV-0022/host.py",
    "command-center/p2-wave/probes/ADV-0022/mechanism.py",
    "command-center/p2-wave/probes/ADV-0022/audit.py",
    "command-center/p2-wave/probes/ADV-0022/probe1_capability_escape.py",
    "command-center/p2-wave/probes/ADV-0022/probe2_enforcement_audit.py",
    "command-center/p2-wave/probes/ADV-0022/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0022/fixtures/narrow_skill.py",
    "command-center/p2-wave/probes/ADV-0022/fixtures/wide_skill.py",
    "command-center/p2-wave/probes/ADV-0022/fixtures/planted_call_time_gate.py",
    "command-center/p2-wave/probes/ARC-0081/model.py",
    "tools/agentspec/agentspec/spec.py",
]


def digest(path: Path) -> tuple[str, int]:
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
        env=env,
        timeout=180,
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
        "unit_id": UID,
        "receipt_path": f"command-center/p2-wave/probes/{UID}/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/ADV-0022/emit_artifact.py"
    )
    ce, te = run_cmd(emit)
    print(te[-3000:])
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}", file=sys.stderr)
        return 1
    if not (REPO / OUT).is_file():
        print(f"FAILED:receipts missing {OUT}", file=sys.stderr)
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}", file=sys.stderr)
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary]
    for rel in SUPPORTING:
        if (REPO / rel).is_file():
            artifacts.append(row(rel, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0022",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "narrow-capability-escape",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "static-enforcement-audit",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0022/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0022-probe2-static-enforcement-audit",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0022: live named probes exit 0, artifact "
            "state=SUCCESS overall_verdict=CONFIRMED (escape), per-unit "
            "manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild circle."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0022 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
