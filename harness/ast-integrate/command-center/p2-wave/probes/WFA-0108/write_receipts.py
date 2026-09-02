#!/usr/bin/env python3
"""Per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json for WFA-0108."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "WFA-0108"
OUT_REL = "command-center/wfa/WFA-0108-fusion-capability-loss-detector.json"
RECEIPT_REL = "command-center/p2-wave/probes/WFA-0108/SUBAGENT-RETURN.json"
MANIFEST_REL = "command-center/p2-wave/probes/WFA-0108/UNIT-ARTIFACT-MANIFEST.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0108/probe1_planted_lossy.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0108/probe2_disconnect_and_gate.py"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(path: str, role: str) -> dict:
    fp = REPO / path
    sha, nbytes = digest_file(fp)
    return {
        "path": path,
        "sha256": sha,
        "bytes": nbytes,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": RECEIPT_REL,
        "role": role,
    }


def main() -> int:
    supporting = [
        "command-center/p2-wave/probes/WFA-0108/fixtures.py",
        "command-center/p2-wave/probes/WFA-0108/detector.py",
        "command-center/p2-wave/probes/WFA-0108/emit.py",
        "command-center/p2-wave/probes/WFA-0108/probe1_planted_lossy.py",
        "command-center/p2-wave/probes/WFA-0108/probe2_disconnect_and_gate.py",
        "command-center/p2-wave/probes/WFA-0108/write_receipts.py",
    ]
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code1 != 0 or code2 != 0:
        print("FAILED:WFA-0108 write_receipts probes did not exit 0")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    art = REPO / OUT_REL
    sha, nbytes = digest_file(art)
    artifacts = [row(OUT_REL, "primary")]
    for rel in supporting:
        artifacts.append(row(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    receipt = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UNIT}",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "planted-lossy-both-signals",
                "raw_output": out1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "behavioural-disconnect-and-p1-gate",
                "raw_output": out2[-4000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": sha,
                "bytes": nbytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": MANIFEST_REL,
        "reviewer": {
            "reviewer_id": "WFA-0108-probe2-disconnect-and-p1-gate",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 for WFA-0108: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }

    man_path = REPO / MANIFEST_REL
    rec_path = REPO / RECEIPT_REL
    with rec_path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(receipt, fh, indent=1, ensure_ascii=True)
        fh.write("\n")
    with man_path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=True)
        fh.write("\n")
    print(f"wrote {RECEIPT_REL}")
    print(f"wrote {MANIFEST_REL}")
    print(f"primary sha256={sha} bytes={nbytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
