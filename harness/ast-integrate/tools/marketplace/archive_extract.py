"""Safe archive import: normalize, then contain, then write. No extractall."""
from __future__ import annotations

import io
import posixpath
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

DEVICE_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "CLOCK$",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)
RATIO_LIMIT = 10000.0


class ArchiveExtractError(Exception):
    def __init__(self, code: str, member: str = "", detail: str = "") -> None:
        super().__init__(f"{code}:{member}:{detail}")
        self.code = code
        self.member = member
        self.detail = detail


@dataclass
class ExtractReport:
    ok: bool
    error: str | None = None
    rejected: bool = False
    written: list[str] = field(default_factory=list)
    code: str | None = None

    def __bool__(self) -> bool:
        return self.ok


def _device_stem(name: str) -> str:
    base = posixpath.basename(name.replace("\\", "/"))
    stem = base.split(".")[0]
    return stem.upper()


def normalize_member_name(name: str) -> str:
    raw = str(name or "").replace("\\", "/")
    if raw.startswith("/") or (len(raw) >= 2 and raw[1] == ":"):
        raise ArchiveExtractError("ABSOLUTE", raw)
    if raw.startswith("\\\\") or raw.startswith("//"):
        raise ArchiveExtractError("ABSOLUTE", raw)
    norm = posixpath.normpath(raw)
    if norm in {".", ""}:
        raise ArchiveExtractError("EMPTY", raw)
    if norm.startswith("../") or norm == ".." or norm.startswith("..\\"):
        raise ArchiveExtractError("TRAVERSAL", raw)
    if _device_stem(norm) in DEVICE_NAMES:
        raise ArchiveExtractError("DEVICE_NAME", raw)
    return norm.lstrip("./")


def assert_contained_after_normalize(dest: Path, member: str) -> Path:
    normalized = normalize_member_name(member)
    root = dest.resolve()
    target = (root / normalized).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ArchiveExtractError("TRAVERSAL", member) from exc
    return target


def census_files(dest: Path) -> list[str]:
    if not dest.exists():
        return []
    root = dest.resolve()
    out: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.resolve().relative_to(root).as_posix()
        out.append(rel)
    return out


def _write_bytes(dest: Path, member: str, data: bytes) -> str:
    target = assert_contained_after_normalize(dest, member)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return normalize_member_name(member)


def _iter_tar(blob: bytes) -> Iterable[tuple[str, bytes, str]]:
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tf:
        for info in tf.getmembers():
            if info.issym():
                raise ArchiveExtractError("SYMLINK", info.name, info.linkname or "")
            if info.islnk():
                raise ArchiveExtractError("HARDLINK", info.name, info.linkname or "")
            if not info.isreg():
                if info.isdir():
                    continue
                raise ArchiveExtractError("SPECIAL", info.name)
            handle = tf.extractfile(info)
            payload = handle.read() if handle is not None else b""
            yield info.name, payload, "reg"


def _iter_zip(blob: bytes) -> Iterable[tuple[str, bytes, str]]:
    with zipfile.ZipFile(io.BytesIO(blob), mode="r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            uncompressed = int(info.file_size or 0)
            compressed = max(int(info.compress_size or 0), 1)
            if uncompressed / compressed > RATIO_LIMIT:
                raise ArchiveExtractError("RATIO", info.filename)
            yield info.filename, zf.read(info), "reg"


def extract_import_archive(blob: bytes, dest: Path) -> ExtractReport:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    try:
        if len(blob) >= 4 and blob[:2] == b"PK":
            members = list(_iter_zip(blob))
        else:
            members = list(_iter_tar(blob))
        # Pre-write containment pass: every member is normalised and contained
        # before a single byte lands, so a hostile member late in the archive
        # cannot leave earlier members half-extracted. _write_bytes re-asserts.
        for name, _payload, _kind in members:
            assert_contained_after_normalize(dest, name)
        for name, payload, _kind in members:
            written.append(_write_bytes(dest, name, payload))
        return ExtractReport(ok=True, written=sorted(set(written)))
    except ArchiveExtractError as exc:
        return ExtractReport(
            ok=False,
            error=f"{exc.code}:{exc.member}",
            rejected=True,
            written=[],
            code=exc.code,
        )
    except (tarfile.TarError, zipfile.BadZipFile, OSError, ValueError) as exc:
        return ExtractReport(
            ok=False,
            error=type(exc).__name__,
            rejected=True,
            written=[],
            code="DECODE",
        )
