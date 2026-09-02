"""Independent unique-line differ for IMP-0024 (does not import three_way_merge).

Byte-level second signal for the upgrade probes: the lines the user added to a
shipped file (present in *ours*, absent from *base*) must all still be present
in the upgraded file (*after*). A file that merely exists would pass an
existence check; the census hashes the surviving set, so a truncated twin that
lost the user's lines produces a different ``present_sha256`` than
``unique_sha256``.
"""
from __future__ import annotations

import hashlib
from typing import Any


def _norm_bytes(data: bytes | str) -> list[bytes]:
    """Split into LF-normalised lines (no terminators); blank lines are kept."""
    raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    raw = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return raw.split(b"\n")


def _norm(data: bytes | str) -> list[str]:
    return [ln.decode("utf-8", errors="replace") for ln in _norm_bytes(data)]


def _sha_lines(lines: list[bytes]) -> str:
    return hashlib.sha256(b"\n".join(lines)).hexdigest()


def _utf8(lines: list[bytes]) -> list[str]:
    return [ln.decode("utf-8", errors="replace") for ln in lines]


def unique_ours_lines(base: bytes | str, ours: bytes | str) -> list[bytes]:
    """Non-empty lines of *ours* that do not occur anywhere in *base*, in order."""
    base_set = set(_norm_bytes(base))
    return [ln for ln in _norm_bytes(ours) if ln not in base_set and ln != b""]


def census(base: bytes | str, ours: bytes | str, after: bytes | str) -> dict[str, Any]:
    """Count the user's unique lines that survive in *after* (JSON-serialisable).

    ``truncated`` is set when unique lines are missing AND *after* has fewer
    lines than *ours* — the shape of a file that still exists but lost content.
    """
    unique = unique_ours_lines(base, ours)
    after_lines = _norm_bytes(after)
    after_set = set(after_lines)
    present = [ln for ln in unique if ln in after_set]
    missing = [ln for ln in unique if ln not in after_set]
    ours_count = len([ln for ln in _norm_bytes(ours) if ln != b""])
    after_count = len([ln for ln in after_lines if ln != b""])
    return {
        "unique_count": len(unique),
        "present_count": len(present),
        "missing_count": len(missing),
        "all_unique_present": not missing,
        "truncated": bool(missing) and after_count < ours_count,
        "unique_sha256": _sha_lines(unique),
        "present_sha256": _sha_lines(present),
        "unique": _utf8(unique),
        "present": _utf8(present),
        "missing": _utf8(missing),
        "unique_utf8": _utf8(unique),
        "present_utf8": _utf8(present),
        "missing_utf8": _utf8(missing),
    }


def assert_unique_lines_survive(base: bytes | str, ours: bytes | str, after: bytes | str) -> None:
    """Raise ``AssertionError`` naming the user's lines that *after* lost."""
    row = census(base, ours, after)
    if not row["all_unique_present"]:
        raise AssertionError(f"unique lines missing: {row['missing_utf8']}")


__all__ = ["assert_unique_lines_survive", "census", "unique_ours_lines"]
