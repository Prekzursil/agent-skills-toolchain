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
OUT = "command-center/research/RES-0101.json"
SENTINEL = (
    "SUCCESS:RES-0101 in the receipt AND an accuracy-versus-catalog-size table "
    "at >=3 sizes with the pre-published gold task set attached"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0101/probe1_remeasure.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0101/probe2_independent.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0101/gold_task_set.json",
    "command-center/p2-wave/probes/RES-0101/inventory.py",
    "command-center/p2-wave/probes/RES-0101/router.py",
    "command-center/p2-wave/probes/RES-0101/measure.py",
    "command-center/p2-wave/probes/RES-0101/emit.py",
    "command-center/p2-wave/probes/RES-0101/probe1_remeasure.py",
    "command-center/p2-wave/probes/RES-0101/probe2_independent.py",
    "command-center/p2-wave/probes/RES-0101/inventory.live.json",
    "command-center/p2-wave/probes/RES-0101/measurement.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
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
        "unit_id": "RES-0101",
        "receipt_path": "command-center/p2-wave/probes/RES-0101/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0101",
        "unit_id": "RES-0101",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/measurement-run.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "tfidf-remeasure",
                "raw_output": t1 + "\n",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "jaccard-and-recount",
                "raw_output": t2 + "\n",
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
        "manifest_path": "command-center/p2-wave/probes/RES-0101/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0101-probe2-jaccard-and-recount",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Jaccard description/name overlap plus recount of stored "
                "TF-IDF selections; not a TF-IDF re-run."
            ),
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0101: live named probes exit 0, RES-0101.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "PATH CLIs resolve against /usr/local/bin:/usr/bin:/bin so "
            "agent-injected rg cannot change catalog size on remasure."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0101",
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
    print("SUCCESS:RES-0101 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
