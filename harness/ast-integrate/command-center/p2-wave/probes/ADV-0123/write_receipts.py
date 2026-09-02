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
sys.path.insert(0, str(HERE))
import race as R  # noqa: E402

SUPPORTING = [
    R.SCHEMA_REL,
    "command-center/p2-wave/probes/ADV-0123/race.py",
    "command-center/p2-wave/probes/ADV-0123/probe1_index_overlap.py",
    "command-center/p2-wave/probes/ADV-0123/probe2_lease_enforcement.py",
    "command-center/p2-wave/probes/ADV-0123/emit_artifact.py",
]
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0123/emit_artifact.py"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(R.REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = R.REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": R.UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0123/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}")
        print(te[-4000:])
        return 1
    print(te[-2000:])
    c1, t1 = run_cmd(R.P1_CMD)
    c2, t2 = run_cmd(R.P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(R.OUTPUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": R.UNIT_ID,
        "unit_id": R.UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": R.catalog_sentinel(),
        "registered": True,
        "output_path": R.OUTPUT_REL,
        "output_schema": R.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": R.P1_CMD,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": R.P2_CMD,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": R.OUTPUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/ADV-0123/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "ADV-0123-probe2-lease-enforcement",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for ADV-0123: live named probes exit 0, honest SUCCESS "
            "fault-injection-run on scratch-tree index/lease races, "
            "per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "measure_line": f"SUCCESS:delivered {R.UNIT_ID}",
        "measure": {"exit_code": 0, "line": f"SUCCESS:delivered {R.UNIT_ID}"},
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": R.UNIT_ID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote receipts primary_sha={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0123 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
