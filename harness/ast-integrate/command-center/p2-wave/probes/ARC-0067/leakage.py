"""Leakage scan over a directory tree using the enumerated pattern list."""
from __future__ import annotations

import json
from pathlib import Path

from identities import enumerated_literals, find_hits

SKIP_DIR_NAMES = {".git", "__pycache__"}


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.exists():
        return files
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def scan_tree(root: Path) -> dict:
    hits: list[dict] = []
    files = iter_files(root)
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for hit in find_hits(text):
            rel = path.as_posix()
            hits.append(
                {
                    "path": rel,
                    "span": hit["span"],
                    "start": hit["start"],
                }
            )
    return {
        "root": str(root),
        "file_count": len(files),
        "pattern_count": len(enumerated_literals()),
        "hit_count": len(hits),
        "hits": hits[:50],
    }


def plant_and_scan(sample_text: str, plant: str) -> dict:
    """Detector control: same scanner must fire when a listed name is planted."""
    clean = find_hits(sample_text)
    planted = find_hits(sample_text + "\n" + plant + "\n")
    return {
        "plant": plant,
        "clean_hits": len(clean),
        "planted_hits": len(planted),
        "detector_fired": len(planted) > len(clean),
    }


def dump_scan(doc: dict, path: Path) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
