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
sys.path.insert(0, str(HERE))
from detector import repo_root  # noqa: E402

OUT = "command-center/design/council/CNL-0094-evidence-free-majority-blocker.md"
SCHEMA = "command-center/schema/council-detector-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0094/probe1_planted_bad.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0094/probe2_known_good.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0094/emit_spec.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNL-0094/artifact.schema.json",
    "command-center/p2-wave/probes/CNL-0094/detector.py",
    "command-center/p2-wave/probes/CNL-0094/fixtures.py",
    "command-center/p2-wave/probes/CNL-0094/recount.py",
    "command-center/p2-wave/probes/CNL-0094/probe1_planted_bad.py",
    "command-center/p2-wave/probes/CNL-0094/probe2_known_good.py",
    "command-center/p2-wave/probes/CNL-0094/emit_spec.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(repo: Path, cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(repo),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(repo: Path, rel: str, role: str) -> dict:
    path = repo / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "CNL-0094",
        "receipt_path": "command-center/p2-wave/probes/CNL-0094/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    repo = repo_root()
    ce, te = run_cmd(repo, EMIT)
    if ce != 0:
        print(f"FAILED:CNL-0094 receipts emit rc={ce}")
        print(te[-3000:])
        return 1
    c1, t1 = run_cmd(repo, P1)
    c2, t2 = run_cmd(repo, P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNL-0094 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(repo, OUT, "primary")
    artifacts = [primary] + [row(repo, p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNL-0094",
        "unit_id": "CNL-0094",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0094",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/CNL-0094/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0094-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CNL-0094: live named probes exit 0, evidence-free majority "
            "blocker spec state=SUCCESS, per-unit manifest row. Did not run "
            "global unit_manifest.py --write. No ADV rebuild."
        ),
        "emit_output": te,
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0094",
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
    print("SUCCESS:CNL-0094 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
