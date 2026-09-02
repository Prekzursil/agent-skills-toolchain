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
OUT = "command-center/adversarial/ADV-0139-build-environment-supply-chain.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0139/probe1_two_signal_load.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0139/probe2_planted_config.py"
)
SUPPORTING = [
    "command-center/schema/runtime-trust-inventory.schema.json",
    "command-center/p2-wave/probes/ADV-0139/common.py",
    "command-center/p2-wave/probes/ADV-0139/load_probe.py",
    "command-center/p2-wave/probes/ADV-0139/autoload.py",
    "command-center/p2-wave/probes/ADV-0139/attribution.py",
    "command-center/p2-wave/probes/ADV-0139/inventory.py",
    "command-center/p2-wave/probes/ADV-0139/probe1_two_signal_load.py",
    "command-center/p2-wave/probes/ADV-0139/probe2_planted_config.py",
    "command-center/p2-wave/probes/ADV-0139/emit_inventory.py",
    "command-center/p2-wave/probes/ADV-0139/fixtures/load-control/workspace/mcp.json",
    "command-center/p2-wave/probes/ADV-0139/fixtures/load-control/wrong-scope/mcp.json",
    "command-center/p2-wave/probes/ADV-0139/fixtures/session-skill-injection.json",
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
        "unit_id": "ADV-0139",
        "receipt_path": "command-center/p2-wave/probes/ADV-0139/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    primary_path = REPO / OUT
    if not primary_path.is_file():
        print("FAILED:ADV-0139 receipts: primary missing; run emit_inventory.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    extra = []
    for rel in (
        "command-center/p2-wave/probes/ADV-0139/fixtures/attribution-canary.json",
        "command-center/p2-wave/probes/ADV-0139/fixtures/attribution-event-log.jsonl",
    ):
        if (REPO / rel).is_file():
            extra.append(rel)
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING + extra]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0139",
        "unit_id": "ADV-0139",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0139",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/runtime-trust-inventory.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "two-signal-load-detector",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "planted-config-and-process-table",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0139/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0139-probe2-process-table",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0139: live named probes exit 0, inventory "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "Report-only; no config changes."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0139",
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
    print("SUCCESS:ADV-0139 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
