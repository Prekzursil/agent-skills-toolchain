#!/usr/bin/env python3
"""Shard-10 wave-2 helper: emit SUBAGENT-RETURN.json + UNIT-ARTIFACT-MANIFEST.json
for a unit from live on-disk state. sha256 = CRLF-normalized (matches
_measure_one_delivered.py digest_file)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "p2-g1"
PROBES = REPO / "command-center" / "p2-wave" / "probes"


def norm_sha(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    import os
    import re as _re
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    # Windows cmd.exe cannot run POSIX "VAR=value command" prefixes; move
    # them into the child env exactly like _measure_one_delivered.py does.
    if os.name == "nt":
        while True:
            m = _re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
            cmd = cmd[m.end():]
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        exe = str(sys.executable).replace("\\", "/")
        cmd = cmd.replace("python3", f"{exe} {wrapper.as_posix()}", 1)
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          timeout=2700, cwd=str(REPO), env=env)
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def emit(unit_id: str, probes: list[dict], artifact_rows: list[dict],
         notes: str) -> None:
    out = json.loads((REPO / f"command-center/receipts/{unit_id}.json").read_text(encoding="utf-8"))
    out_path = out["output_path"] if "output_path" in out else None
    if not out_path:
        # receipt layout differs; read output_path from the catalog
        cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
        unit = next(u for u in cat["work_units"] if u.get("id") == unit_id)
        out_path = unit["output_path"]

    named = []
    for p in probes:
        rc, tail = run_probe(p["command"])
        named.append({
            "id": p["id"],
            "command": p["command"],
            "role": p["role"],
            "exit_code": rc,
            "raw_output": tail[-4000:],
        })
        if rc != 0:
            print(f"FAILED:emit {unit_id} probe {p['id']} rc={rc}")
            print(tail[-2000:])
            raise SystemExit(1)

    return_doc = {
        "id": unit_id,
        "unit_id": unit_id,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": out.get("completion_sentinel") or f"SUCCESS:{unit_id}",
        "output_path": out_path,
        "manifest_path": f"command-center/p2-wave/probes/{unit_id}/UNIT-ARTIFACT-MANIFEST.json",
        "artifacts": [],
        "named_probes": named,
        "notes": notes,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "registered": True,
    }

    man_rows = []
    all_paths = [out_path] + [r["path"] for r in artifact_rows]
    seen = set()
    for row_path, role in ([(out_path, "primary")] + [(r["path"], r["role"]) for r in artifact_rows]):
        if row_path in seen:
            continue
        seen.add(row_path)
        p = REPO / row_path
        if not p.is_file():
            print(f"FAILED:emit {unit_id} missing artifact {row_path}")
            raise SystemExit(1)
        sha, nbytes = norm_sha(p)
        man_rows.append({
            "unit_id": unit_id,
            "path": row_path,
            "role": role,
            "present": True,
            "bytes": nbytes,
            "sha256": sha,
            "receipt_path": f"command-center/p2-wave/probes/{unit_id}/SUBAGENT-RETURN.json",
        })
        return_doc["artifacts"].append({
            "path": row_path,
            "role": role,
            "exists": True,
            "bytes": nbytes,
            "sha256": sha,
        })

    ret_path = PROBES / unit_id / "SUBAGENT-RETURN.json"
    ret_path.write_text(json.dumps(return_doc, indent=1) + "\n", encoding="utf-8")
    man_path = PROBES / unit_id / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(json.dumps({"artifacts": man_rows}, indent=2) + "\n", encoding="utf-8")
    print(f"SUCCESS:emit {unit_id} return={ret_path} manifest={man_path} rows={len(man_rows)}")


if __name__ == "__main__":
    cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    emit(cfg["unit_id"], cfg["probes"], cfg["artifact_rows"], cfg["notes"])
