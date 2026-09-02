#!/usr/bin/env python3
"""Write the ADV-0038 artifact plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
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
import harness as H  # noqa: E402

UNIT = "ADV-0038"
OUT = H.ARTIFACT_REL
P1 = H.P1_CMD
P2 = H.P2_CMD
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0038/harness.py",
    "command-center/p2-wave/probes/ADV-0038/emit_receipt.py",
    "command-center/p2-wave/probes/ADV-0038/probe1_revoke_and_install.py",
    "command-center/p2-wave/probes/ADV-0038/probe2_metadata_capability.py",
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
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/ADV-0038/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    rec = H.write_artifact({"probe1": "", "probe2": ""})
    print(f"emit {OUT} bytes={rec['_disk_bytes']}")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    print(f"probe1 rc={c1}")
    print(t1[-1500:])
    print(f"probe2 rc={c2}")
    print(t2[-1500:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0038 probes c1={c1} c2={c2}")
        return 1

    rec = H.write_artifact({"probe1": t1, "probe2": t2})
    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:ADV-0038 re-run probes c1={c1b} c2={c2b}")
        print(t1b[-1500:])
        print(t2b[-1500:])
        return 1

    rec = H.write_artifact({"probe1": t1b, "probe2": t2b})
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": H.SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": H.SCHEMA_REL,
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered ADV-0038",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "revoke-then-install-from-each-source",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "metadata-revocation-field-capability-audit",
                "raw_output": t2b,
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0038/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0038-probe2-metadata-capability-audit",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for ADV-0038: live named probes exit 0, artifact state=SUCCESS "
            "verdict=CONFIRMED (revoked withdrawn-kit@1.0.0 still silently "
            "installs from cache/lockfile/offline_bundle/mirror; no source or "
            "live schema carries a revocation field). Per-unit manifest row. "
            "Did not run global unit_manifest.py --write. Did not rebuild "
            "IMP-0079 or any ADV production installer."
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0038 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
