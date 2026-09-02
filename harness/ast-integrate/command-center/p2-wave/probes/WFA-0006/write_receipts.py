#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "WFA-0006"
OUT = "command-center/wfa/WFA-0006-discovery-only-consumers.json"
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0006/emit_artifact.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0006/probe1_use_vs_mention_and_plant.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0006/probe2_independent_role_reread.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0006/names.py",
    "command-center/p2-wave/probes/WFA-0006/hunt.py",
    "command-center/p2-wave/probes/WFA-0006/graph.py",
    "command-center/p2-wave/probes/WFA-0006/classify_a.py",
    "command-center/p2-wave/probes/WFA-0006/classify_b.py",
    "command-center/p2-wave/probes/WFA-0006/fixtures/mention-only.md",
    "command-center/p2-wave/probes/WFA-0006/fixtures/capability-plant.md",
    "command-center/p2-wave/probes/WFA-0006/emit_artifact.py",
    "command-center/p2-wave/probes/WFA-0006/probe1_use_vs_mention_and_plant.py",
    "command-center/p2-wave/probes/WFA-0006/probe2_independent_role_reread.py",
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
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": (
            "command-center/p2-wave/probes/WFA-0006/SUBAGENT-RETURN.json"
        ),
        "role": role,
        "sha256": sha,
        "unit_id": UID,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:WFA-0006 emit rc={ce}")
        print(te[-4000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0006 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    out_path = REPO / OUT
    if not out_path.is_file():
        print(f"FAILED:WFA-0006 missing {OUT}")
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        "id": UID,
        "manifest_path": (
            "command-center/p2-wave/probes/WFA-0006/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "use-vs-mention-and-planted-capability",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "independent-token-window-reread",
            },
        ],
        "notes": (
            "G-1 for WFA-0006: live named probes exit 0, discovery-only "
            "consumer audit state=SUCCESS, per-unit manifest row. 08/09/10 "
            "bodies absent on this Linux worktree; the grep graph plus "
            "planted both-states control is the executable proof. Did not "
            "run global unit_manifest.py --write. cloud ok=true is not "
            "delivery. No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport"
        ),
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "WFA-0006-probe2-independent-role-reread",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:WFA-0006",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:WFA-0006 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
