"""Independent ZIP central-directory reader (not zipfile)."""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any


class ZipCdError(ValueError):
    pass


def read_entries(path: Path) -> list[dict[str, Any]]:
    data = Path(path).read_bytes()
    eocd = data.rfind(b"PK\x05\x06")
    if eocd < 0 or eocd + 22 > len(data):
        raise ZipCdError("missing end of central directory")
    cd_size, cd_off = struct.unpack_from("<II", data, eocd + 12)
    if cd_off + cd_size > len(data):
        raise ZipCdError("central directory truncated")
    entries: list[dict[str, Any]] = []
    off = cd_off
    end = cd_off + cd_size
    while off < end:
        if data[off : off + 4] != b"PK\x01\x02":
            raise ZipCdError("bad central directory signature")
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, off + 28)
        uncomp = struct.unpack_from("<I", data, off + 24)[0]
        name = data[off + 46 : off + 46 + name_len].decode("utf-8", "replace").replace("\\", "/")
        entries.append({"path": name, "size": uncomp})
        off += 46 + name_len + extra_len + comment_len
    return [e for e in entries if e["path"] and not e["path"].endswith("/")]
