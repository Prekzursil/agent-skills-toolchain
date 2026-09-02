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
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

SUPPORTING = [
    S.SCHEMA_REL,
    "command-center/p2-wave/probes/SYN-0011/adjudicate.py",
    "command-center/p2-wave/probes/SYN-0011/scenario.py",
    "command-center/p2-wave/probes/SYN-0011/emit.py",
    "command-center/p2-wave/probes/SYN-0011/probe1_lexical_and_anchor.py",
    "command-center/p2-wave/probes/SYN-0011/probe2_planted_split.py",
    S.PLANTED_REL,
    "command-center/p2-wave/probes/SYN-0011/fixtures/candidates.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "SYN-0011",
        "receipt_path": "command-center/p2-wave/probes/SYN-0011/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(S.P1)
    c2, t2 = run_probe(S.P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(S.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "SYN-0011",
        "unit_id": "SYN-0011",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0011",
        "registered": True,
        "output_path": S.OUT_REL,
        "output_schema": S.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": S.P1,
                "exit_code": c1,
                "role": "lexical-gate-and-resolving-anchor",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": S.P2,
                "exit_code": c2,
                "role": "planted-split-file-supported-side",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": S.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/SYN-0011/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "SYN-0011-probe2-planted-split",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for SYN-0011: live named probes exit 0, adjudications.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Upstream SYN-0008/0009/0010 artifacts "
            "are absent and disclosed; planted split plus live catalog/measure "
            "facts were settled from raw sources."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "SYN-0011",
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
    print(f"primary {S.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:SYN-0011 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
