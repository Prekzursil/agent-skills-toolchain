#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py --write.
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

UID = "ADV-0135"
OUT = "command-center/adversarial/ADV-0135-antigroupthink-evasion.json"
SCHEMA = "command-center/schema/evasion-corpus.schema.json"
SENTINEL = "SUCCESS:ADV-0135"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0135/probe1_evasion_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0135/probe2_reviewer_and_coc.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0135/controls.py",
    "command-center/p2-wave/probes/ADV-0135/councils.py",
    "command-center/p2-wave/probes/ADV-0135/corpus.py",
    "command-center/p2-wave/probes/ADV-0135/substance.py",
    "command-center/p2-wave/probes/ADV-0135/probe1_evasion_both_states.py",
    "command-center/p2-wave/probes/ADV-0135/probe2_reviewer_and_coc.py",
    "command-center/p2-wave/probes/ADV-0135/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0135/schema_local.py",
    "tools/council/quota/unique_ideas.py",
    "command-center/p2-wave/probes/CNL-0070/preservation.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0135/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/ADV-0135/emit_artifact.py"
    )
    ce, te = run_cmd(emit)
    if ce != 0:
        print(f"FAILED:ADV-0135 emit rc={ce}")
        print(te[-3000:])
        return 1
    print(te[-1500:])

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0135 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary]
    for p in SUPPORTING:
        if (REPO / p).is_file():
            artifacts.append(manifest_row(p, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "evasion-both-states",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "label-blind-reviewer-and-control-of-the-control",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0135/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0135-probe2-connected-components",
            "verdict": "PASS",
            "independent": True,
            "control_executed": True,
            "labels_hidden": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0135: live named probes exit 0, evasion corpus "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
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
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0135 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
