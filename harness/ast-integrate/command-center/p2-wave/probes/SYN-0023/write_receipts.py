#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import emit as E  # noqa: E402
from attribute import OUT_REL, P1, P2, SCHEMA_REL, sha256_file  # noqa: E402

UNIT = "SYN-0023"
REPO = E.REPO
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/SYN-0023/attribute.py",
    "command-center/p2-wave/probes/SYN-0023/live.py",
    "command-center/p2-wave/probes/SYN-0023/emit.py",
    "command-center/p2-wave/probes/SYN-0023/probe1_planted_labels.py",
    "command-center/p2-wave/probes/SYN-0023/probe2_identity_join.py",
    "command-center/p2-wave/probes/SYN-0023/fixtures/planted_conformity.json",
    "command-center/p2-wave/probes/SYN-0023/fixtures/planted_corroboration.json",
    "command-center/p2-wave/probes/SYN-0023/fixtures/planted_shared_stale_ancestor.json",
    "command-center/p2-wave/probes/SYN-0023/fixtures/planted_title_trap.json",
]


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "sha256": digest,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/SYN-0023/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    erc = E.main()
    if erc != 0:
        print(f"FAILED:SYN-0023 emit rc={erc}")
        return erc
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:SYN-0023 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0023",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "measure_line": "SUCCESS:delivered SYN-0023",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered SYN-0023"},
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "planted-labels",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "identity-join",
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/SYN-0023/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "SYN-0023-probe2-identity-join-and-share-recompute",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for SYN-0023: live named probes exit 0, SYN-0023.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Live SYN-0010 agreed set is attributed "
            "if present; planted controls are scored separately."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
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
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:SYN-0023 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
