"""Independent unique-line differ for IMP-0024 (does not import three_way_merge)."""
from __future__ import annotations

import hashlib
from typing import Any


def _norm(data: bytes | str) -> list[str]:
    if isinstance(data, bytes):
        text = data.decode("utf-8", errors="replace")
    else:
        text = data
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.split("\n")


def _sha_lines(lines: list[str]) -> str:
    blob = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest()


def unique_ours_lines(base: bytes | str, ours: bytes | str) -> list[str]:
    base_set = set(_norm(base))
    unique = [ln for ln in _norm(ours) if ln not in base_set and ln != ""]
    return unique


def census(base: bytes | str, ours: bytes | str, after: bytes | str) -> dict[str, Any]:
    unique = unique_ours_lines(base, ours)
    after_lines = set(_norm(after))
    present = [ln for ln in unique if ln in after_lines]
    missing = [ln for ln in unique if ln not in after_lines]
    return {
        "unique_count": len(unique),
        "present_count": len(present),
        "missing_count": len(missing),
        "all_unique_present": not missing,
        "unique_sha256": _sha_lines(unique),
        "present_sha256": _sha_lines(present),
        "missing": missing,
        "present": present,
        "unique": unique,
    }


def assert_unique_lines_survive(base: bytes | str, ours: bytes | str, after: bytes | str) -> None:
    row = census(base, ours, after)
    if not row["all_unique_present"]:
        raise AssertionError(f"unique lines missing: {row['missing']}")
