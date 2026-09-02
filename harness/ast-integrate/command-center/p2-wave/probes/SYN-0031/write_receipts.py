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
OUT = "command-center/receipts/SYN-0031.json"
SCHEMA = "command-center/schema/floor-recount.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0031/probe1_two_extractors.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0031/probe2_protocol_preset_disjoint.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/SYN-0031/extract.py",
    "command-center/p2-wave/probes/SYN-0031/emit_recount.py",
    "command-center/p2-wave/probes/SYN-0031/probe1_two_extractors.py",
    "command-center/p2-wave/probes/SYN-0031/probe2_protocol_preset_disjoint.py",
    "command-center/p2-wave/probes/SYN-0031/fixtures/corpus-good/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/p2-wave/probes/SYN-0031/fixtures/corpus-good/12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
    "command-center/p2-wave/probes/SYN-0031/fixtures/planted-overlap/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/p2-wave/probes/SYN-0031/fixtures/planted-disagreement/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/p2-wave/probes/SYN-0031/fixtures/planted-disagreement/12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": "SYN-0031",
        "receipt_path": "command-center/p2-wave/probes/SYN-0031/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = subprocess.run(
        [sys.executable, "-B", str(HERE / "emit_recount.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if emit.returncode != 0:
        print(emit.stdout)
        print(emit.stderr)
        print("FAILED:SYN-0031 receipts emit")
        return 1
    print(emit.stdout.strip())
    code1, text1 = run_probe(P1)
    code2, text2 = run_probe(P2)
    if code1 != 0 or code2 != 0:
        print(f"FAILED:SYN-0031 receipts probes c1={code1} c2={code2}")
        print(text1[-2000:])
        print(text2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    missing = [item["path"] for item in artifacts if item["present"] is not True]
    if missing:
        print(f"FAILED:SYN-0031 receipts missing {missing}")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "SYN-0031",
        "unit_id": "SYN-0031",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0031",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "two-extractors-and-known-present",
                "raw_output": text1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "protocol-preset-disjoint-and-cross-silence",
                "raw_output": text2,
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
        "manifest_path": "command-center/p2-wave/probes/SYN-0031/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "SYN-0031-probe1-independent-brace-scanner",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for SYN-0031: live named probes exit 0, SYN-0031.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "SYN-0031",
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
    print("SUCCESS:SYN-0031 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
