"""Extent measurement: marked-span UTF-8 bytes, not file size and not impression."""
from __future__ import annotations

from pathlib import Path

from plant_payload import BEGIN_MARK, END_MARK, PLANT_REL


def extract_marked_bytes(text: str) -> bytes:
    start = text.find(BEGIN_MARK)
    end = text.find(END_MARK)
    if start < 0 or end < 0 or end <= start:
        raise ValueError("marked third-party span not found")
    interior = text[start + len(BEGIN_MARK) : end]
    if interior.startswith("\n"):
        interior = interior[1:]
    if interior.endswith("\n"):
        interior = interior[:-1]
    return interior.encode("utf-8")


def measure_marked_file(repo: Path, rel: str = PLANT_REL) -> dict:
    path = repo / rel
    text = path.read_text(encoding="utf-8")
    payload = extract_marked_bytes(text)
    return {
        "path": rel.replace("\\", "/"),
        "measured_bytes": len(payload),
        "method": "marked-span-utf8-byte-count",
        "begin": BEGIN_MARK,
        "end": END_MARK,
    }


def naive_whole_file_bytes(repo: Path, rel: str = PLANT_REL) -> int:
    """Broken strawman: file size including the first-party wrapper."""
    return (repo / rel).stat().st_size


def count_marker_bytes(text: str, markers: tuple[str, ...]) -> dict:
    total = 0
    counts = {}
    for m in markers:
        n = text.count(m)
        counts[m] = n
        total += n * len(m.encode("utf-8"))
    return {"bytes": total, "counts": counts}
