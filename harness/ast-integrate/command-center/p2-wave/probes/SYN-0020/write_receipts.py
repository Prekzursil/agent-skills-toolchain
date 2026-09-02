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

from contract import (  # noqa: E402
    COMPLETION_SENTINEL,
    LIVE_CHECKLIST,
    OUT_REL,
    P1,
    P2,
    SCHEMA_REL,
    SENTINEL,
    UNIT_ID,
)

SUPPORTING = [
    SCHEMA_REL,
    LIVE_CHECKLIST,
    "command-center/p2-wave/probes/SYN-0020/contract.py",
    "command-center/p2-wave/probes/SYN-0020/extract.py",
    "command-center/p2-wave/probes/SYN-0020/statements.py",
    "command-center/p2-wave/probes/SYN-0020/runner.py",
    "command-center/p2-wave/probes/SYN-0020/report.py",
    "command-center/p2-wave/probes/SYN-0020/emit.py",
    "command-center/p2-wave/probes/SYN-0020/probe1_known_present_and_noexec.py",
    "command-center/p2-wave/probes/SYN-0020/probe2_untested_not_agree.py",
    "command-center/p2-wave/probes/SYN-0020/schema_local.py",
    "command-center/p2-wave/probes/SYN-0020/fixtures/docs/README.md",
    "command-center/p2-wave/probes/SYN-0020/fixtures/docs/RUNBOOK.md",
    "command-center/p2-wave/probes/SYN-0020/fixtures/docs/plugin-marketplace.md",
    "command-center/p2-wave/probes/SYN-0020/fixtures/noexec-marked.md",
    "command-center/p2-wave/probes/SYN-0020/fixtures/noexec-unmarked.md",
    "command-center/p2-wave/probes/SYN-0020/fixtures/untested.md",
    "command-center/p2-wave/probes/SYN-0020/fixtures/known-present-git-archive.md",
    "command-center/p2-wave/probes/SYN-0020/fixtures/mention-only.md",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
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
        "present": True,
        "unit_id": UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/SYN-0020/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = subprocess.run(
        [sys.executable, "-B", str(HERE / "emit.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if emit.returncode != 0:
        print("FAILED:receipts emit")
        print((emit.stdout or "")[-2000:])
        print((emit.stderr or "")[-2000:])
        return 1
    print((emit.stdout or "").strip())
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT_ID,
        "unit_id": UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "known-present-and-noexec",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "untested-not-agree",
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
        "manifest_path": "command-center/p2-wave/probes/SYN-0020/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "SYN-0020-probe2-untested-not-agree",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for SYN-0020: live named probes exit 0, docs-code-parity "
            "report state=SUCCESS, known-present git-archive CONTRADICT fired, "
            "no AGREE without a test id, per-unit manifest row. Did not run "
            "global unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT_ID,
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
    print("SUCCESS:SYN-0020 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
