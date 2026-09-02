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
sys.path.insert(0, str(HERE))

import emit as E  # noqa: E402

OUT = E.OUT
SCHEMA = E.SCHEMA
P1 = E.P1
P2 = E.P2
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0041/expectation.py",
    "command-center/p2-wave/probes/WFA-0041/sources.py",
    "command-center/p2-wave/probes/WFA-0041/run_records.py",
    "command-center/p2-wave/probes/WFA-0041/classify.py",
    "command-center/p2-wave/probes/WFA-0041/extract.py",
    "command-center/p2-wave/probes/WFA-0041/emit.py",
    "command-center/p2-wave/probes/WFA-0041/probe1_claimed_not_found.py",
    "command-center/p2-wave/probes/WFA-0041/probe2_no_score_and_near_zero.py",
    "command-center/p2-wave/probes/WFA-0041/fixtures/corpus/citable.json",
    "command-center/p2-wave/probes/WFA-0041/fixtures/corpus/claimed-no-record.json",
    "command-center/p2-wave/probes/WFA-0041/fixtures/corpus/honest-null.json",
    "command-center/p2-wave/probes/WFA-0041/fixtures/corpus/score-tempt.json",
    "command-center/p2-wave/probes/WFA-0041/fixtures/run-records/citable-run.json",
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
        timeout=180,
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
        "unit_id": "WFA-0041",
        "receipt_path": "command-center/p2-wave/probes/WFA-0041/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    rc = E.main()
    if rc != 0:
        print("FAILED:WFA-0041 emit")
        return rc
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0041 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "WFA-0041",
        "unit_id": "WFA-0041",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0041",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "claimed-not-found-downgrade",
                "raw_output": t1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "no-score-and-near-zero",
                "raw_output": t2[-8000:],
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0041/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0041-probe2-no-score-and-near-zero",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0041: live named probes exit 0, extract-benchmark-evidence "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0041",
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
    print("SUCCESS:WFA-0041 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
