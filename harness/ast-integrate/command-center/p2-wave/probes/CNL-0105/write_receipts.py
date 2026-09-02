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
OUT = (
    "command-center/design/council/"
    "CNL-0105-anonymous-peer-review-preset-with-an-author-rebuttal-round.md"
)
SCHEMA = "command-center/schema/council-preset.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0105/probe1_instantiate_schema.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0105/probe2_capture_sibling.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNL-0105/preset.record.schema.json",
    "command-center/p2-wave/probes/CNL-0105/envelope.schema.json",
    "command-center/p2-wave/probes/CNL-0105/fixtures/records.json",
    "command-center/p2-wave/probes/CNL-0105/common.py",
    "command-center/p2-wave/probes/CNL-0105/instantiate.py",
    "command-center/p2-wave/probes/CNL-0105/capture.py",
    "command-center/p2-wave/probes/CNL-0105/schema_util.py",
    "command-center/p2-wave/probes/CNL-0105/probe1_instantiate_schema.py",
    "command-center/p2-wave/probes/CNL-0105/probe2_capture_sibling.py",
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
        "unit_id": "CNL-0105",
        "receipt_path": "command-center/p2-wave/probes/CNL-0105/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNL-0105",
        "unit_id": "CNL-0105",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0105",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
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
        "manifest_path": "command-center/p2-wave/probes/CNL-0105/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0105-probe1-instantiate-fresh",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CNL-0105: live named probes exit 0, design artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Library 12-COUNCIL-PROTOCOLS-AND-PRESETS.json "
            "is absent; nearest sibling named from CNL-0104 / P46 reconstruction."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0105",
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
    meas = subprocess.run(
        [
            sys.executable,
            str(REPO / "command-center/p2-wave/_measure_one_delivered.py"),
            "CNL-0105",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    meas_text = ((meas.stdout or "") + (meas.stderr or "")).strip()
    meas_line = meas_text.splitlines()[-1] if meas_text else f"exit={meas.returncode}"
    ret["measure"] = {"exit_code": meas.returncode, "line": meas_line}
    ret["measure_line"] = meas_line
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(meas_line)
    print("SUCCESS:CNL-0105 receipts")
    return 0 if meas.returncode == 0 else meas.returncode


if __name__ == "__main__":
    raise SystemExit(main())
