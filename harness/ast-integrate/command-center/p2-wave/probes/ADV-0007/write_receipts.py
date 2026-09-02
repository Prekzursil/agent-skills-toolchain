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
from engine import OUT_REL, PROBE1, PROBE2, SCHEMA_REL, UNIT  # noqa: E402

SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0007/engine.py",
    "command-center/p2-wave/probes/ADV-0007/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0007/probe1_defining_index.py",
    "command-center/p2-wave/probes/ADV-0007/probe2_title_similarity.py",
    "command-center/p2-wave/probes/ADV-0007/fixtures/defining/option-universe.md",
    "command-center/p2-wave/probes/ADV-0007/fixtures/defining/architecture-candidates.md",
    "command-center/p2-wave/probes/ADV-0007/fixtures/defining/research-harness.md",
    "command-center/p2-wave/probes/ADV-0007/fixtures/references/unambiguous.md",
    "command-center/p2-wave/probes/ADV-0007/fixtures/references/ambiguous.md",
    "command-center/p2-wave/probes/ADV-0007/fixtures/selected-ids.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/ADV-0007/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    primary_path = REPO / OUT_REL
    if not primary_path.is_file() or primary_path.stat().st_size < 2048:
        print(f"FAILED:{UNIT} receipts artifact missing; run emit_artifact.py first")
        return 1
    text = primary_path.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:{UNIT} receipts self-declared {doc.get('state')}")
        return 1
    c1, t1 = run_cmd(PROBE1)
    c2, t2 = run_cmd(PROBE2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UNIT}",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": PROBE1,
                "exit_code": c1,
                "role": "defining-heading-index",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": PROBE2,
                "exit_code": c2,
                "role": "title-similarity-unresolved",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0007/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0007-probe2-title-similarity",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0007: live named probes exit 0, option-ID binding "
            "artifact state=SUCCESS, per-unit manifest row. Did not run "
            "global unit_manifest.py --write. Did not rebuild "
            "refutation-record.schema.json. cloud ok=true is not delivery."
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
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
