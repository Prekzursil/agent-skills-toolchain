"""Search product trees for a live measure-fingerprint lock.

Catalog prose and this probe directory are not a product loop. Hits in
tools/ or platform/ executable code would be.
"""
from __future__ import annotations

import re
from pathlib import Path

NEEDLES = (
    re.compile(r"measure[_-]fingerprint", re.I),
    re.compile(r"pre[-_]change[-_]measure", re.I),
    re.compile(r"fingerprint[_-]invariance", re.I),
    re.compile(r"self-improvement-validation"),
    re.compile(r"self_improvement_loop"),
)

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "node_modules",
    "ADV-0088",
}
SKIP_FILE_NAMES = {
    "WORK-UNIT-CATALOG.json",
    "P2-CLOUD-LEFTOVER_2026-08-24.json",
}
TEXT_SUFFIXES = {".py", ".json", ".md", ".yml", ".yaml"}
MAX_BYTES = 1_000_000


def _iter_files(root: Path):
    if not root.is_dir():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.name in SKIP_FILE_NAMES:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
        except OSError:
            continue
        yield path


def census(repo: Path) -> dict:
    roots = [
        repo / "tools",
        repo / "platform",
        repo / "command-center" / "phase3",
        repo / "command-center" / "receipts",
        repo / "command-center" / "schema",
    ]
    hits: list[dict] = []
    scanned = 0
    for root in roots:
        for path in _iter_files(root):
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            matched = [n.pattern for n in NEEDLES if n.search(text)]
            if matched:
                rel = path.relative_to(repo).as_posix()
                hits.append({"path": rel, "needles": matched})
    executable = [
        h
        for h in hits
        if h["path"].endswith(".py") and "/probes/" not in h["path"]
    ]
    return {
        "scanned_files": scanned,
        "roots": [r.relative_to(repo).as_posix() for r in roots],
        "hits": hits,
        "executable_lock_hits": executable,
        "product_fingerprint_lock_present": len(executable) > 0,
        "user_prompts_present": (repo / "_USER-PROMPTS.md").is_file(),
        "imp0255_receipt_present": (repo / "command-center/receipts/IMP-0255.json").is_file(),
        "tst0236_receipt_present": (repo / "command-center/receipts/TST-0236.json").is_file(),
    }
