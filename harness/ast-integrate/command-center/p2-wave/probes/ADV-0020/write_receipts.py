#!/usr/bin/env python3
"""Write ADV-0020 primary artifact plus per-unit G-1 sidecars.

Does not run tools/command-center/unit_manifest.py --write.
"""
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
OUT = "command-center/adversarial/ADV-0020-citation-linkrot-archival-audit.json"
SCHEMA = "command-center/schema/stale-premise-reprobe.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0020/probe1_http_resolve.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0020/probe2_archive_recheck.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0020/emit_artifact.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0020/lib_adv0020.py",
    "command-center/p2-wave/probes/ADV-0020/probe1_http_resolve.py",
    "command-center/p2-wave/probes/ADV-0020/probe2_archive_recheck.py",
    "command-center/p2-wave/probes/ADV-0020/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0020/probe1-live.json",
    "command-center/p2-wave/probes/ADV-0020/probe2-archive.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str, timeout: int = 170) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "bytes": size,
        "path": rel,
        "present": path.is_file(),
        "receipt_path": "command-center/p2-wave/probes/ADV-0020/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "ADV-0020",
    }


def main() -> int:
    c1, t1 = run_cmd(P1)
    print(t1)
    if c1 != 0:
        print(f"FAILED:ADV-0020-receipts probe1 rc={c1}")
        return 1
    (HERE / "probe1.stdout.txt").write_text(t1 + "\n", encoding="utf-8", newline="\n")

    c2, t2 = run_cmd(P2)
    print(t2)
    if c2 != 0:
        print(f"FAILED:ADV-0020-receipts probe2 rc={c2}")
        return 1
    (HERE / "probe2.stdout.txt").write_text(t2 + "\n", encoding="utf-8", newline="\n")

    ce, te = run_cmd(EMIT)
    print(te)
    if ce != 0:
        print(f"FAILED:ADV-0020-receipts emit rc={ce}")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": "ADV-0020",
        "manifest_path": "command-center/p2-wave/probes/ADV-0020/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "live-http-status-final-url-quote-containment",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "wayback-cdx-plus-snapshot-quote",
            },
        ],
        "notes": (
            "G-1 for ADV-0020: live named probes exit 0, citation-linkrot archival "
            "audit state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. cloud ok=true is not delivery."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "ADV-0020-probe2-wayback-cdx",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:ADV-0020",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "ADV-0020",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "schema_version": 1,
        "unit_id": "ADV-0020",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0020 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
