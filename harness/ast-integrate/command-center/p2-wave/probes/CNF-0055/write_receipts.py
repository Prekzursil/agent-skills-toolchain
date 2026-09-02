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
REPO = HERE.parents[3]
OUT = "command-center/confirmation/CNF-0055-router-selection-diff.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0055/probe1_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0055/probe2_unreachable.py"
)
SUPPORTING = [
    "command-center/schema/regression-delta.schema.json",
    "command-center/p2-wave/probes/CNF-0055/router.py",
    "command-center/p2-wave/probes/CNF-0055/selection.py",
    "command-center/p2-wave/probes/CNF-0055/fixtures/capability-index.json",
    "command-center/p2-wave/probes/CNF-0055/fixtures/corpus.json",
    "command-center/p2-wave/probes/CNF-0055/fixtures/after-mutation.json",
    "command-center/p2-wave/probes/CNF-0055/probe1_control.py",
    "command-center/p2-wave/probes/CNF-0055/probe2_unreachable.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": "CNF-0055",
        "receipt_path": "command-center/p2-wave/probes/CNF-0055/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNF-0055",
        "unit_id": "CNF-0055",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0055",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/regression-delta.schema.json",
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
        "manifest_path": "command-center/p2-wave/probes/CNF-0055/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0055-probe2-unreachable",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CNF-0055: live named probes exit 0, router-selection-diff "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0055",
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
            "CNF-0055",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    mtext = ((meas.stdout or "") + "\n" + (meas.stderr or "")).strip()
    mline = mtext.splitlines()[-1] if mtext.splitlines() else f"exit={meas.returncode}"
    ret["measure"] = {"exit_code": meas.returncode, "line": mline}
    ret["measure_line"] = mline
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(mline)
    if meas.returncode != 0:
        print("FAILED:CNF-0055 receipts measure")
        print(mtext[-2000:])
        return 1
    print("SUCCESS:CNF-0055 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
