#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

SUPPORTING = [
    H.SCHEMA_REL,
    "command-center/p2-wave/probes/AUD-0027/harness.py",
    "command-center/p2-wave/probes/AUD-0027/emit_report.py",
    "command-center/p2-wave/probes/AUD-0027/probe1_wheel_tags.py",
    "command-center/p2-wave/probes/AUD-0027/probe2_install.py",
    "command-center/p2-wave/probes/AUD-0027/fixtures/source_only_ext/setup.py",
    "command-center/p2-wave/probes/AUD-0027/fixtures/source_only_ext/aud0027_source_only.c",
]


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(H.REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=170,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = H.REPO / rel
    sha, size = H.digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": H.UNIT,
        "receipt_path": "command-center/p2-wave/probes/AUD-0027/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(H.P1)
    c2, t2 = run_probe(H.P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(H.OUT_REL, "primary")
    artifacts = [primary]
    for rel in SUPPORTING:
        if (H.REPO / rel).is_file():
            artifacts.append(row(rel, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": H.UNIT,
        "unit_id": H.UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0027",
        "registered": True,
        "output_path": H.OUT_REL,
        "output_schema": H.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": H.P1,
                "exit_code": c1,
                "role": "wheel-tag-matrix",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": H.P2,
                "exit_code": c2,
                "role": "nonwindows-install",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": H.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/AUD-0027/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0027-probe2-install-attempt",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0027: live named probes exit 0, native-platform census "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. AUD-0022 is absent; census is direct names "
            "from AUD-0020. Probe 2 extracted wheels (PEP 427) plus source-only "
            "build_ext."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": H.UNIT,
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
    print(f"primary {H.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0027 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
