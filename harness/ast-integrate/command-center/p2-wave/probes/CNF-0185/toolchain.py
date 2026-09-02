"""Isolate CI-pinned and comparison ruff binaries. Never use ambient PATH."""
from __future__ import annotations

import io
import json
import os
import stat
import subprocess
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLCHAIN = HERE / "toolchains"

RUFF_PIN = "0.15.17"
RUFF_LOCAL_PRECEDENT = "0.15.22"
PYPI = "https://pypi.org/pypi/ruff/{version}/json"


def ruff_bin(version: str) -> Path:
    return TOOLCHAIN / f"ruff-{version}" / "ruff"


def _wheel_url(version: str) -> str:
    data = json.load(urllib.request.urlopen(PYPI.format(version=version), timeout=30))
    for row in data["urls"]:
        name = row.get("filename") or ""
        if (
            row.get("packagetype") == "bdist_wheel"
            and "manylinux_2_17_x86_64" in name
            and "musllinux" not in name
        ):
            return str(row["url"])
    raise RuntimeError(f"no manylinux x86_64 wheel for ruff {version}")


def ensure_ruff(version: str) -> Path:
    dest = ruff_bin(version)
    if dest.is_file() and dest.stat().st_size > 1_000_000:
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = urllib.request.urlopen(_wheel_url(version), timeout=120).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("/ruff") or n == "ruff")
        dest.write_bytes(zf.read(name))
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR)
    return dest


def run_ruff(
    version: str, args: list[str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    binary = ensure_ruff(version)
    env = os.environ.copy()
    env["PATH"] = str(binary.parent)
    return subprocess.run(
        [str(binary), *args],
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def ruff_version_stdout(version: str) -> tuple[str, str]:
    binary = ensure_ruff(version)
    invocation = f"{binary.as_posix()} version"
    proc = run_ruff(version, ["version"])
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return invocation, out


def verdict_from_proc(proc: subprocess.CompletedProcess[str]) -> str:
    if proc.returncode == 0:
        return "PASS"
    if proc.returncode == 1:
        return "FAIL"
    return "ERROR"
