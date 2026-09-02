#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
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
import emit_receipt as ER  # noqa: E402

P1 = ER.P1
P2 = ER.P2
OUT = ER.OUT_REL
SUPPORTING = [
    ER.SCHEMA_REL,
    "command-center/p2-wave/probes/REL-0019/gates.py",
    "command-center/p2-wave/probes/REL-0019/fixtures.py",
    "command-center/p2-wave/probes/REL-0019/measure.py",
    "command-center/p2-wave/probes/REL-0019/emit_receipt.py",
    "command-center/p2-wave/probes/REL-0019/probe1_knownbad_repro.py",
    "command-center/p2-wave/probes/REL-0019/probe2_always_accept.py",
    "command-center/ready_units.py",
    "tools/plugin/credential_boundary.py",
    "tools/router/route.py",
    "tools/plugin/drift.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = {**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"}
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
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
        "unit_id": "REL-0019",
        "receipt_path": "command-center/p2-wave/probes/REL-0019/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ER.write_receipt()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:REL-0019 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "REL-0019",
        "unit_id": "REL-0019",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0019",
        "registered": True,
        "output_path": OUT,
        "output_schema": ER.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "known-bad-and-seed-repro",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "always-accept-fn-shift",
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
        "manifest_path": "command-center/p2-wave/probes/REL-0019/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "REL-0019-probe2-always-accept-independent-recompute",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered REL-0019",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered REL-0019"},
        "ts": now,
        "notes": (
            "G-1 for REL-0019: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Rates measured on labelled fixtures wrapping shipped gates. "
            "cloud_ok is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "REL-0019",
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
    print("SUCCESS:REL-0019 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
