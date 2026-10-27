"""Independent ustar reader (not tarfile)."""
from __future__ import annotations

from pathlib import Path
from typing import Any


class UstarError(ValueError):
    pass


def _oct(field: bytes) -> int:
    text = field.strip(b"\x00").strip().decode("ascii", "replace")
    if not text:
        return 0
    return int(text, 8)


def read_entries(path: Path) -> list[dict[str, Any]]:
    data = Path(path).read_bytes()
    if len(data) < 512:
        raise UstarError("truncated tar")
    entries: list[dict[str, Any]] = []
    off = 0
    while off + 512 <= len(data):
        block = data[off : off + 512]
        if block == b"\x00" * 512:
            break
        name = block[0:100].split(b"\x00", 1)[0].decode("utf-8", "replace")
        prefix = block[345:500].split(b"\x00", 1)[0].decode("utf-8", "replace")
        if prefix:
            name = prefix.rstrip("/") + "/" + name
        size = _oct(block[124:136])
        typ = block[156:157]
        off += 512
        off += ((size + 511) // 512) * 512
        if not name or name.endswith("/"):
            continue
        if typ in {b"5", b"L", b"g", b"x"}:
            continue
        entries.append({"path": name.replace("\\", "/"), "size": size})
    if not entries and len(data) < 1024:
        raise UstarError("no members")
    return entries
