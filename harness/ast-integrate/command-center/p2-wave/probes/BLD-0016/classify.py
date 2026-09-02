"""On-disk existence classifier for BLD-0016.

Verdicts:
  PRESENT        — regular file, st_size > 0; bytes + sha256 read here
  EMPTY          — regular file, st_size == 0 (never PRESENT)
  ABSENT         — path does not exist
  DIR-INCOMPLETE — directory without a named minimum member file, or
                   the named member is itself ABSENT/EMPTY-without-content

A digest is computed from filesystem bytes in this process. It is never
copied from a manifest row.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any

PRESENT = "PRESENT"
EMPTY = "EMPTY"
ABSENT = "ABSENT"
DIR_INCOMPLETE = "DIR-INCOMPLETE"


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def digest_file(path: Path) -> tuple[str, int]:
    return digest_bytes(path.read_bytes())


def classify_path(
    path: Path,
    *,
    required_member: str | None = None,
) -> dict[str, Any]:
    p = Path(path)
    rec: dict[str, Any] = {
        "path": str(p),
        "required_member": required_member,
        "exists": p.exists(),
        "is_file": False,
        "is_dir": False,
        "tool": "python-os.stat+hashlib",
        "st_size": None,
        "bytes": 0,
        "sha256": None,
        "verdict": ABSENT,
    }
    if not p.exists():
        rec["verdict"] = ABSENT
        return rec
    rec["is_file"] = p.is_file()
    rec["is_dir"] = p.is_dir()
    if p.is_dir():
        if not required_member:
            rec["verdict"] = DIR_INCOMPLETE
            rec["detail"] = (
                "directory deliverable without a named minimum member file "
                "is not PRESENT"
            )
            return rec
        member = p / required_member
        inner = classify_path(member)
        rec["member_probe"] = {
            "path": inner["path"],
            "verdict": inner["verdict"],
            "bytes": inner["bytes"],
            "sha256": inner["sha256"],
            "st_size": inner["st_size"],
        }
        if inner["verdict"] == PRESENT:
            rec["verdict"] = PRESENT
            rec["bytes"] = inner["bytes"]
            rec["sha256"] = inner["sha256"]
            rec["st_size"] = inner["st_size"]
        elif inner["verdict"] == EMPTY:
            rec["verdict"] = EMPTY
            rec["bytes"] = 0
            rec["sha256"] = inner.get("sha256")
            rec["st_size"] = 0
        else:
            rec["verdict"] = DIR_INCOMPLETE
        return rec
    st = os.stat(p)
    rec["st_size"] = int(st.st_size)
    raw = p.read_bytes()
    sha, nbytes = digest_bytes(raw)
    rec["bytes"] = nbytes
    rec["sha256"] = sha
    if st.st_size == 0:
        rec["verdict"] = EMPTY
    else:
        rec["verdict"] = PRESENT
    return rec


def unix_stat_reprobe(path: Path) -> dict[str, Any]:
    """Independent tool: GNU/BSD `stat` size + `sha256sum` of raw bytes.

    Catalog reviewer pairing is PowerShell Get-Item vs Python os.stat.
    This Linux estate has no pwsh/powershell; unix stat is the second tool.
    """
    p = Path(path)
    rec: dict[str, Any] = {
        "path": str(p),
        "tool": "unix-stat+sha256sum",
        "exists": p.exists(),
        "st_size": None,
        "sha256_raw": None,
        "verdict": ABSENT,
        "error": None,
    }
    if not p.exists() or not p.is_file():
        rec["verdict"] = ABSENT if not p.exists() else DIR_INCOMPLETE
        return rec
    try:
        size_p = subprocess.run(
            ["stat", "-c", "%s", str(p)],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if size_p.returncode != 0:
            rec["error"] = (size_p.stderr or size_p.stdout or "stat failed")[-400]
            return rec
        rec["st_size"] = int(size_p.stdout.strip())
        hash_p = subprocess.run(
            ["sha256sum", str(p)],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if hash_p.returncode != 0:
            rec["error"] = (hash_p.stderr or hash_p.stdout or "sha256sum failed")[-400]
            return rec
        rec["sha256_raw"] = hash_p.stdout.split()[0].strip()
        rec["verdict"] = EMPTY if rec["st_size"] == 0 else PRESENT
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        rec["error"] = type(exc).__name__
    return rec
