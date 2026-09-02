#!/usr/bin/env python3
"""Update per-unit UNIT-ARTIFACT-MANIFEST.json (and SUBAGENT-RETURN) to live sha."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: _refresh_primary_sha.py <UNIT-ID> <output_path>")
        return 2
    uid = sys.argv[1]
    rel = sys.argv[2].replace("\\", "/")
    root = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path.cwd()).resolve()
    out = root / rel
    if not out.is_file() or out.stat().st_size <= 0:
        print(f"FAILED:refresh-sha missing {rel}")
        return 1
    sha, n = digest(out)
    probe_dir = root / "command-center" / "p2-wave" / "probes" / uid
    man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.is_file() else {}
    rows = list(man.get("artifacts") or [])
    found = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("unit_id") == uid and str(row.get("path") or "").replace("\\", "/") == rel:
            row["sha256"] = sha
            row["bytes"] = n
            row["present"] = True
            found = True
    if not found:
        rows.append(
            {
                "unit_id": uid,
                "path": rel,
                "sha256": sha,
                "bytes": n,
                "present": True,
                "role": "primary",
                "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
            }
        )
    man["artifacts"] = rows
    man.setdefault("unit_id", uid)
    man.setdefault("schema_version", 1)
    man_path.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8", newline="\n")
    ret_path = probe_dir / "SUBAGENT-RETURN.json"
    if ret_path.is_file():
        ret = json.loads(ret_path.read_text(encoding="utf-8"))
        arts = ret.get("artifacts") if isinstance(ret.get("artifacts"), list) else []
        if arts and isinstance(arts[0], dict):
            arts[0]["sha256"] = sha
            arts[0]["bytes"] = n
            arts[0]["path"] = rel
            arts[0]["exists"] = True
        ret_path.write_text(json.dumps(ret, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"SUCCESS:refresh-sha {uid} bytes={n} sha256={sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
