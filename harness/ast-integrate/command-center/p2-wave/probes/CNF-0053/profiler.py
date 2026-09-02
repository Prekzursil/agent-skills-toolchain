"""Import-time profiler: python -X importtime plus optional cold-cache fadvise."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

IMPORT_LINE = re.compile(
    r"^import time:\s+(\d+)\s+\|\s+(\d+)\s+\|\s+(\S.*?)\s*$"
)
ENTRY = "tool_startup.entry"
PAYLOAD_NAME = "_payload.bin"
PAYLOAD_BYTES = 1_048_576
TOOL_PKG = "tool_startup"


def write_payload(path: Path, size: int = PAYLOAD_BYTES) -> None:
    block = bytes(range(256)) * 4  # 1024 bytes, deterministic
    path.write_bytes(block * (size // 1024))


def stage_commit(src: Path, dest: Path, with_payload: bool) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    pkg = dest / TOOL_PKG
    payload = pkg / PAYLOAD_NAME
    if with_payload:
        write_payload(payload)
    elif payload.exists():
        payload.unlink()
    for pyc in pkg.rglob("__pycache__"):
        shutil.rmtree(pyc, ignore_errors=True)
    return dest


def parse_importtime(text: str) -> list[dict]:
    rows = []
    for line in (text or "").splitlines():
        m = IMPORT_LINE.match(line)
        if not m:
            continue
        self_us = int(m.group(1))
        cum_us = int(m.group(2))
        name = m.group(3).strip()
        rows.append(
            {
                "module": name,
                "self_us": self_us,
                "cumulative_us": cum_us,
                "self_ms": round(self_us / 1000.0, 6),
            }
        )
    return rows


def drop_fs_cache(paths: list[Path]) -> dict:
    advised = 0
    errors: list[str] = []
    if not hasattr(os, "posix_fadvise"):
        return {"method": "unavailable", "advised": 0, "errors": ["no posix_fadvise"]}
    flag = os.POSIX_FADV_DONTNEED
    for path in paths:
        if not path.is_file():
            continue
        fd = os.open(path, os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, flag)
            advised += 1
        except OSError as exc:
            errors.append(f"{path.name}:{type(exc).__name__}")
        finally:
            os.close(fd)
    return {
        "method": "posix_fadvise(POSIX_FADV_DONTNEED)",
        "advised": advised,
        "errors": errors,
    }


def iter_cache_targets(root: Path) -> list[Path]:
    out: list[Path] = []
    pkg = root / TOOL_PKG
    if not pkg.is_dir():
        return out
    for p in pkg.rglob("*"):
        if p.is_file() and p.suffix in {".py", ".bin"}:
            out.append(p)
    return out


def run_import(
    commit_root: Path,
    *,
    cold: bool = False,
    python: str = sys.executable,
) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(commit_root)
    env.pop("PYTHONSTARTUP", None)
    fadvise = None
    if cold:
        fadvise = drop_fs_cache(iter_cache_targets(commit_root))
    t0 = time.perf_counter()
    proc = subprocess.run(
        [python, "-B", "-X", "importtime", "-c", f"import {ENTRY}"],
        cwd=str(commit_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    wall_ms = (time.perf_counter() - t0) * 1000.0
    text = (proc.stderr or "") + "\n" + (proc.stdout or "")
    rows = parse_importtime(text)
    if proc.returncode != 0:
        raise RuntimeError(
            f"import {ENTRY} failed rc={proc.returncode} "
            f"stderr={(proc.stderr or '')[-800:]}"
        )
    if not rows:
        raise RuntimeError("importtime produced no parseable rows")
    pkg_rows = [r for r in rows if r["module"].startswith("tool_startup")]
    entry = next((r for r in rows if r["module"] == ENTRY), None)
    return {
        "rc": proc.returncode,
        "wall_ms": round(wall_ms, 4),
        "cache": "cold" if cold else "warm",
        "fadvise": fadvise,
        "modules": rows,
        "package_modules": pkg_rows,
        "entry_cumulative_us": entry["cumulative_us"] if entry else None,
        "package_self_us": sum(r["self_us"] for r in pkg_rows),
        "importtime_self_ms": round(sum(r["self_us"] for r in rows) / 1000.0, 4),
    }


def median(values: list[float]) -> float:
    if not values:
        raise ValueError("median of empty")
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


def iqr(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    s = sorted(values)
    n = len(s)
    def pct(p: float) -> float:
        if n == 1:
            return float(s[0])
        idx = p * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return s[lo] * (1 - frac) + s[hi] * frac
    return float(pct(0.75) - pct(0.25))
