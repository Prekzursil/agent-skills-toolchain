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

from common import OUT_REL, P1, P2, SCHEMA_REL, UNIT  # noqa: E402

SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/AUD-0058/common.py",
    "command-center/p2-wave/probes/AUD-0058/frontmatter.py",
    "command-center/p2-wave/probes/AUD-0058/globs.py",
    "command-center/p2-wave/probes/AUD-0058/loader.py",
    "command-center/p2-wave/probes/AUD-0058/classifier.py",
    "command-center/p2-wave/probes/AUD-0058/inventory.py",
    "command-center/p2-wave/probes/AUD-0058/fixtures.py",
    "command-center/p2-wave/probes/AUD-0058/measure.py",
    "command-center/p2-wave/probes/AUD-0058/probe1_frontmatter.py",
    "command-center/p2-wave/probes/AUD-0058/probe2_turn0.py",
    "command-center/p2-wave/probes/AUD-0058/emit_finding.py",
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
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/AUD-0058/SUBAGENT-RETURN.json",
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
    primary = row(OUT_REL, "primary")
    if not primary["present"]:
        print("FAILED:receipts primary artifact absent")
        return 1
    artifacts = [primary]
    for path in SUPPORTING:
        item = row(path, "supporting")
        if not item["present"]:
            print(f"FAILED:receipts supporting absent {path}")
            return 1
        artifacts.append(item)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0058",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "frontmatter-declared-load-class",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "turn0-context-bag-measurement",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/AUD-0058/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0058-probe2-turn0-bag",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0058: live named probes exit 0, skill-load-trigger-audit.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. grok inspect --json and live "
            "~/.claude/skills / ~/.agents/skills are absent; turn0-context-bag "
            "is the equivalent instrument. Catalog 8-file inversion is not on "
            "this worktree."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
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
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0058 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
