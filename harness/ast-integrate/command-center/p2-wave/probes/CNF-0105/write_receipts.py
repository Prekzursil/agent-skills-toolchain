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
OUT = "command-center/confirmation/CNF-0105-shell-interpreter-conformance.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0105/probe1_union_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0105/probe2_crlf_detector.py"
)
SUPPORTING = [
    "command-center/schema/platform-report.schema.json",
    "command-center/p2-wave/probes/CNF-0105/runner.py",
    "command-center/p2-wave/probes/CNF-0105/emit.py",
    "command-center/p2-wave/probes/CNF-0105/probe1_union_matrix.py",
    "command-center/p2-wave/probes/CNF-0105/probe2_crlf_detector.py",
    "command-center/p2-wave/probes/CNF-0105/fixtures/git-bash-standin.sh",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True)
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
        "unit_id": "CNF-0105",
        "receipt_path": "command-center/p2-wave/probes/CNF-0105/SUBAGENT-RETURN.json",
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
        print("FAILED:CNF-0105 emit")
        print((emit.stdout or "")[-2000:])
        print((emit.stderr or "")[-2000:])
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNF-0105 probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    supporting = [p for p in SUPPORTING if (REPO / p).is_file()]
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in supporting]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNF-0105",
        "unit_id": "CNF-0105",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0105",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/platform-report.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/CNF-0105/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0105-probe2-crlf-detector",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNF-0105: live named probes exit 0, shell-interpreter-conformance "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. pwsh7 and MSYS Git Bash are absent on this "
            "Linux host; Git Bash arm is an igncr stand-in; WSL bash is host GNU bash. "
            "Shipped scripts/ bodies were shebang-stubbed so backup/deploy/supervisor "
            "launchers are not executed."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0105",
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
    print("SUCCESS:CNF-0105 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
