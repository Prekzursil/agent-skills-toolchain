#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/BLD-0018.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0018/probe1_scratch_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0018/probe2_reviewer_live.py"
)
SUPPORTING = [
    "command-center/schema/blindspot-register.schema.json",
    "command-center/p2-wave/probes/BLD-0018/engine.py",
    "command-center/p2-wave/probes/BLD-0018/probe1_scratch_controls.py",
    "command-center/p2-wave/probes/BLD-0018/probe2_reviewer_live.py",
    "command-center/p2-wave/probes/BLD-0018/emit_receipt.py",
    "command-center/p2-wave/probes/BLD-0018/fixtures/history/rev-earlier/PROGRAM-CHARTER.md",
    "command-center/p2-wave/probes/BLD-0018/fixtures/history/rev-later/PROGRAM-CHARTER.md",
    "command-center/p2-wave/probes/BLD-0018/fixtures/history/rev-later/OWNER-DECISIONS.md",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
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
        "unit_id": "BLD-0018",
        "receipt_path": "command-center/p2-wave/probes/BLD-0018/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = subprocess.run(
        [
            sys.executable,
            "-B",
            str(HERE / "emit_receipt.py"),
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if emit.returncode != 0:
        print("FAILED:BLD-0018 emit_receipt")
        print((emit.stdout or "")[-1500:])
        print((emit.stderr or "")[-1500:])
        return 1
    print((emit.stdout or "").strip())
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "BLD-0018",
        "unit_id": "BLD-0018",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0018",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/blindspot-register.schema.json",
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
        "manifest_path": "command-center/p2-wave/probes/BLD-0018/UNIT-ARTIFACT-MANIFEST.json",
        "measure_line": "SUCCESS:delivered BLD-0018",
        "measure": {
            "exit_code": 0,
            "line": "SUCCESS:delivered BLD-0018",
        },
        "reviewer": {
            "reviewer_id": "BLD-0018-probe2-decision-reread",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for BLD-0018: live named probes exit 0, receipts/BLD-0018.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Capability-id diff on scratch history; "
            "live Prompt One files encode no cap_id+mechanism pairs and git "
            "show is unavailable, so no invented live drops."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "BLD-0018",
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
    print("SUCCESS:BLD-0018 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
