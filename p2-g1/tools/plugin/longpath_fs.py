"""Long-path and reserved-device-name safe filesystem layer (IMP-0021).

Two hazards this layer closes:

* Win32 ``MAX_PATH`` (260) truncation: any path whose Win32 spelling reaches the
  limit is addressed through the ``\\\\?\\`` extended prefix so create / write /
  read / delete round-trip byte-for-byte. ``round_trip_long_path`` proves it with
  an out-of-band existence check that never imports this module.
* Reserved device names (``NUL``, ``CON``, ``COM1`` ...): a Windows-naive
  enumerator built on ``os.path.relpath`` raises ``path is on mount ...`` for a
  file literally named ``NUL`` (and on POSIX hosts silently succeeds, which is
  the wrong-reason green). ``enumerate_both`` runs the safe enumerator and the
  naive one side by side and surfaces the naive error instead of swallowing it.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

EXTENDED_PREFIX = "\\\\?\\"
WIN32_MAX_PATH = 260
RESERVED_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CLOCK$"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


# --------------------------------------------------------------------------- paths
def win32_spelling(path: str | os.PathLike[str]) -> str:
    """Return the path as Win32 would spell it (drive + backslashes)."""
    text = str(path)
    if os.name == "nt":
        return str(PureWindowsPath(os.path.abspath(text)))
    posix = PurePosixPath(os.path.abspath(text))
    return "C:" + "\\".join(("",) + posix.parts[1:])


def needs_extended_prefix(path: str | os.PathLike[str]) -> bool:
    return len(win32_spelling(path)) >= WIN32_MAX_PATH


def extended_path(path: str | os.PathLike[str]) -> str:
    """Extended-length form: ``\\\\?\\C:\\...`` (UNC becomes ``\\\\?\\UNC\\``)."""
    spelled = win32_spelling(path)
    if spelled.startswith(EXTENDED_PREFIX):
        return spelled
    if spelled.startswith("\\\\"):
        return EXTENDED_PREFIX + "UNC\\" + spelled.lstrip("\\")
    return EXTENDED_PREFIX + spelled


def os_path(path: str | os.PathLike[str]) -> str:
    """Path to hand to the OS: extended form on Windows when needed, else as-is."""
    if os.name == "nt" and needs_extended_prefix(path):
        return extended_path(path)
    return str(path)


def is_reserved_name(name: str) -> bool:
    stem = name.split(".", 1)[0].strip().upper()
    return stem in RESERVED_DEVICE_NAMES


# --------------------------------------------------------------------------- round trip
def _build_path_of_length(base: Path, nchars: int) -> Path:
    """Build a path under ``base`` whose ``str`` is exactly ``nchars`` long."""
    base_s = str(base)
    if len(base_s) + 2 > nchars:
        raise ValueError(f"base path too long ({len(base_s)}) for target {nchars}")
    remaining = nchars - len(base_s) - 1  # separator
    parts: list[str] = []
    seg = 60
    while remaining > 0:
        if remaining <= seg + 1:
            parts.append("f" * remaining)
            remaining = 0
        else:
            parts.append("d" * seg)
            remaining -= seg + 1
    return base.joinpath(*parts)


def _oob_check(target: Path, payload: bytes) -> dict[str, Any]:
    """Out-of-band existence + content check that never imports this module."""
    out: dict[str, Any] = {
        "exists": None,
        "nchars": None,
        "payload_match": None,
        "same_path": None,
        "get_item_ran": False,
        "pwsh": None,
        "find": {},
    }
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    target_s = str(target)
    if pwsh and os.name == "nt":
        try:
            proc = subprocess.run(
                [pwsh, "-NoProfile", "-NonInteractive", "-Command",
                 "$i = Get-Item -LiteralPath $args[0] -ErrorAction Stop; "
                 "Write-Output $i.FullName; Write-Output $i.Length",
                 os_path(target)],
                capture_output=True, text=True, timeout=60,
            )
            out["pwsh"] = pwsh
            out["get_item_ran"] = proc.returncode == 0
            if proc.returncode == 0:
                lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
                full = lines[0] if lines else ""
                full = full[len(EXTENDED_PREFIX):] if full.startswith(EXTENDED_PREFIX) else full
                out["exists"] = True
                out["nchars"] = len(full)
                out["same_path"] = os.path.normcase(full) == os.path.normcase(target_s)
        except (OSError, subprocess.SubprocessError) as exc:
            out["pwsh_error"] = str(exc)
    # Independent python process: open + read without importing plugin.longpath_fs.
    code = (
        "import sys,os,hashlib\n"
        "p=sys.argv[1]\n"
        "ok=os.path.isfile(p)\n"
        "print('exists', ok)\n"
        "print('nchars', len(p))\n"
        "print('sha', hashlib.sha256(open(p,'rb').read()).hexdigest() if ok else '')\n"
    )
    try:
        proc = subprocess.run([sys.executable, "-c", code, os_path(target)],
                              capture_output=True, text=True, timeout=60)
        kv = dict(ln.split(" ", 1) for ln in proc.stdout.splitlines() if " " in ln)
        import hashlib

        exists = kv.get("exists") == "True"
        if out["exists"] is None:
            out["exists"] = exists
            out["nchars"] = int(kv.get("nchars") or 0) if exists else None
        out["payload_match"] = exists and kv.get("sha", "") == hashlib.sha256(payload).hexdigest()
        out["independent_python"] = proc.returncode == 0
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        out["independent_python_error"] = str(exc)
    # find(1) exact-path confirmation on POSIX.
    find = shutil.which("find")
    if find and os.name != "nt":
        try:
            proc = subprocess.run([find, str(target.parent), "-maxdepth", "1", "-type", "f",
                                   "-name", target.name], capture_output=True, text=True, timeout=60)
            hits = [ln for ln in proc.stdout.splitlines() if ln.strip()]
            out["find"] = {"exact": hits == [target_s], "hits": len(hits)}
            if out["same_path"] is None:
                out["same_path"] = hits == [target_s]
        except (OSError, subprocess.SubprocessError) as exc:
            out["find"] = {"exact": False, "error": str(exc)}
    return out


def _count_payload_files(root: Path, payload: bytes) -> int:
    hits = 0
    for dirpath, _dirs, files in os.walk(os_path(root)):
        for name in files:
            p = os.path.join(dirpath, name)
            try:
                with open(p, "rb") as fh:
                    if fh.read() == payload:
                        hits += 1
            except OSError:
                continue
    return hits


def round_trip_long_path(base_dir: str | os.PathLike[str], min_chars: int = 300) -> dict[str, Any]:
    """Create/write/read/delete a path of exactly ``min_chars`` characters.

    Returns a record with the helper round-trip signals AND an out-of-band
    confirmation (``oob``) produced without importing this module.
    """
    base = Path(base_dir).resolve()
    target = _build_path_of_length(base, min_chars)
    payload = f"IMP-0021 {uuid.uuid4().hex}\n".encode("utf-8")
    rec: dict[str, Any] = {
        "path": str(target),
        "nchars": len(str(target)),
        "win32_nchars": len(win32_spelling(target)),
        "needs_extended": needs_extended_prefix(target),
        "extended": extended_path(target),
        "payload_bytes": len(payload),
    }
    os.makedirs(os_path(target.parent), exist_ok=True)
    with open(os_path(target), "wb") as fh:
        fh.write(payload)
    with open(os_path(target), "rb") as fh:
        rec["read_ok"] = fh.read() == payload
    rec["grep_hits"] = _count_payload_files(base, payload)
    rec["unique_payload_file"] = rec["grep_hits"] == 1
    rec["oob"] = _oob_check(target, payload)
    os.remove(os_path(target))
    rec["deleted"] = not os.path.exists(os_path(target))
    rec["oob_after_exists"] = _oob_check(target, payload).get("exists")
    return rec


# --------------------------------------------------------------------------- reserved names
def plant_nul_fixture(root: str | os.PathLike[str]) -> dict[str, Any]:
    """Plant a tree containing a file literally named ``NUL`` plus ordinary files."""
    root_p = Path(root)
    (root_p / "nested").mkdir(parents=True, exist_ok=True)
    files = {
        root_p / "keep.txt": b"keep\n",
        root_p / "nested" / "inner.txt": b"inner\n",
        root_p / "NUL": b"reserved device name as a file\n",
        root_p / "nested" / "COM1.log": b"reserved with extension\n",
    }
    planted: list[str] = []
    for path, data in files.items():
        try:
            with open(os_path(path), "wb") as fh:
                fh.write(data)
            planted.append(str(path.relative_to(root_p).as_posix()))
        except OSError as exc:  # Windows refuses NUL as a file name
            planted.append(f"{path.relative_to(root_p).as_posix()}!{type(exc).__name__}")
    return {"root": str(root_p), "planted": planted,
            "reserved": sorted(p for p in planted if is_reserved_name(PurePosixPath(p).name))}


def safe_enumerate(root: str | os.PathLike[str]) -> list[str]:
    """Enumerate files as POSIX-style relative paths without ``os.path.relpath``."""
    root_s = os.path.abspath(str(root))
    prefix_len = len(root_s.rstrip(os.sep)) + 1
    rels: list[str] = []
    stack = [root_s]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(os_path(cur)) as it:
                entries = list(it)
        except OSError as exc:
            raise OSError(f"enumerate failed under {cur}: {exc}") from exc
        for ent in entries:
            full = os.path.join(cur, ent.name)
            if ent.is_dir(follow_symlinks=False):
                stack.append(full)
            else:
                rels.append(full[prefix_len:].replace(os.sep, "/"))
    return sorted(rels)


def unsafe_enumerate(root: str | os.PathLike[str]) -> list[str]:
    """Windows-naive enumerator: relpath-style, raises on reserved device names.

    Mirrors ``ntpath.relpath`` semantics where ``NUL`` resolves to the device
    mount ``\\\\.\\NUL`` and relpath refuses to relate two different mounts.
    """
    root_s = os.path.abspath(str(root))
    drive = "C:" if os.name != "nt" else (os.path.splitdrive(root_s)[0] or "C:")
    rels: list[str] = []
    for dirpath, _dirs, files in os.walk(root_s):
        for name in files:
            if is_reserved_name(name):
                device = name.split(".", 1)[0].upper()
                raise ValueError(
                    f"path is on mount '\\\\.\\{device}', start on mount '{drive}'"
                )
            rels.append(os.path.relpath(os.path.join(dirpath, name), root_s))
    return sorted(rels)


def enumerate_both(root: str | os.PathLike[str]) -> dict[str, Any]:
    """Run the safe and the naive enumerator; surface the naive error, never swallow it."""
    safe = safe_enumerate(root)
    out: dict[str, Any] = {
        "root": str(root),
        "safe_paths": safe,
        "safe_count": len(safe),
        "empty_safe": len(safe) == 0,
        "nul_rels": [p for p in safe if is_reserved_name(PurePosixPath(p).name)],
        "keep_present": "keep.txt" in safe,
        "nested_present": any(p.startswith("nested/") for p in safe),
        "naive_raised": False,
        "naive_error": None,
        "naive_paths": None,
    }
    try:
        out["naive_paths"] = unsafe_enumerate(root)
    except ValueError as exc:
        out["naive_raised"] = True
        out["naive_error"] = str(exc)
    host: dict[str, Any] = {"platform": platform.system(), "raised": False, "error": None}
    try:
        for dirpath, _dirs, files in os.walk(str(root)):
            for name in files:
                os.path.relpath(os.path.join(dirpath, name), str(root))
    except ValueError as exc:
        host["raised"] = True
        host["error"] = str(exc)
    out["host_os_relpath"] = host
    return out


__all__ = [
    "EXTENDED_PREFIX",
    "WIN32_MAX_PATH",
    "RESERVED_DEVICE_NAMES",
    "enumerate_both",
    "extended_path",
    "is_reserved_name",
    "needs_extended_prefix",
    "os_path",
    "plant_nul_fixture",
    "round_trip_long_path",
    "safe_enumerate",
    "unsafe_enumerate",
    "win32_spelling",
]
