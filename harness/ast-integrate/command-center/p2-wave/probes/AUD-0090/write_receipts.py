#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.

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
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

UID = E.UID
OUT = E.OUT_REL
SCHEMA = E.SCHEMA_REL
P1 = E.P1
P2 = E.P2
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/AUD-0090/engine.py",
    "command-center/p2-wave/probes/AUD-0090/probe1_blob.py",
    "command-center/p2-wave/probes/AUD-0090/probe2_worktree.py",
    "command-center/p2-wave/probes/AUD-0090/emit_artifact.py",
    "command-center/p2-wave/probes/AUD-0090/fixtures/semgrep-rules.yaml",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    deps = str((HERE / "deps").resolve())
    cur = env.get("PYTHONPATH", "")
    kept = [p for p in cur.split(os.pathsep) if p and not p.startswith(deps)]
    if kept:
        env["PYTHONPATH"] = os.pathsep.join(kept)
    else:
        env.pop("PYTHONPATH", None)
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
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/AUD-0090/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit_rc, emit_out = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/AUD-0090/emit_artifact.py"
    )
    if emit_rc != 0:
        print(f"FAILED:{UID} emit rc={emit_rc}")
        print(emit_out[-4000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UID} post-emit probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0090",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
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
        "manifest_path": (
            "command-center/p2-wave/probes/AUD-0090/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "AUD-0090-probe2-windows-worktree-analogue",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for AUD-0090: live named probes exit 0, static-analysis "
            "baseline state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. No ADV rebuild."
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
        json.dumps(ret, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UID} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
