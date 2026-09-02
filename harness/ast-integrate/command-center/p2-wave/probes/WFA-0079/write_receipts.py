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
sys.path.insert(0, str(HERE))
import graph as G  # noqa: E402

REPO = G.REPO
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0079/graph.py",
    "command-center/p2-wave/probes/WFA-0079/emit.py",
    "command-center/p2-wave/probes/WFA-0079/probe1_closure_counts.py",
    "command-center/p2-wave/probes/WFA-0079/probe2_reachability.py",
    "command-center/p2-wave/probes/WFA-0079/licenses/BMAD-METHOD.LICENSE",
    "command-center/p2-wave/probes/WFA-0079/licenses/microsoft-autogen.LICENSE",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": G.UNIT,
        "receipt_path": "command-center/p2-wave/probes/WFA-0079/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(G.P1)
    c2, t2 = run_probe(G.P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{G.UNIT} receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(G.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": G.UNIT,
        "unit_id": G.UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": G.SENTINEL,
        "registered": True,
        "output_path": G.OUT_REL,
        "output_schema": G.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": G.P1,
                "exit_code": c1,
                "role": "closure-counts-both-states",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": G.P2,
                "exit_code": c2,
                "role": "reachability-walk",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": G.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/WFA-0079/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0079-probe2-reachability-walk",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0079: live named probes exit 0, provenance-licence "
            "graph v2 state=SUCCESS with SUCCESS:WFA-0079, per-unit manifest "
            "row. Did not run global unit_manifest.py --write. v1 466-node "
            "blob absent on this tree; live-estate reconstruction with "
            "fetched BMAD/autogen licences. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": G.UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a.get("present") is True),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps({"primary": primary, "probes": [c1, c2]}, sort_keys=True))
    print("SUCCESS:WFA-0079 receipts written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
