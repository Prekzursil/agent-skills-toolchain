#!/usr/bin/env python3
"""Builder shard22-w4 resume: write SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST.

Re-runs the unit's named probes live, captures outputs, hashes the primary
artifact with the _measure_one_delivered convention (CRLF normalized to LF
before hashing), and writes both probe-dir files. The catalog receipt at
output_path is NEVER modified by this writer.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
BUILDER = "shard22-w4-resume (builder) 2026-10-26"


def digest(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    if os.name == "nt" and cmd.startswith("python3 "):
        cmd = cmd.replace("python3", sys.executable.replace("\\", "/"), 1)
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=2700, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def build_unit(uid: str, output_path: str, probes: list, supporting: list) -> int:
    probe_dir = REPO / "command-center" / "p2-wave" / "probes" / uid
    art = REPO / output_path
    assert art.is_file() and art.stat().st_size > 0, "primary artifact missing"
    sha, nbytes = digest(art)

    named_probes = []
    all_ok = True
    for pid, command, role in probes:
        rc, out = run_cmd(command)
        all_ok = all_ok and rc == 0
        named_probes.append({
            "id": pid, "command": command, "exit_code": rc, "role": role,
            "raw_output": out[-6000:],
        })
        print(f"  probe {pid} rc={rc}")

    artifacts_rows = [{
        "path": output_path, "unit_id": uid, "role": "primary",
        "present": True, "bytes": nbytes, "sha256": sha,
        "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
        "hash_convention": "sha256 over CRLF-normalized bytes (_measure_one_delivered)",
    }]
    for rel, role in supporting:
        f = REPO / rel
        s, n = digest(f)
        artifacts_rows.append({
            "path": rel, "unit_id": uid, "role": role, "present": True,
            "bytes": n, "sha256": s,
            "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
        })

    ret = {
        "id": uid,
        "status": "DELIVERED" if all_ok else "FAILED",
        "cloud_ok": False,
        "artifacts": [{
            "path": output_path, "exists": True, "bytes": nbytes,
            "sha256": sha, "role": "primary",
        }],
        "named_probes": named_probes,
        "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
        "builder": {
            "note": ("probe kit re-materialized on the Windows worktree by builder "
                     + BUILDER + "; the catalog receipt at " + output_path
                     + " is untouched (original closed receipt, built on a Linux "
                       "substrate per its own produced_by/scope fields); fixtures "
                       "rebuilt with fresh bytes, live hashes recorded in the manifest"),
            "receipt_modified": False,
        },
    }
    (probe_dir / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1), encoding="utf-8", newline="\n")
    man = {"artifacts": artifacts_rows}
    (probe_dir / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1), encoding="utf-8", newline="\n")

    m = subprocess.run([sys.executable.replace("\\", "/"), "command-center/p2-wave/_measure_one_delivered.py", uid],
                       cwd=str(REPO), capture_output=True, text=True, timeout=2700,
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    tail = "\n".join((m.stdout or "").strip().splitlines()[-2:])
    print("  measure rc=%d %s" % (m.returncode, tail))
    ret["measure"] = {"exit_code": m.returncode, "line": tail.splitlines()[-1] if tail else ""}
    (probe_dir / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1), encoding="utf-8", newline="\n")
    return 0 if (all_ok and m.returncode == 0) else 1


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    rc = build_unit(spec["id"], spec["output_path"], spec["probes"], spec["supporting"])
    print(("SUCCESS:unit " if rc == 0 else "FAILED:unit ") + spec["id"])
    raise SystemExit(rc)
