#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/adversarial/ADV-0136-independence-attestation.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0136/probe1_planted_collusion.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0136/probe2_reviewer_from_logs.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0136/emit_ledger.py"
)
SUPPORTING = [
    "command-center/schema/attestation-ledger.schema.json",
    "command-center/p2-wave/probes/ADV-0136/attestation.py",
    "command-center/p2-wave/probes/ADV-0136/harvest.py",
    "command-center/p2-wave/probes/ADV-0136/rederive.py",
    "command-center/p2-wave/probes/ADV-0136/emit_ledger.py",
    "command-center/p2-wave/probes/ADV-0136/schema_offline.py",
    "command-center/p2-wave/probes/ADV-0136/probe1_planted_collusion.py",
    "command-center/p2-wave/probes/ADV-0136/probe2_reviewer_from_logs.py",
    "command-center/p2-wave/probes/ADV-0136/fixtures/events/planted-collusion.json",
    "command-center/p2-wave/probes/ADV-0136/fixtures/events/planted-driver-confound.json",
    "command-center/p2-wave/probes/ADV-0136/fixtures/events/planted-declared-only.json",
    "command-center/p2-wave/probes/ADV-0136/fixtures/events/known-good.json",
    "command-center/p2-wave/probes/ADV-0136/fixtures/logs/planted-collusion.jsonl",
    "command-center/p2-wave/probes/ADV-0136/fixtures/logs/planted-driver-confound.jsonl",
    "command-center/p2-wave/probes/ADV-0136/fixtures/logs/planted-declared-only.jsonl",
    "command-center/p2-wave/probes/ADV-0136/fixtures/logs/known-good.jsonl",
    "command-center/p2-wave/probes/ADV-0136/fixtures/prompts/collusion-shared.txt",
    "command-center/p2-wave/probes/ADV-0136/fixtures/prompts/good-anthropic.txt",
    "command-center/p2-wave/probes/ADV-0136/fixtures/prompts/good-openai.txt",
    "command-center/p2-wave/probes/ADV-0136/fixtures/prompts/good-google.txt",
    "command-center/p2-wave/probes/ADV-0136/fixtures/prompts/confound-gpt-arm.txt",
    "command-center/p2-wave/probes/ADV-0136/fixtures/prompts/confound-opus-arm.txt",
    "command-center/p2-wave/probes/ADV-0136/fixtures/prompts/declared-anthropic.txt",
    "command-center/p2-wave/probes/ADV-0136/fixtures/prompts/declared-openai-stripped.txt",
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
        "present": True,
        "unit_id": "ADV-0136",
        "receipt_path": "command-center/p2-wave/probes/ADV-0136/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:receipts emit c={ce}")
        print(te[-4000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0136",
        "unit_id": "ADV-0136",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0136",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/attestation-ledger.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "planted-collusion-same-tuple-label-blind",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "reviewer-from-raw-logs-driver-confound-declared-only",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0136/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0136-probe2-reviewer-from-logs",
            "verdict": "PASS",
            "independent": True,
            "rederived_from": "raw-transport-logs",
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0136: live named probes exit 0, independence "
            "attestation ledger is non-BLOCKED, per-unit manifest row. "
            "Did not run global unit_manifest.py --write. cloud_ok is false "
            "and is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0136",
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
    print("SUCCESS:ADV-0136 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
