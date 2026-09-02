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
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import emit_report as E  # noqa: E402

OUT = "command-center/receipts/TST-0040.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0040/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0040/probe2_registry_census.py"
)
SUPPORTING = [
    "command-center/schema/claim-record.schema.json",
    "command-center/p2-wave/probes/TST-0040/claim-contract.schema.json",
    "command-center/schema/conformance-report.schema.json",
    "command-center/p2-wave/probes/TST-0040/contract.py",
    "command-center/p2-wave/probes/TST-0040/emit_report.py",
    "command-center/p2-wave/probes/TST-0040/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0040/probe2_registry_census.py",
    "command-center/p2-wave/probes/TST-0040/schema_check.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = {**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "TST-0040",
        "receipt_path": "command-center/p2-wave/probes/TST-0040/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    erc = E.main()
    if erc != 0:
        print(f"FAILED:TST-0040 emit rc={erc}")
        return erc
    code1, text1 = run_probe(P1)
    code2, text2 = run_probe(P2)
    if code1 != 0 or code2 != 0:
        print(f"FAILED:TST-0040 receipts probes c1={code1} c2={code2}")
        print(text1[-2000:])
        print(text2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "TST-0040",
        "unit_id": "TST-0040",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0040",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/conformance-report.schema.json",
        "measure_line": "SUCCESS:delivered TST-0040",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered TST-0040"},
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "raw_output": text1,
                "role": "both-states-and-negatives",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "raw_output": text2,
                "role": "registry-census-overclaim",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0040/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0040-probe2-independent-census",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0040: live named probes exit 0, TST-0040.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Registry census is from disk; "
            "CLAIM-REGISTRY.json absence is not treated as vacuous YES."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0040",
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
    print("SUCCESS:TST-0040 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
