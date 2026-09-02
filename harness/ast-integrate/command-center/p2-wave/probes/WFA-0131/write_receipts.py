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
REPO = HERE.parents[3]
OUT = "command-center/foundry/WFA-0131-benchmark-gaming-adversarial-control.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0131/probe1_control_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0131/probe2_naive_pin_and_genuine.py"
)
SUPPORTING = [
    "command-center/schema/foundry-artifact.schema.json",
    "command-center/p2-wave/probes/WFA-0131/registry.py",
    "command-center/p2-wave/probes/WFA-0131/corpus.py",
    "command-center/p2-wave/probes/WFA-0131/engine.py",
    "command-center/p2-wave/probes/WFA-0131/variants.py",
    "command-center/p2-wave/probes/WFA-0131/campaign.py",
    "command-center/p2-wave/probes/WFA-0131/emit_artifact.py",
    "command-center/p2-wave/probes/WFA-0131/probe1_control_both_states.py",
    "command-center/p2-wave/probes/WFA-0131/probe2_naive_pin_and_genuine.py",
    "command-center/p2-wave/probes/WFA-0131/fixtures/registry.json",
    "command-center/p2-wave/probes/WFA-0131/fixtures/registry.pin",
    "command-center/p2-wave/probes/WFA-0131/fixtures/cases.json",
    "command-center/p2-wave/probes/WFA-0131/fixtures/runs/honest_baseline.json",
    "command-center/p2-wave/probes/WFA-0131/fixtures/runs/genuine_improvement.json",
    "command-center/p2-wave/probes/WFA-0131/fixtures/runs/gamed_stage_padding.json",
    "command-center/p2-wave/probes/WFA-0131/fixtures/runs/gamed_case_overfitting.json",
    "command-center/p2-wave/probes/WFA-0131/fixtures/runs/gamed_retry_until_pass.json",
    "command-center/p2-wave/probes/WFA-0131/fixtures/runs/gamed_output_shaping.json",
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
        "unit_id": "WFA-0131",
        "receipt_path": "command-center/p2-wave/probes/WFA-0131/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not (REPO / OUT).is_file():
        print("FAILED:WFA-0131 artifact missing; run emit_artifact.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0131 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary]
    for rel in SUPPORTING:
        if not (REPO / rel).is_file():
            print(f"FAILED:WFA-0131 missing supporting {rel}")
            return 1
        artifacts.append(row(rel, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "WFA-0131",
        "unit_id": "WFA-0131",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0131",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/foundry-artifact.schema.json#/$defs/adversarial-control"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "control-both-states",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "naive-accept-pin-genuine",
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0131/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0131-probe2-independent-arithmetic-and-pin",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0131: live named probes exit 0, foundry adversarial-control "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Naive predicate accepts gamed variants; "
            "gaming-control-v1 fires on them and stays silent on the honest baseline."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0131",
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
    print("SUCCESS:WFA-0131 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
