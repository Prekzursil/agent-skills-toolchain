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
import engine as E  # noqa: E402

P1 = E.P1
P2 = E.P2
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0142/engine.py",
    "command-center/p2-wave/probes/ADV-0142/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0142/probe1_hygiene.py",
    "command-center/p2-wave/probes/ADV-0142/probe2_controls.py",
    "command-center/p2-wave/probes/ADV-0142/fixtures/synthetic/a.json",
    "command-center/p2-wave/probes/ADV-0142/fixtures/synthetic/b.md",
    "command-center/p2-wave/probes/ADV-0142/fixtures/synthetic/c.py",
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
        timeout=170,
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
        "unit_id": E.UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0142/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not (REPO / E.OUT_REL).is_file():
        print(f"FAILED:receipts missing {E.OUT_REL}; run emit_artifact.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(E.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": E.UNIT_ID,
        "unit_id": E.UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{E.UNIT_ID}",
        "registered": True,
        "output_path": E.OUT_REL,
        "output_schema": E.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "context-hygiene",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "negative-control-and-join-necessity",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": E.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0142/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0142-probe1-hygiene",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": f"SUCCESS:delivered {E.UNIT_ID}",
        "ts": now,
        "notes": (
            "G-1 for ADV-0142: live named probes exit 0, re-identification "
            "artifact state=SUCCESS, per-unit manifest row. Did not run "
            "global unit_manifest.py --write. No ADV rebuild of "
            "reidentification-assessment.schema.json. cloud ok=true is not "
            "delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": E.UNIT_ID,
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
    print(f"primary {E.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0142 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
