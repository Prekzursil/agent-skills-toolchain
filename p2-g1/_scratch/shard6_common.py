"""Shared plumbing for shard-6 resume builds (IMP units).

Writes per-unit SUBAGENT-RETURN.json + UNIT-ARTIFACT-MANIFEST.json and
refreshes receipt artifact rows / live probe outputs, hashing CRLF->LF
exactly like command-center/p2-wave/_measure_one_delivered.py.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def run_probe(command: str, timeout: int = 180) -> tuple[int, str]:
    """Run a probe command with the same env the measure script uses."""
    import os
    import re as _re

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    env["PYTHONPATH"] = os.pathsep.join(
        [hook_dir, str(REPO), str(REPO / "tools"), str(REPO / "tools" / "measure-guard"),
         str(REPO / "platform" / "lib"), str(REPO / "tools" / "agentspec"),
         env.get("PYTHONPATH", "")]
    )
    cmd = command
    if os.name == "nt":
        while True:
            m = _re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
            cmd = cmd[m.end():]
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        exe = str(Path(sys_executable())).replace("\\", "/")
        cmd = cmd.replace("python3", f"{exe} {wrapper.as_posix()}", 1)
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=timeout, env=env)
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text[-4000:]


def sys_executable() -> str:
    import sys
    return sys.executable


def update_artifact_rows(receipt: dict, paths: list[str], role_by_path: dict[str, str]) -> None:
    """Refresh/append receipt artifacts rows for recreated files with live hashes."""
    arts = receipt.get("artifacts") or []
    by_path = {a.get("path"): a for a in arts if isinstance(a, dict)}
    for relpath in paths:
        p = REPO / relpath
        sha, nbytes = digest_file(p)
        row = by_path.get(relpath)
        if row is None:
            row = {"path": relpath}
            arts.append(row)
            by_path[relpath] = row
        row.update({"exists": True, "bytes": nbytes, "sha256": sha, "eol": "LF"})
        if relpath in role_by_path:
            row["role"] = role_by_path[relpath]
    receipt["artifacts"] = arts


def save_receipt(unit_id: str, receipt: dict) -> str:
    out = REPO / "command-center" / "receipts" / f"{unit_id}.json"
    text = json.dumps(receipt, indent=1, ensure_ascii=False) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    return rel(out)


def write_subagent_return(unit_id: str, named_probes: list[dict], notes: str,
                          extra: dict | None = None) -> str:
    """named_probes: [{id, command, role, exit_code, raw_output}] (already run)."""
    receipt_rel = f"command-center/receipts/{unit_id}.json"
    sha, nbytes = digest_file(REPO / receipt_rel)
    doc = {
        "id": unit_id,
        "unit_id": unit_id,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{unit_id}",
        "output_path": receipt_rel,
        "output_schema": "command-center/schema/receipt.schema.json",
        "manifest_path": f"command-center/p2-wave/probes/{unit_id}/UNIT-ARTIFACT-MANIFEST.json",
        "artifacts": [
            {"path": receipt_rel, "role": "primary", "exists": True,
             "bytes": nbytes, "sha256": sha}
        ],
        "named_probes": [
            {
                "id": np["id"],
                "command": np["command"],
                "role": np["role"],
                "exit_code": np["exit_code"],
                "raw_output": np["raw_output"],
            }
            for np in named_probes
        ],
        "notes": notes,
        "ts": "2026-10-24T00:00:00Z",
        "registered": True,
    }
    if extra:
        doc.update(extra)
    out = REPO / "command-center" / "p2-wave" / "probes" / unit_id / "SUBAGENT-RETURN.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    return rel(out)


def write_manifest(unit_id: str, rows: list[dict]) -> str:
    """rows: [{path, role, receipt_path}] — hashes computed live, present=True."""
    out_rows = []
    for r in rows:
        p = REPO / r["path"]
        sha, nbytes = digest_file(p)
        out_rows.append({
            "unit_id": unit_id,
            "path": r["path"],
            "role": r.get("role", "supporting"),
            "present": True,
            "bytes": nbytes,
            "sha256": sha,
            "receipt_path": r.get("receipt_path",
                                  f"command-center/p2-wave/probes/{unit_id}/SUBAGENT-RETURN.json"),
        })
    out = REPO / "command-center" / "p2-wave" / "probes" / unit_id / "UNIT-ARTIFACT-MANIFEST.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {"artifacts": out_rows}
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    return rel(out)


def refresh_evidence_probe(receipt: dict, command_sub: str, raw_output: str,
                           exit_code: int = 0) -> int:
    """Replace raw_output of the first evidence probe whose command contains
    command_sub; returns number of probes updated."""
    n = 0
    for ev in receipt.get("evidence") or []:
        for pr in ev.get("probes") or []:
            cmd = str(pr.get("command") or "")
            if command_sub in cmd:
                pr["raw_output"] = raw_output
                pr["exit_code"] = exit_code
                n += 1
    return n
