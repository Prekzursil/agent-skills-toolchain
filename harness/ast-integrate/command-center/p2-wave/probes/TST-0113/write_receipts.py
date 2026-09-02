#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.

Does not invoke tools/command-center/unit_manifest.py --write.
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
sys.path.insert(0, str(HERE))
from emit_receipt import write_receipt  # noqa: E402

UNIT = "TST-0113"
OUT = f"command-center/receipts/{UNIT}.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"command-center/p2-wave/probes/{UNIT}/probe1_every_path_triggered.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"command-center/p2-wave/probes/{UNIT}/probe2_rubric_on_captured_text.py"
)
SUPPORTING = [
    "tools/plugin/client_negotiate.py",
    "tools/plugin/install_gate.py",
    f"command-center/p2-wave/probes/{UNIT}/inventory.py",
    f"command-center/p2-wave/probes/{UNIT}/rubric.py",
    f"command-center/p2-wave/probes/{UNIT}/probe1_every_path_triggered.py",
    f"command-center/p2-wave/probes/{UNIT}/probe2_rubric_on_captured_text.py",
    f"command-center/p2-wave/probes/{UNIT}/emit_receipt.py",
    f"command-center/p2-wave/probes/{UNIT}/fixtures/bare-messages.json",
    f"command-center/p2-wave/probes/{UNIT}/fixtures/unparsable-min-manifest.json",
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
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    write_receipt()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} write_receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["present"]]
    if missing:
        print(f"FAILED:{UNIT} write_receipts missing", missing)
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UNIT}",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "every-error-path-triggered",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "rubric-on-captured-text",
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
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": f"{UNIT}-probe2-rubric-on-captured-text",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            f"G-1 for {UNIT}: live named probes exit 0, receipts/{UNIT}.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
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
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote return+manifest primary sha256={primary['sha256']} "
        f"bytes={primary['bytes']}"
    )
    print(f"SUCCESS:{UNIT} write_receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
