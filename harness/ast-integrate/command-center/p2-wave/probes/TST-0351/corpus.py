"""Walk the program corpus of receipts, reports, and status documents."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

SKIP_PARTS = frozenset(
    {".git", "node_modules", "__pycache__", ".cursor", ".venv", ".tox"}
)
SCAN_SUFFIXES = frozenset({".json", ".md", ".txt", ".yml", ".yaml"})
CORPUS_DIRS = (
    "command-center/receipts",
    "command-center/confirmation",
    "command-center/synthesis",
    "command-center/audit",
    "command-center/reports",
)
CORPUS_GLOBS = (
    "command-center/*.md",
    "command-center/p2-wave/*.md",
    "command-center/STATUS.md",
)
SELF_SKIP = (
    "command-center/receipts/TST-0351.json",
    "command-center/p2-wave/probes/TST-0351/",
    "command-center/WORK-UNIT-CATALOG.json",
)
MAX_BYTES = 8 * 1024 * 1024


def _skip(rel: str) -> bool:
    posix = rel.replace("\\", "/")
    if posix in SELF_SKIP or posix.startswith("command-center/p2-wave/probes/TST-0351/"):
        return True
    if posix.endswith("WORK-UNIT-CATALOG.json"):
        return True
    parts = set(Path(posix).parts)
    return bool(parts & SKIP_PARTS)


def iter_corpus(repo: Path) -> Iterator[Path]:
    seen: set[str] = set()
    for rel in CORPUS_DIRS:
        root = repo / rel
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            try:
                key = path.resolve().relative_to(repo.resolve()).as_posix()
            except ValueError:
                continue
            if _skip(key) or key in seen:
                continue
            try:
                if path.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue
            seen.add(key)
            yield path
    for pattern in CORPUS_GLOBS:
        for path in repo.glob(pattern):
            if not path.is_file():
                continue
            try:
                key = path.resolve().relative_to(repo.resolve()).as_posix()
            except ValueError:
                continue
            if _skip(key) or key in seen:
                continue
            seen.add(key)
            yield path


def sweep(
    repo: Path,
    ledger: dict | None = None,
    registry: dict | None = None,
) -> dict:
    from extract import extract_paths
    from ledger import load_ledger, load_registry
    from resolve import classify_claims

    paths = list(iter_corpus(repo))
    claims = extract_paths(paths, repo)
    ledger = ledger if ledger is not None else load_ledger(repo)
    registry = registry if registry is not None else load_registry(repo)
    report = classify_claims(claims, ledger, registry)
    report["files_scanned"] = len(paths)
    report["ledger_meta"] = {
        "path": ledger.get("path"),
        "present": ledger.get("present"),
        "row_count": ledger.get("row_count"),
        "files": ledger.get("files"),
    }
    report["registry_meta"] = {
        "path": registry.get("path"),
        "present": registry.get("present"),
        "parseable": registry.get("parseable"),
    }
    return report
