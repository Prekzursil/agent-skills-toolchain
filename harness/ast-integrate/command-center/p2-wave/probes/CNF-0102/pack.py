"""Deterministic zip writer. Bytes in, archive out. No tree walk."""
from __future__ import annotations

import zipfile
from pathlib import Path

ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def write_zip(files: dict[str, bytes], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        for rel, data in sorted(files.items()):
            name = rel.replace("\\", "/").lstrip("/")
            info = zipfile.ZipInfo(filename=name, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)


def append_member(archive: Path, rel: str, data: bytes) -> None:
    """Add one member to an existing zip without consulting inclusion rules."""
    name = rel.replace("\\", "/").lstrip("/")
    with zipfile.ZipFile(
        archive, "a", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        info = zipfile.ZipInfo(filename=name, date_time=ZIP_EPOCH)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = 0o644 << 16
        zf.writestr(info, data)
