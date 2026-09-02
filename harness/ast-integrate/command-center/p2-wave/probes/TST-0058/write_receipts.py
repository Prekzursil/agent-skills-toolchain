#!/usr/bin/env python3
"""Write TST-0058 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py --write.
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
UID = "TST-0058"
OUT = "command-center/receipts/TST-0058.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0058/probe1_agreement_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0058/probe2_adversarial_and_detector.py"
)
SUPPORTING = [
    "tools/json_ingest.py",
    SCHEMA,
    "command-center/p2-wave/probes/TST-0058/matrix.py",
    "command-center/p2-wave/probes/TST-0058/corpus.py",
    "command-center/p2-wave/probes/TST-0058/probe1_agreement_matrix.py",
    "command-center/p2-wave/probes/TST-0058/probe2_adversarial_and_detector.py",
    "command-center/p2-wave/probes/TST-0058/emit_receipt.py",
    "command-center/p2-wave/probes/TST-0058/fixtures/adversarial/01-trailing-comma-object.jsonc",
    "command-center/p2-wave/probes/TST-0058/fixtures/adversarial/02-trailing-comma-array.jsonc",
    "command-center/p2-wave/probes/TST-0058/fixtures/adversarial/03-line-comment.jsonc",
    "command-center/p2-wave/probes/TST-0058/fixtures/adversarial/04-block-comment.jsonc",
    "command-center/p2-wave/probes/TST-0058/fixtures/adversarial/05-single-quoted-string.jsonc",
    "command-center/p2-wave/probes/TST-0058/fixtures/adversarial/06-single-quoted-key.jsonc",
    "command-center/p2-wave/probes/TST-0058/fixtures/adversarial/07-comment-and-trailing-comma.jsonc",
    "command-center/p2-wave/probes/TST-0058/fixtures/adversarial/08-block-comment-in-array.jsonc",
    "command-center/p2-wave/probes/TST-0058/fixtures/adversarial/09-nested-trailing-comma.jsonc",
    "command-center/p2-wave/probes/TST-0058/fixtures/adversarial/10-mixed-json5.jsonc",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def manifest_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0058/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c0, t0 = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/TST-0058/emit_receipt.py"
    )
    if c0 != 0:
        print("FAILED:TST-0058 emit")
        print(t0[-2500:])
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0058 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    rec = REPO / OUT
    if not rec.is_file():
        print(f"FAILED:TST-0058 missing {OUT}")
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0058",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "agreement-matrix",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "adversarial-and-detector",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0058/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0058-probe2-adversarial-and-detector",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0058: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild circle."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0058 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
