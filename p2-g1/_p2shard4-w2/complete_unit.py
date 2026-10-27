#!/usr/bin/env python3
"""shard4-w2 completion writer: run named probes, write SUBAGENT-RETURN.json
and UNIT-ARTIFACT-MANIFEST.json for one unit (AUD-0069 writer shape)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str, timeout: int = 1800) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    if os.name == "nt":
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip('"').strip("'")
            cmd = cmd[m.end():]
        exe = sys.executable.replace("\\", "/")
        cmd = cmd.replace("python3", f"{exe}", 1)
    proc = subprocess.run(
        cmd, cwd=str(REPO), shell=True, capture_output=True, text=True,
        env=env, timeout=timeout,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def row(rel: str, role: str, unit: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel, "sha256": sha, "bytes": size, "present": path.is_file(),
        "unit_id": unit,
        "receipt_path": f"command-center/p2-wave/probes/{unit}/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    unit, out_rel = sys.argv[1], sys.argv[2]
    p1_cmd, p2_cmd = sys.argv[3], sys.argv[4]
    supporting = sys.argv[5].split(",") if len(sys.argv) > 5 and sys.argv[5] else []
    here = REPO / "command-center" / "p2-wave" / "probes" / unit
    out = REPO / out_rel
    if not out.is_file() or out.stat().st_size <= 0:
        print(f"FAILED:complete {unit} artifact missing")
        return 1
    c1, t1 = run_cmd(p1_cmd)
    c2, t2 = run_cmd(p2_cmd)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:complete {unit} probes c1={c1} c2={c2}")
        print(t1[-1500:]); print(t2[-1500:])
        return 1
    primary = row(out_rel, "primary", unit)
    artifacts = [primary] + [row(p, "supporting", unit) for p in supporting]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": unit, "unit_id": unit, "status": "DELIVERED", "state": "SUCCESS",
        "sentinel": f"SUCCESS:{unit}", "registered": True,
        "output_path": out_rel,
        "output_schema": json.loads(out.read_text(encoding="utf-8")).get("output_schema", ""),
        "named_probes": [
            {"id": "probe1", "command": p1_cmd, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": p2_cmd, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [{
            "path": out_rel, "sha256": primary["sha256"],
            "bytes": primary["bytes"], "exists": True, "role": "primary",
        }],
        "manifest_path": f"command-center/p2-wave/probes/{unit}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": f"{unit}-pending-independent-reviewer",
            "verdict": "NOT-REVIEWED", "independent": False,
            "notes": "builder shard4-w2: artifact delivered, probes live-green; receipt stays BLOCKED pending independent closure",
        },
        "ts": now,
        "notes": (
            f"shard4-w2 resume 2026-10-25: prior builder died after emitting the "
            f"artifact; this run re-ran both named probes live (exit 0) and "
            f"completed return+manifest. No rebuild of artifact content. "
            f"Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": unit,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    (here / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (here / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"primary {out_rel} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{unit} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
