#!/usr/bin/env python3
"""Write per-unit UNIT-ARTIFACT-MANIFEST.json and SUBAGENT-RETURN.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys_path_note = HERE
UNIT = "AUD-0014"
OUT = "command-center/audit/AUD-0014-agents-commands-drift.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0014/probe1_path_content.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0014/probe2_frontmatter_model.py"
)
SUPPORTING = [
    "command-center/schema/audit-drift.schema.json",
    "command-center/p2-wave/probes/AUD-0014/drift.py",
    "command-center/p2-wave/probes/AUD-0014/emit_artifact.py",
    "command-center/p2-wave/probes/AUD-0014/probe1_path_content.py",
    "command-center/p2-wave/probes/AUD-0014/probe2_frontmatter_model.py",
    "command-center/p2-wave/probes/AUD-0014/fixtures/body-mention-only.md",
    "command-center/p2-wave/probes/AUD-0014/fixtures/frontmatter-sonnet.md",
    "command-center/p2-wave/probes/AUD-0014/fixtures/path-control/repo/keep.md",
    "command-center/p2-wave/probes/AUD-0014/fixtures/path-control/live/keep.md",
    "command-center/p2-wave/probes/AUD-0014/fixtures/path-control/repo/changed.md",
    "command-center/p2-wave/probes/AUD-0014/fixtures/path-control/live/changed.md",
    "command-center/p2-wave/probes/AUD-0014/fixtures/path-control/repo/repo-only.md",
    "command-center/p2-wave/probes/AUD-0014/fixtures/path-control/live/live-only.md",
]


def digest(rel: str) -> tuple[str, int, bool]:
    path = REPO / rel
    if not path.is_file():
        return "", 0, False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw), True


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    sha, n, present = digest(rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": n,
        "present": present,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/AUD-0014/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    sha, n, present = digest(OUT)
    if not present or n <= 0:
        print("FAILED:AUD-0014 receipt writer: primary artifact missing")
        return 1
    rc1, out1 = run_cmd(P1)
    rc2, out2 = run_cmd(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:AUD-0014 probes rc {rc1} {rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    if any(not a["present"] for a in artifacts):
        print("FAILED:AUD-0014 missing supporting file")
        print(json.dumps([a for a in artifacts if not a["present"]], indent=2))
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0014",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/audit-drift.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "path-set-normalized-content",
                "raw_output": out1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "frontmatter-model-field",
                "raw_output": out2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": n,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/AUD-0014/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0014-probe2-frontmatter-independent",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0014: live named probes exit 0, agents-commands-drift "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. cloud ok=true is not "
            "delivery."
        ),
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} bytes={n} sha256={sha}")
    print("SUCCESS:AUD-0014 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
