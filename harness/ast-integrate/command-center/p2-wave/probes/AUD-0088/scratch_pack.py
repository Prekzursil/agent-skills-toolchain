"""Scratch-directory plugin packer for AUD-0088 measurement.

This is not tools/plugin/pack.py (IMP-0002). It builds a zip from a caller-
supplied path list into a scratch directory so probe 2 can unpack a real
archive. Production pack.py is recorded as present/absent, not rebuilt here.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Mapping

ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def write_archive(
    repo: Path,
    members: list[str],
    dest: Path,
    extra: Mapping[str, bytes] | None = None,
) -> dict:
    """Write a zip at dest. extra members are injected as archive-only plants."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted({m.replace("\\", "/").lstrip("./") for m in members})
    extras = {k.replace("\\", "/").lstrip("./"): v for k, v in (extra or {}).items()}
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for rel in ordered:
            src = repo / rel
            data = src.read_bytes() if src.is_file() else b""
            info = zipfile.ZipInfo(filename=rel, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
        for rel, data in sorted(extras.items()):
            info = zipfile.ZipInfo(filename=rel, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    return {
        "path": str(dest),
        "archive_bytes": dest.stat().st_size,
        "member_count": len(ordered) + len(extras),
    }


def list_archive(archive: Path) -> list[dict]:
    """Enumerate real zip members. Directories are skipped. Bodies are not returned."""
    rows: list[dict] = []
    with zipfile.ZipFile(archive, "r") as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if not name or name.endswith("/") or info.is_dir():
                continue
            rows.append(
                {
                    "path": name,
                    "uncompressed_bytes": int(info.file_size),
                    "compressed_bytes": int(info.compress_size),
                }
            )
    rows.sort(key=lambda r: r["path"])
    return rows


def extract_file_names(archive: Path, dest: Path) -> list[str]:
    """Unpack regular files and return POSIX paths relative to dest."""
    dest.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    with zipfile.ZipFile(archive, "r") as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if not name or name.endswith("/") or info.is_dir():
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, open(target, "wb") as out:
                out.write(src.read())
            names.append(name)
    names.sort()
    return names


def bytes_zip(members: Mapping[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        for name, data in sorted(members.items()):
            zf.writestr(name.replace("\\", "/"), data)
    return buf.getvalue()
