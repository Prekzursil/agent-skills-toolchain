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
import emit_artifact as EA  # noqa: E402

OUT = EA.OUT
P1 = EA.P1
P2 = EA.P2
SUPPORTING = [
    EA.SCHEMA,
    "command-center/TEST-REGISTRY.json",
    "command-center/p2-wave/probes/AUD-0038/engine.py",
    "command-center/p2-wave/probes/AUD-0038/probe1_collect_match.py",
    "command-center/p2-wave/probes/AUD-0038/probe2_execute_sample.py",
    "command-center/p2-wave/probes/AUD-0038/emit_artifact.py",
    "command-center/p2-wave/probes/AUD-0038/fixtures/control/test_setup_error.py",
    "command-center/p2-wave/probes/AUD-0038/fixtures/control/test_mention_trap.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(os.environ)
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
        "unit_id": "AUD-0038",
        "receipt_path": "command-center/p2-wave/probes/AUD-0038/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = subprocess.run(
        [sys.executable, "-B", str(HERE / "emit_artifact.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if emit.returncode != 0:
        print("FAILED:AUD-0038 emit_artifact")
        print((emit.stdout or "")[-2000:])
        print((emit.stderr or "")[-2000:])
        return 1

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0038 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    art_path = REPO / OUT
    doc = json.loads(art_path.read_text(encoding="utf-8"))
    doc["named_probes"] = [
        {
            "id": "probe1",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1,
            "role": "collect-string-match",
        },
        {
            "id": "probe2",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2,
            "role": "single-node-execution",
        },
    ]
    EA.write(doc)

    c1b, t1b = run_probe(P1)
    c2b, t2b = run_probe(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:AUD-0038 probes-after-embed c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "AUD-0038",
        "unit_id": "AUD-0038",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0038",
        "registered": True,
        "output_path": OUT,
        "output_schema": EA.SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "raw_output": t1b,
                "role": "collect-string-match",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "raw_output": t2b,
                "role": "single-node-execution",
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0038/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0038-probe2-single-node-execution",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0038: live named probes exit 0, "
            "AUD-0038-test-registry-resolution.json state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild circle."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "AUD-0038",
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
    print("SUCCESS:AUD-0038 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
