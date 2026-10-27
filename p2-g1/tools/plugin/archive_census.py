"""Two-reader archive census: zipfile/tarfile vs ZIP-CD/ustar."""
from __future__ import annotations

import struct
import tarfile
import zipfile
from pathlib import Path
from typing import Any

from ustar import UstarError, read_entries as ustar_entries
from zip_cd import ZipCdError, read_entries as zip_cd_entries


class DetectorFailure(Exception):
    """Readers disagree or the archive is truncated/corrupt."""


def _is_zip(path: Path) -> bool:
    raw = path.read_bytes()[:4]
    return raw.startswith(b"PK")


def _zipfile_entries(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            entries.append({"path": info.filename.replace("\\", "/"), "size": info.file_size})
    return entries


def _tarfile_entries(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with tarfile.open(path, "r") as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            entries.append({"path": m.name.replace("\\", "/"), "size": int(m.size)})
    return entries


def census(archive: Path) -> dict[str, Any]:
    archive = Path(archive)
    try:
        if _is_zip(archive):
            primary = _zipfile_entries(archive)
            independent = zip_cd_entries(archive)
            primary_lib, indep_lib = "zipfile", "zip_cd"
        else:
            primary = _tarfile_entries(archive)
            independent = ustar_entries(archive)
            primary_lib, indep_lib = "tarfile", "ustar"
    except (zipfile.BadZipFile, tarfile.TarError, ZipCdError, UstarError, OSError, struct.error) as exc:
        raise DetectorFailure(str(exc)) from exc

    def _key(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
        return sorted((r["path"], int(r["size"])) for r in rows)

    if _key(primary) != _key(independent):
        raise DetectorFailure("primary/independent disagreement")
    payload = sum(int(r["size"]) for r in primary)
    return {
        "file_count": len(primary),
        "payload_bytes": payload,
        "os_archive_bytes": archive.stat().st_size,
        "primary": {"library": primary_lib, "entries": primary},
        "independent": {"library": indep_lib, "entries": independent},
    }



