#!/usr/bin/env python3
"""Claim catalog and environment-sensitive evaluation for CNF-0151.

Portable subset is reconstructed here because CNF-0150 has no receipt on this
tree. Portable means the verdict does not depend on PATHEXT, MSYS path
conversion, PowerShell caret-escaping, or CRLF-as-bytes. The windows-specific
control is .cmd shim resolution via Get-Command/PATHEXT.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

SHIM_NAME = "cnf0151shim"
HOST_CACHE = Path("/var/tmp/cnf0151-host-cache")
MARKER_NAME = "MARKER"
MARKER_BODY = "HOST-CACHE-MARKER-CNF-0151\n"
WIN_PATHEXT = ".COM;.EXE;.BAT;.CMD"

CANON_JSON_OBJ = {"k": "cnf0151", "n": 151, "portable": True}

CLAIMS = (
    {
        "id": "C-WIN-CMD-SHIM",
        "class": "windows-specific",
        "title": "Resolve cnf0151shim via PATHEXT/.cmd (Get-Command semantics)",
        "portable": False,
    },
    {
        "id": "C-PORTABLE-JSON",
        "class": "portable",
        "title": "json.dumps of a canonical object with sorted keys",
        "portable": True,
    },
    {
        "id": "C-PORTABLE-SHA256",
        "class": "portable",
        "title": "sha256 of planted portable.json fixture bytes",
        "portable": True,
    },
    {
        "id": "C-PORTABLE-LF",
        "class": "portable",
        "title": "LF-normalised sha256 of planted portable.txt (CRLF stripped)",
        "portable": True,
    },
)


def path_dirs(path_value: str | None = None) -> list[str]:
    raw = path_value if path_value is not None else os.environ.get("PATH", "")
    return [p for p in raw.split(os.pathsep) if p]


def windows_resolve(name: str, dirs: list[str], pathext: str) -> str | None:
    """Get-Command-like lookup: PATHEXT suffixes, case-insensitive, no X_OK.

    Linux trees are case-sensitive; a planted ``.cmd`` must still match PATHEXT
    ``.CMD``. Scan the directory and compare folded names rather than probing
    a single case.
    """
    exts = []
    for item in pathext.split(";"):
        item = item.strip()
        if not item:
            continue
        if not item.startswith("."):
            item = "." + item
        exts.append(item)
    wanted = {name.lower()}
    wanted.update((name + ext).lower() for ext in exts)
    for directory in dirs:
        base = Path(directory)
        if not base.is_dir():
            continue
        try:
            entries = list(base.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_file() and entry.name.lower() in wanted:
                return str(entry)
    return None


def posix_which(name: str, dirs: list[str]) -> str | None:
    """POSIX which: exact basename, no implicit .cmd, X_OK required."""
    for directory in dirs:
        cand = Path(directory) / name
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None


def canonical_json() -> str:
    return json.dumps(CANON_JSON_OBJ, separators=(",", ":"), sort_keys=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lf_sha256(data: bytes) -> str:
    return sha256_bytes(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))


def fixture_bytes(name: str, work: Path | None = None) -> bytes:
    root = (work or Path(os.environ.get("CNF0151_WORK", str(HERE)))) / "fixtures"
    path = root / name
    if not path.is_file():
        path = FIX / name
    return path.read_bytes()


def host_cache_visible(cache_root: Path | None = None) -> bool:
    root = cache_root or Path(os.environ.get("CNF0151_HOST_CACHE", str(HOST_CACHE)))
    marker = root / MARKER_NAME
    return marker.is_file() and MARKER_BODY.strip() in marker.read_text(encoding="utf-8", errors="replace")


def eval_shim(dirs: list[str], pathext: str | None) -> dict[str, Any]:
    if pathext:
        found = windows_resolve(SHIM_NAME, dirs, pathext)
        rule = "windows-pathext"
    else:
        found = posix_which(SHIM_NAME, dirs)
        rule = "posix-which"
    return {
        "claim_id": "C-WIN-CMD-SHIM",
        "ok": found is not None,
        "value": found or "",
        "rule": rule,
        "pathext": pathext or "",
        "path_dirs": dirs,
    }


def eval_portable_json() -> dict[str, Any]:
    value = canonical_json()
    return {
        "claim_id": "C-PORTABLE-JSON",
        "ok": True,
        "value": value,
        "rule": "json.dumps-sorted",
    }


def eval_portable_sha256(work: Path | None = None) -> dict[str, Any]:
    raw = fixture_bytes("portable.json", work)
    value = sha256_bytes(raw)
    return {
        "claim_id": "C-PORTABLE-SHA256",
        "ok": True,
        "value": value,
        "rule": "sha256-file-bytes",
        "bytes": len(raw),
    }


def eval_portable_lf(work: Path | None = None) -> dict[str, Any]:
    raw = fixture_bytes("portable.txt", work)
    value = lf_sha256(raw)
    return {
        "claim_id": "C-PORTABLE-LF",
        "ok": True,
        "value": value,
        "rule": "sha256-lf-normalised",
        "raw_bytes": len(raw),
        "crlf_present": b"\r\n" in raw or b"\r" in raw,
    }


def evaluate_bundle(work: Path | None = None) -> dict[str, Any]:
    """Evaluate every claim under the current process environment."""
    work = work or Path(os.environ.get("CNF0151_WORK", "/work"))
    dirs = path_dirs(os.environ.get("CNF0151_PATH", os.environ.get("PATH", "")))
    pathext = os.environ.get("CNF0151_PATHEXT") or os.environ.get("PATHEXT") or ""
    cache = Path(os.environ.get("CNF0151_HOST_CACHE", str(HOST_CACHE)))
    results = [
        eval_shim(dirs, pathext if pathext else None),
        eval_portable_json(),
        eval_portable_sha256(work if (work / "fixtures").is_dir() else HERE),
        eval_portable_lf(work if (work / "fixtures").is_dir() else HERE),
    ]
    return {
        "results": results,
        "host_cache_visible": host_cache_visible(cache),
        "host_cache_path": str(cache / MARKER_NAME),
        "python": os.environ.get("CNF0151_PYTHON", ""),
        "path": os.environ.get("CNF0151_PATH", os.environ.get("PATH", "")),
        "pathext": pathext,
    }


def plant_host_cache() -> Path:
    """Plant a .cmd shim and marker in a host cache that the container must not see."""
    bin_dir = HOST_CACHE / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (HOST_CACHE / MARKER_NAME).write_text(MARKER_BODY, encoding="utf-8")
    shim_src = FIX / "cnf0151shim.cmd"
    (bin_dir / "cnf0151shim.cmd").write_bytes(shim_src.read_bytes())
    return HOST_CACHE


def expected_portable() -> dict[str, str]:
    work = HERE
    return {
        "C-PORTABLE-JSON": canonical_json(),
        "C-PORTABLE-SHA256": eval_portable_sha256(work)["value"],
        "C-PORTABLE-LF": eval_portable_lf(work)["value"],
    }
