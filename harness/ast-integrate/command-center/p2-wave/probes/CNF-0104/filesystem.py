"""Mount a real VFAT loop (case-insensitive) and a native POSIX temp dir (case-sensitive)."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

MKFS = "/usr/sbin/mkfs.vfat"


def fstype_of(path: Path) -> str:
    path = path.resolve()
    best = ("", "")
    try:
        lines = Path("/proc/mounts").read_text(encoding="utf-8").splitlines()
    except OSError:
        return "unknown"
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        mountpoint, fstype = parts[1], parts[2]
        mountpoint = mountpoint.replace("\\040", " ")
        if str(path) == mountpoint or str(path).startswith(mountpoint.rstrip("/") + "/"):
            if len(mountpoint) >= len(best[0]):
                best = (mountpoint, fstype)
    return best[1] or "unknown"


def list_regular_files(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for p in sorted(root.iterdir(), key=lambda x: x.name):
        if p.is_file():
            out[p.name] = p.read_bytes()
    return out


def read_name(root: Path, name: str) -> bytes | None:
    p = root / name
    try:
        if p.exists() and p.is_file():
            return p.read_bytes()
    except OSError:
        return None
    return None


@contextmanager
def case_sensitive_root() -> Iterator[Path]:
    tmp = Path(tempfile.mkdtemp(prefix="cnf0104-posix-"))
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _drvfs_temp_parent() -> Path | None:
    for cand in (
        Path("/mnt/c/Users/Prekzursil/AppData/Local/Temp"),
        Path("/mnt/c/Windows/Temp"),
    ):
        if cand.is_dir():
            return cand
    return None


@contextmanager
def case_insensitive_root() -> Iterator[Path]:
    """Case-insensitive last-wins root: VFAT loop if permitted, else DrvFS."""
    tmp = Path(tempfile.mkdtemp(prefix="cnf0104-vfat-"))
    img = tmp / "fat.img"
    mnt = tmp / "mnt"
    mnt.mkdir()
    mounted = False
    try:
        if Path(MKFS).is_file():
            subprocess.run(
                ["dd", "if=/dev/zero", f"of={img}", "bs=1M", "count=16", "status=none"],
                check=True,
                capture_output=True,
                text=True,
            )
            mk = subprocess.run(
                [MKFS, "-n", "CNF0104", str(img)],
                capture_output=True,
                text=True,
            )
            if mk.returncode == 0:
                (tmp / "mkfs.out").write_text(
                    (mk.stdout or "") + (mk.stderr or ""), encoding="utf-8"
                )
                for argv in (
                    ["mount", "-o", "loop,shortname=winnt,utf8=1", str(img), str(mnt)],
                    [
                        "sudo",
                        "-n",
                        "mount",
                        "-o",
                        "loop,uid=0,gid=0,shortname=winnt,utf8=1",
                        str(img),
                        str(mnt),
                    ],
                ):
                    got = subprocess.run(argv, capture_output=True, text=True)
                    if got.returncode == 0:
                        mounted = True
                        yield mnt
                        return
        win = _drvfs_temp_parent()
        if win is None:
            raise RuntimeError("case-insensitive-root-unavailable")
        drvfs = Path(tempfile.mkdtemp(prefix="cnf0104-drvfs-", dir=str(win)))
        try:
            yield drvfs
        finally:
            shutil.rmtree(drvfs, ignore_errors=True)
    finally:
        if mounted:
            subprocess.run(["umount", str(mnt)], capture_output=True, text=True)
        shutil.rmtree(tmp, ignore_errors=True)
