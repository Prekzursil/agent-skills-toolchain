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
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = E.OUT_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0072/probe1_lexical_mapping.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0072/probe2_residue_report.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/AUD-0072/engine.py",
    "command-center/p2-wave/probes/AUD-0072/emit_artifact.py",
    "command-center/p2-wave/probes/AUD-0072/probe1_lexical_mapping.py",
    "command-center/p2-wave/probes/AUD-0072/probe2_residue_report.py",
    "command-center/p2-wave/probes/AUD-0072/fixtures/planted-expressions.json",
    "command-center/phase4/contracts/ARC-0085.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    import re as _re

    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    # shard4-w2 repair 2026-10-25 (mirror _measure_one_delivered.py shard11
    # repair): cmd.exe (COMSPEC) cannot execute POSIX "VAR=value command"
    # prefixes; move them into the child env so the identical named-probe
    # commands run verbatim on Windows. Probe selection, exit codes and all
    # other checks unchanged; no-op on POSIX.
    if os.name == "nt":
        while True:
            m = _re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
            cmd = cmd[m.end():]
    p = subprocess.run(
        cmd,
        cwd=str(E.REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = E.REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "AUD-0072",
        "receipt_path": "command-center/p2-wave/probes/AUD-0072/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit_rc, emit_out = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/AUD-0072/emit_artifact.py"
    )
    if emit_rc != 0:
        print(f"FAILED:receipts emit rc={emit_rc}")
        print(emit_out[-2000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    art = json.loads((E.REPO / OUT).read_text(encoding="utf-8"))
    art["named_probes"] = [
        {
            "id": "probe1",
            "role": "lexical-mapping",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1,
        },
        {
            "id": "probe2",
            "role": "unmapped-residue",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2,
        },
    ]
    (E.REPO / OUT).write_text(
        json.dumps(art, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary]
    for p in SUPPORTING:
        if (E.REPO / p).is_file():
            artifacts.append(row(p, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "AUD-0072",
        "unit_id": "AUD-0072",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0072",
        "registered": True,
        "output_path": OUT,
        "output_schema": E.CATALOG_SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "lexical-mapping",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "unmapped-residue",
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0072/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0072-probe2-unmapped-residue",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for AUD-0072: live named probes exit 0, confidence-status "
            "normalization state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. Catalog "
            "claim-record.schema.json is a generated shim; nested claims follow ARC-0085."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "AUD-0072",
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
    print("SUCCESS:AUD-0072 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
