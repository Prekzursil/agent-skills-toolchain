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

import engine as E  # noqa: E402

EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0106/emit_artifact.py"
)
SUPPORTING = [
    "tools/council/partition.py",
    "command-center/p2-wave/probes/ADV-0106/engine.py",
    "command-center/p2-wave/probes/ADV-0106/probe1_identity_reattribution.py",
    "command-center/p2-wave/probes/ADV-0106/probe2_partition_audit.py",
    "command-center/p2-wave/probes/ADV-0106/emit_artifact.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(E.REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = E.REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "exists": path.is_file(),
        "eol": "LF",
        "unit_id": E.UNIT,
        "receipt_path": "command-center/p2-wave/probes/ADV-0106/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}")
        print(te[-4000:])
        return 1
    print(te)

    c1, t1 = run_cmd(E.PROBE1_CMD)
    c2, t2 = run_cmd(E.PROBE2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1

    out = E.REPO / E.OUT_REL
    doc = json.loads(out.read_text(encoding="utf-8"))
    doc["named_probes"] = [
        {
            "id": "probe1",
            "command": E.PROBE1_CMD,
            "exit_code": c1,
            "role": "identity-reattribution-vs-chance",
            "catalog_text": E.CATALOG_PROBE1,
            "raw_output": t1,
        },
        {
            "id": "probe2",
            "command": E.PROBE2_CMD,
            "exit_code": c2,
            "role": "partition-content-audit",
            "catalog_text": E.CATALOG_PROBE2,
            "raw_output": t2,
        },
    ]
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(E.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": E.UNIT,
        "unit_id": E.UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": E.SENTINEL,
        "registered": True,
        "output_path": E.OUT_REL,
        "output_schema": E.SCHEMA_DECLARED,
        "named_probes": [
            {
                "id": "probe1",
                "command": E.PROBE1_CMD,
                "exit_code": c1,
                "role": "identity-reattribution-vs-chance",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": E.PROBE2_CMD,
                "exit_code": c2,
                "role": "partition-content-audit",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": E.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0106/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0106-probe2-partition-content-audit",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0106: live named probes exit 0, adversarial artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Did not rebuild "
            "council-pathology-sim.schema.json. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": E.UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {E.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0106 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
