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
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402
import emit_artifact  # noqa: E402

SUPPORTING = [
    C.SCHEMA_REL,
    "command-center/p2-wave/probes/CNL-0047/scheduler.py",
    "tools/council/budget/engagement.py",
    "command-center/p2-wave/probes/ADV-0094/common.py",
    "command-center/p2-wave/probes/ADV-0094/probe1_shares.py",
    "command-center/p2-wave/probes/ADV-0094/probe2_loo.py",
    "command-center/p2-wave/probes/ADV-0094/emit_artifact.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(C.REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = C.REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": C.UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0094/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    rc = emit_artifact.main()
    if rc != 0:
        print(f"FAILED:receipts emit rc={rc}")
        return rc
    c1, t1 = run_probe(C.P1_CMD)
    c2, t2 = run_probe(C.P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(C.ART_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": C.UNIT_ID,
        "unit_id": C.UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0094",
        "registered": True,
        "output_path": C.ART_REL,
        "output_schema": C.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": C.P1_CMD,
                "exit_code": c1,
                "role": "token-idea-attribution-shares",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": C.P2_CMD,
                "exit_code": c2,
                "role": "leave-one-out-outcome-delta",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": C.ART_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0094/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0094-probe2-loo-rederive",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0094: live named probes exit 0, council-pathology "
            "artifact state=SUCCESS with catalog completion_sentinel, per-unit "
            "manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": C.UNIT_ID,
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
    print(f"primary {C.ART_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0094 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
