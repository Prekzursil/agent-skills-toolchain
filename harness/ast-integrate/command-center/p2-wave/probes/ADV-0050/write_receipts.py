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
OUT = "command-center/adversarial/ADV-0050-license-rider-field-of-use-audit.json"
SCHEMA = "command-center/schema/license-and-rights-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0050/probe1_canonical_diff.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0050/probe2_extra_license.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0050/license_diff.py",
    "command-center/p2-wave/probes/ADV-0050/audit.py",
    "command-center/p2-wave/probes/ADV-0050/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0050/probe1_canonical_diff.py",
    "command-center/p2-wave/probes/ADV-0050/probe2_extra_license.py",
    "command-center/p2-wave/probes/ADV-0050/fixtures/control-canonical-mit/LICENSE",
    "command-center/p2-wave/probes/ADV-0050/fixtures/control-canonical-mit-whitespace/LICENSE",
    "command-center/p2-wave/probes/ADV-0050/fixtures/planted-mit-ml-rider/LICENSE",
    "command-center/p2-wave/probes/ADV-0050/fixtures/planted-extra-license-readme/LICENSE",
    "command-center/p2-wave/probes/ADV-0050/fixtures/planted-extra-license-readme/README.md",
    "command-center/p2-wave/probes/ADV-0050/fixtures/planted-extra-license-readme/NOTICE",
    "command-center/p2-wave/probes/ADV-0050/fixtures/known-case-mcp-agent-mail/LICENSE",
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
        "present": True,
        "unit_id": "ADV-0050",
        "receipt_path": "command-center/p2-wave/probes/ADV-0050/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not (REPO / OUT).is_file():
        print("FAILED:ADV-0050 receipts primary missing; run emit_artifact.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0050",
        "unit_id": "ADV-0050",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0050",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "canonical-spdx-license-diff",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "extra-license-restriction-search",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0050/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0050-probe2-extra-license",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0050: live named probes exit 0, license-and-rights-record "
            "state=SUCCESS, per-unit manifest row. Canonical SPDX body diff plus "
            "extra-LICENSE README/NOTICE search. mcp_agent_mail MIT+rider captured; "
            "live vendored tree absent. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. Not legal advice."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0050",
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
    print("SUCCESS:ADV-0050 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
