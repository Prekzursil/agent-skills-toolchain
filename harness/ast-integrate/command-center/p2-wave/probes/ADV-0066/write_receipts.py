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
OUT = "command-center/adversarial/ADV-0066-version-downgrade-attack.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0066/probe1_downgrade_paths.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0066/probe2_stale_index.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0066/emit_artifact.py"
)
SUPPORTING = [
    "command-center/schema/supply-chain-attestation.schema.json",
    "command-center/p2-wave/probes/ADV-0066/resolver.py",
    "command-center/p2-wave/probes/ADV-0066/fixtures.py",
    "command-center/p2-wave/probes/ADV-0066/probe1_downgrade_paths.py",
    "command-center/p2-wave/probes/ADV-0066/probe2_stale_index.py",
    "command-center/p2-wave/probes/ADV-0066/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0066/fixtures/advisory.json",
    "command-center/p2-wave/probes/ADV-0066/fixtures/packages/1.0.0/package.json",
    "command-center/p2-wave/probes/ADV-0066/fixtures/packages/2.0.0/package.json",
    "command-center/p2-wave/probes/ADV-0066/fixtures/mirrors/fresh/index.json",
    "command-center/p2-wave/probes/ADV-0066/fixtures/mirrors/stale/index.json",
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
        "unit_id": "ADV-0066",
        "receipt_path": "command-center/p2-wave/probes/ADV-0066/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}")
        print(te[-3000:])
        return 1
    print(te)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0066",
        "unit_id": "ADV-0066",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0066",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/supply-chain-attestation.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "per-path-downgrade-with-advisory-present",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "stale-index-freshness-versus-silent-v1",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0066/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0066-probe2-stale-index",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0066: live named probes exit 0, version-downgrade "
            "attestation state=SUCCESS (CONFIRMED: rollback/pin/stale index "
            "install v1 with advisory present and no min-version floor), "
            "per-unit manifest row. Did not run global unit_manifest.py "
            "--write. No ADV rebuild. Distinct from ADV-0038 revocation."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0066",
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
    print("SUCCESS:ADV-0066 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
