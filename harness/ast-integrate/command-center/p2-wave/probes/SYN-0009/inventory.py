"""Walk a corpus and split admitted vs excluded under the SYN-0009 deny-list."""
from __future__ import annotations

from pathlib import Path

from denylist import DIGEST_CLASS, RAW, classify, posix

SKIP_DIR_NAMES = {".git", "__pycache__", ".mypy_cache", ".pytest_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo"}

PHASE_ROOTS = (
    "command-center/phase10",
    "command-center/phase11",
    "command-center/phase12",
    "command-center/phase13",
)

FIXTURE_CORPUS = "command-center/p2-wave/probes/SYN-0009/fixtures/corpus"


def _iter_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        out.append(path)
    return out


def row_for(repo: Path, path: Path) -> dict:
    rel = posix(path.relative_to(repo).as_posix()) if path.is_absolute() else posix(str(path))
    try:
        rel = posix(path.resolve().relative_to(repo.resolve()).as_posix())
    except ValueError:
        rel = posix(str(path))
    return {
        "path": rel,
        "class": classify(rel),
        "bytes": path.stat().st_size if path.is_file() else 0,
    }


def scan(repo: Path, corpus_rel: str) -> dict:
    """Inventory one corpus root. Counts are of files, not bytes."""
    root = repo / corpus_rel
    exists = root.is_dir()
    admitted: list[dict] = []
    excluded: list[dict] = []
    if exists:
        for path in _iter_files(root):
            row = row_for(repo, path)
            if row["class"] == RAW:
                admitted.append(row)
            else:
                excluded.append(row)
    digest_admitted = sum(1 for r in admitted if r["class"] == DIGEST_CLASS)
    return {
        "root": posix(corpus_rel),
        "exists": exists,
        "admitted": admitted,
        "excluded": excluded,
        "admitted_count": len(admitted),
        "excluded_count": len(excluded),
        "digest_class_admitted": digest_admitted,
        "digest_class_excluded": sum(1 for r in excluded if r["class"] == DIGEST_CLASS),
        "sibling_excluded": sum(1 for r in excluded if r["class"] == "sibling-conclusion"),
    }


def merge_inventories(parts: list[dict]) -> dict:
    admitted: list[dict] = []
    excluded: list[dict] = []
    seen_a: set[str] = set()
    seen_e: set[str] = set()
    for part in parts:
        for row in part.get("admitted") or []:
            p = row["path"]
            if p not in seen_a:
                seen_a.add(p)
                admitted.append(row)
        for row in part.get("excluded") or []:
            p = row["path"]
            if p not in seen_e:
                seen_e.add(p)
                excluded.append(row)
    return {
        "admitted": admitted,
        "excluded": excluded,
        "admitted_count": len(admitted),
        "excluded_count": len(excluded),
        "digest_class_admitted": sum(1 for r in admitted if r["class"] == DIGEST_CLASS),
        "digest_class_excluded": sum(1 for r in excluded if r["class"] == DIGEST_CLASS),
        "sibling_excluded": sum(1 for r in excluded if r["class"] == "sibling-conclusion"),
        "parts": [
            {
                "root": p.get("root"),
                "exists": p.get("exists"),
                "admitted_count": p.get("admitted_count"),
                "excluded_count": p.get("excluded_count"),
            }
            for p in parts
        ],
    }


def production_inventory(repo: Path) -> dict:
    parts = [scan(repo, root) for root in PHASE_ROOTS]
    merged = merge_inventories(parts)
    present = [p["root"] for p in merged["parts"] if p["exists"]]
    merged["production_status"] = "PRESENT" if present else "ABSENT"
    merged["production_roots_present"] = present
    return merged


def control_inventory(repo: Path) -> dict:
    return scan(repo, FIXTURE_CORPUS)
