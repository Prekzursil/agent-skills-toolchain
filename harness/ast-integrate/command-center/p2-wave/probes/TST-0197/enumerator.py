"""Windows-safe tree enumerator for reserved device names.

The Phase-0 crash is `os.path.relpath` on Windows after GetFullPathName
collapses a file named NUL to `\\\\.\\NUL`, raising:

    ValueError: path is on mount '\\\\.\\NUL'

This walker never calls os.path.relpath / Path.relative_to. Relative
paths are accumulated from directory-entry names. On Windows it stats
via the `\\\\?\\` extended-length prefix; on POSIX it still records
that form and the device-namespace collapse, then opens the native path.

An incomplete walk is an error (`complete=False`, `count=None`), not a
small number. Swallowing the ValueError is how a baseline enumerator
reported every count as zero.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

RESERVED_BASENAMES = ("NUL", "CON", "AUX", "PRN", "COM1", "LPT1")
RESERVED_RE = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)",
    re.IGNORECASE,
)
KNOWN_PRESENT_NAME = "known-present.txt"
KNOWN_PRESENT_PAYLOAD = "TST-0197-KNOWN-PRESENT\n"


def is_reserved_device_name(name: str) -> bool:
    base = name.split("\\")[-1].split("/")[-1]
    stem = base.split(".")[0] if "." in base else base
    if base.upper() in {n.upper() for n in RESERVED_BASENAMES}:
        return True
    return bool(RESERVED_RE.match(base) or RESERVED_RE.match(stem))


def device_namespace_path(basename: str) -> str:
    """What Windows GetFullPathName yields for a reserved device basename."""
    stem = basename.split(".")[0]
    return r"\\." + "\\" + stem.upper()


def extended_length_path(win_abs: str) -> str:
    """`\\\\?\\` prefix for a Windows absolute path (UNC-aware)."""
    if win_abs.startswith("\\\\?\\"):
        return win_abs
    if win_abs.startswith("\\\\"):
        rest = win_abs[2:]
        return "\\\\?\\UNC\\" + rest
    return "\\\\?\\" + win_abs


def simulated_win_abs(root: Path, rel: str) -> str:
    """Map a POSIX probe path onto a Windows absolute path for prefix records."""
    rel_win = rel.replace("/", "\\")
    return r"C:\TST-0197\\" + rel_win


def _open_path(native: Path) -> str:
    if os.name == "nt":
        return extended_length_path(str(native.resolve()))
    return str(native)


def enumerate_tree(root: Path) -> dict[str, Any]:
    """Walk `root` without os.path.relpath. Fail closed on errors."""
    files: list[dict[str, Any]] = []
    reserved: list[str] = []
    errors: list[dict[str, str]] = []
    exception: str | None = None

    def rec(dir_native: Path, parts: tuple[str, ...]) -> None:
        scan_target = _open_path(dir_native)
        try:
            entries = list(os.scandir(scan_target))
        except OSError as exc:
            errors.append(
                {
                    "rel": "/".join(parts) if parts else ".",
                    "op": "scandir",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            return
        for entry in entries:
            name = entry.name
            child_parts = parts + (name,)
            rel = "/".join(child_parts)
            reserved_hit = is_reserved_device_name(name)
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
                is_file = entry.is_file(follow_symlinks=False)
            except OSError as exc:
                errors.append(
                    {
                        "rel": rel,
                        "op": "stat",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            rec_item = {
                "rel": rel,
                "name": name,
                "reserved": reserved_hit,
                "device_namespace_form": (
                    device_namespace_path(name) if reserved_hit else None
                ),
                "extended_length_form": extended_length_path(
                    simulated_win_abs(root, rel)
                ),
                "kind": "dir" if is_dir else ("file" if is_file else "other"),
            }
            if reserved_hit:
                reserved.append(rel)
            if is_dir:
                rec(Path(entry.path), child_parts)
            elif is_file:
                files.append(rec_item)

    try:
        rec(Path(root), ())
    except Exception as exc:  # noqa: BLE001 — fail-closed, do not zero
        exception = f"{type(exc).__name__}: {exc}"

    complete = exception is None and not errors
    count: int | None = len(files) if complete else None
    rels = [f["rel"] for f in files]
    return {
        "api": "os.scandir+name-stack",
        "root": str(root),
        "os_name": os.name,
        "complete": complete,
        "count": count,
        "file_count_if_incomplete": len(files),
        "files": files,
        "rels": rels,
        "reserved": sorted(reserved),
        "reserved_basenames_found": sorted(
            {Path(r).name.upper() for r in reserved}
        ),
        "errors": errors,
        "exception": exception,
        "used_os_path_relpath": False,
        "used_pathlib_relative_to": False,
        "known_present_found": KNOWN_PRESENT_NAME in {Path(r).name for r in rels},
    }


def ntpath_relpath_regression(start: str = r"C:\worktree") -> dict[str, Any]:
    """Reproduce the Phase-0 seed using Windows ntpath on this host."""
    import ntpath

    cases = []
    for name in RESERVED_BASENAMES:
        device = device_namespace_path(name)
        raised = None
        result = None
        try:
            result = ntpath.relpath(device, start)
        except ValueError as exc:
            raised = f"{type(exc).__name__}: {exc}"
        except Exception as exc:  # noqa: BLE001
            raised = f"{type(exc).__name__}: {exc}"
        cases.append(
            {
                "name": name,
                "path": device,
                "start": start,
                "raised": raised,
                "result": result,
                "is_valueerror": bool(raised and raised.startswith("ValueError")),
            }
        )
    nul = next(c for c in cases if c["name"] == "NUL")
    return {
        "module": "ntpath",
        "note": (
            "On POSIX, os.path.relpath is posixpath and does not raise on a "
            "file named NUL. The Phase-0 crash is ntpath after the name "
            "collapses to the device namespace \\\\.\\NUL."
        ),
        "nul_raises_valueerror": nul["is_valueerror"],
        "nul_message": nul["raised"],
        "all_reserved_raise_valueerror": all(c["is_valueerror"] for c in cases),
        "cases": cases,
    }


def posix_relpath_on_named_nul(nul_native: Path, root: Path) -> dict[str, Any]:
    """Both-states: posixpath.relpath does not raise on Linux for a real NUL file."""
    raised = None
    result = None
    try:
        result = os.path.relpath(str(nul_native), str(root))
    except Exception as exc:  # noqa: BLE001
        raised = f"{type(exc).__name__}: {exc}"
    return {
        "module": "os.path (posixpath on this host)",
        "raised": raised,
        "result": result,
        "raises": raised is not None,
    }
