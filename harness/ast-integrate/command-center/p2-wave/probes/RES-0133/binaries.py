"""Pinned gitleaks 8.30.1 and trufflehog 3.96.0, checksum-verified."""
from __future__ import annotations

import hashlib
import subprocess
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE / ".bin"

GITLEAKS_VER = "8.30.1"
GITLEAKS_URL = (
    "https://github.com/gitleaks/gitleaks/releases/download/"
    f"v{GITLEAKS_VER}/gitleaks_{GITLEAKS_VER}_linux_x64.tar.gz"
)
GITLEAKS_SHA256 = "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"

TRUFFLEHOG_VER = "3.96.0"
TRUFFLEHOG_URL = (
    "https://github.com/trufflesecurity/trufflehog/releases/download/"
    f"v{TRUFFLEHOG_VER}/trufflehog_{TRUFFLEHOG_VER}_linux_amd64.tar.gz"
)
TRUFFLEHOG_SHA256 = "7105f1cd6577f058a9e39d0578f1a99c8a1e481e4d3512cd8a09acfe22a0fdc0"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path, expect: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and _sha256(dest) == expect:
        return
    subprocess.run(
        ["curl", "-fsSL", "-o", str(dest), url],
        check=True,
        timeout=120,
    )
    got = _sha256(dest)
    if got != expect:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"checksum mismatch for {dest.name}: {got}")


def _extract_member(tarball: Path, member: str, dest: Path) -> None:
    with tarfile.open(tarball, "r:gz") as tf:
        tf.extract(member, path=dest.parent, filter="data")
    extracted = dest.parent / member
    if extracted != dest:
        extracted.replace(dest)
    dest.chmod(0o755)


def gitleaks_bin() -> Path:
    exe = BIN / "gitleaks"
    if exe.is_file() and exe.stat().st_size > 1_000_000:
        return exe
    tar = BIN / f"gitleaks_{GITLEAKS_VER}_linux_x64.tar.gz"
    _download(GITLEAKS_URL, tar, GITLEAKS_SHA256)
    _extract_member(tar, "gitleaks", exe)
    return exe


def trufflehog_bin() -> Path:
    exe = BIN / "trufflehog"
    if exe.is_file() and exe.stat().st_size > 1_000_000:
        return exe
    tar = BIN / f"trufflehog_{TRUFFLEHOG_VER}_linux_amd64.tar.gz"
    _download(TRUFFLEHOG_URL, tar, TRUFFLEHOG_SHA256)
    _extract_member(tar, "trufflehog", exe)
    return exe
