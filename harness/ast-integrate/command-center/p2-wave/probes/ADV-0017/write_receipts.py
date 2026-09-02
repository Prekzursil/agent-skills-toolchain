#!/usr/bin/env python3
"""Write SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json for ADV-0017."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit_common as A  # noqa: E402
import build_artifact as B  # noqa: E402
import condition11_check as C11  # noqa: E402
import fixtures as F  # noqa: E402

from audit_common import OUT_REL, P1, P2, REPO, SCHEMA_REL, UID  # noqa: E402

SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/ADV-0017/audit_common.py",
    "command-center/p2-wave/probes/ADV-0017/lib_classify.py",
    "command-center/p2-wave/probes/ADV-0017/lib_provenance.py",
    "command-center/p2-wave/probes/ADV-0017/fixtures.py",
    "command-center/p2-wave/probes/ADV-0017/controls.py",
    "command-center/p2-wave/probes/ADV-0017/scope_guard.py",
    "command-center/p2-wave/probes/ADV-0017/recover_historical.py",
    "command-center/p2-wave/probes/ADV-0017/probe1_classify.py",
    "command-center/p2-wave/probes/ADV-0017/probe2_provenance.py",
    "command-center/p2-wave/probes/ADV-0017/build_artifact.py",
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
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/ADV-0017/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UID,
    }


def main() -> int:
    A.unshadow_stdlib()
    F.write_fixture_trees()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0017 receipts probes c1={c1} c2={c2}")
        print(t1[-4000:])
        print(t2[-4000:])
        return 1
    doc = B.build_doc(probe1_raw=t1, probe2_raw=t2)
    out_path = B.write_artifact(doc)
    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0017",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0017/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0017-probe2-provenance-rederive",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0017: live named probes exit 0, artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. cloud ok=true is not "
            "delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    c11 = C11.check_manifest(HERE / "UNIT-ARTIFACT-MANIFEST.json")
    if not c11["ok"]:
        print(f"FAILED:ADV-0017 condition11 {c11}")
        return 1
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"wrote {out_path}")
    print("SUCCESS:ADV-0017 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
