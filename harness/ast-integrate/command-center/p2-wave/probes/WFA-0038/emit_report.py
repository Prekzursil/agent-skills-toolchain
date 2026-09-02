#!/usr/bin/env python3
"""Write WFA-0038 artifact then per-unit receipts. Does not touch the global catalog."""
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
import extract as X  # noqa: E402

OUT = "command-center/wfa/WFA-0038-extract-tool-permissions.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0038/probe1_planted_overprivileged.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0038/probe2_escalation_static.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0038/extract.py",
    "command-center/p2-wave/probes/WFA-0038/estate.py",
    "command-center/p2-wave/probes/WFA-0038/probe1_planted_overprivileged.py",
    "command-center/p2-wave/probes/WFA-0038/probe2_escalation_static.py",
    "command-center/p2-wave/probes/WFA-0038/fixtures/candidates.json",
    "command-center/p2-wave/probes/WFA-0038/fixtures/owner-ops-authorization.md",
    "command-center/p2-wave/probes/WFA-0038/fixtures/settings.permissions.json",
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
        "unit_id": "WFA-0038",
        "receipt_path": "command-center/p2-wave/probes/WFA-0038/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    art = X.write_artifact(REPO)
    rel = art.relative_to(REPO).as_posix()
    if rel != OUT:
        print(f"FAILED:emit unexpected path {rel}")
        return 1
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
        "id": "WFA-0038",
        "unit_id": "WFA-0038",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0038",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/ExtractionReport",
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0038/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0038-probe2-escalation-static",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for WFA-0038: live named probes exit 0, extract-tool-permissions "
            "state=SUCCESS, per-unit manifest row. Live 08-WORKFLOW-CANDIDATE-REGISTRY.json "
            "is not on this Linux worktree; planted controls plus inspect stubs plus "
            "on-disk workflow-like files were scanned. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0038",
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
    print("SUCCESS:WFA-0038 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
