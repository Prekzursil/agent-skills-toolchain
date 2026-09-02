"""Canonical and naive ZIP packers for RES-0134 asset-package reproducibility.

Two mechanically different writers:
  pack_zipfile  — stdlib zipfile, ZIP_DEFLATED level 9 (delivery recipe)
  pack_stored   — hand-rolled ZIP_STORED via struct (independent pass B)
"""
from __future__ import annotations

import io
import struct
import unicodedata
import zipfile
import zlib
from pathlib import Path
from typing import Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
DEFINITION_PATH = HERE / "DEFINITION.json"

TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".md",
    ".py",
    ".rst",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
ALLOW_SUFFIXES = set(TEXT_SUFFIXES)
EXCLUDE_DIRS = {".git", ".venv", "__pycache__", "node_modules"}
EXCLUDE_SUFFIXES = {".pyc"}
RECIPE_DATE = (1980, 1, 1, 0, 0, 0)
RECIPE_CREATE_SYSTEM = 3
RECIPE_MODE = 0o644  # 420 decimal, frozen in DEFINITION.json
UTF8_FLAG = 1 << 11


def posix_name(name: str) -> str:
    return str(name).replace("\\", "/").lstrip("/")


def is_text_name(name: str) -> bool:
    return Path(posix_name(name)).suffix.lower() in TEXT_SUFFIXES


def should_skip(name: str) -> bool:
    parts = [p for p in posix_name(name).split("/") if p]
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    suf = Path(parts[-1]).suffix.lower() if parts else ""
    return suf in EXCLUDE_SUFFIXES


def to_lf(body: bytes) -> bytes:
    return body.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def dos_time(date_time: Sequence[int]) -> tuple[int, int]:
    y, m, d, hh, mm, ss = date_time
    dt = (hh << 11) | (mm << 5) | (ss // 2)
    dd = ((y - 1980) << 9) | (m << 5) | d
    return dt, dd


def normalize_members(members: Mapping[str, bytes]) -> list[tuple[str, bytes]]:
    """Apply the frozen recipe to (name, body) pairs. Drops junk paths."""
    out: dict[str, bytes] = {}
    for raw_name, body in members.items():
        if should_skip(raw_name):
            continue
        name = unicodedata.normalize("NFC", posix_name(raw_name))
        if not name or name.endswith("/"):
            continue
        suf = Path(name).suffix.lower()
        if suf not in ALLOW_SUFFIXES:
            continue
        payload = to_lf(body) if is_text_name(name) else bytes(body)
        folded = name.casefold()
        for existing, _b in out.items():
            if existing.casefold() == folded and existing != name:
                raise ValueError(f"Windows-unsafe case collision: {existing!r} vs {name!r}")
        out[name] = payload
    return sorted(out.items(), key=lambda kv: kv[0].encode("utf-8"))


def pack_zipfile(
    members: Iterable[tuple[str, bytes]],
    *,
    date_time: tuple[int, ...] = RECIPE_DATE,
    create_system: int = RECIPE_CREATE_SYSTEM,
    external_attr: int | None = None,
    compresslevel: int = 9,
    normalize: bool = False,
) -> bytes:
    """Stdlib zipfile packer. If normalize=True, run the frozen recipe first."""
    items = list(members)
    if normalize:
        items = normalize_members(dict(items))
    attr = (RECIPE_MODE << 16) if external_attr is None else external_attr
    buf = io.BytesIO()
    with zipfile.ZipFile(
        buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=compresslevel
    ) as zf:
        for name, body in items:
            info = zipfile.ZipInfo(filename="placeholder", date_time=tuple(date_time))
            info.filename = name
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = create_system
            info.external_attr = attr
            info.comment = b""
            info.extra = b""
            zf.writestr(info, body, compresslevel=compresslevel)
    return buf.getvalue()


def pack_stored(
    members: Iterable[tuple[str, bytes]],
    *,
    date_time: tuple[int, ...] = RECIPE_DATE,
    create_system: int = RECIPE_CREATE_SYSTEM,
    external_attr: int | None = None,
    normalize: bool = False,
) -> bytes:
    """Independent ZIP_STORED writer (no zipfile.ZipFile)."""
    items = list(members)
    if normalize:
        items = normalize_members(dict(items))
    attr = (RECIPE_MODE << 16) if external_attr is None else external_attr
    dos_t, dos_d = dos_time(date_time)
    chunks: list[bytes] = []
    central: list[bytes] = []
    offset = 0
    for name, body in items:
        raw_name = name.encode("utf-8")
        payload = bytes(body)
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        size = len(payload)
        flag = UTF8_FLAG
        local = struct.pack(
            "<4sHHHHHIIIHH",
            b"PK\x03\x04",
            20,
            flag,
            0,
            dos_t,
            dos_d,
            crc,
            size,
            size,
            len(raw_name),
            0,
        )
        rec = local + raw_name + payload
        chunks.append(rec)
        version_made = 20 | (create_system << 8)
        cd = struct.pack(
            "<4sHHHHHHIIIHHHHHII",
            b"PK\x01\x02",
            version_made,
            20,
            flag,
            0,
            dos_t,
            dos_d,
            crc,
            size,
            size,
            len(raw_name),
            0,
            0,
            0,
            0,
            attr,
            offset,
        )
        central.append(cd + raw_name)
        offset += len(rec)
    body_blob = b"".join(chunks)
    cd_blob = b"".join(central)
    eocd = struct.pack(
        "<4sHHHHIIH",
        b"PK\x05\x06",
        0,
        0,
        len(items),
        len(items),
        len(cd_blob),
        len(body_blob),
        0,
    )
    return body_blob + cd_blob + eocd


def recipe_pack(members: Mapping[str, bytes]) -> bytes:
    return pack_zipfile(list(members.items()), normalize=True)
