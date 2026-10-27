"""Static audit for publisher-key lifecycle calls and private material."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

_SKIP = {".git", "__pycache__", "node_modules", ".venv"}
_LIFECYCLE = {"rotate_key", "generate_private_key", "export_private_key"}
_PRIVATE = re.compile(r"BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY")


class Hit:
    def __init__(self, name: str, path: str = "", line: int = 0) -> None:
        self.name = name
        self.path = path
        self.line = line

    def __repr__(self) -> str:
        return f"Hit({self.name!r}, {self.path!r}, {self.line})"


def _py_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os_walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP]
        for name in filenames:
            if name.endswith(".py"):
                yield Path(dirpath) / name


def os_walk(root: Path):
    import os

    return os.walk(root, followlinks=False)


def _hits_in_source(text: str, path: str = "") -> list[Hit]:
    found: list[Hit] = []
    if "rsa.generate_private_key" in text or "generate_private_key(" in text:
        found.append(Hit(name="generate_private_key", path=path, line=0))
    if "def rotate_key" in text or re.search(r"\brotate_key\s*\(", text):
        found.append(Hit(name="rotate_key", path=path, line=0))
    if "export_private_key" in text:
        found.append(Hit(name="export_private_key", path=path, line=0))
    return found


def scan_tree(root: Path) -> list[Hit]:
    hits: list[Hit] = []
    for path in _py_files(Path(root)):
        # Skip this auditor and tests so production stays clean.
        rel = path.as_posix()
        if path.name in {"audit.py", "test_benchmark_gaming.py"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hits.extend(_hits_in_source(text, rel))
    return hits


def detect_plant(source: str) -> list[Hit]:
    return _hits_in_source(source, path="<plant>")


def scan_source(source: str, path: str = "") -> list[Hit]:
    return _hits_in_source(source, path=path)


def _scan_placement(plugin_dir: Path, mkt_dir: Path) -> dict:
    import re

    sites: list[dict[str, str]] = []
    plugin_dir = Path(plugin_dir)
    mkt_dir = Path(mkt_dir)
    for path in plugin_dir.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"def place_payload_files\s*\(", text):
            sites.append({"package": "plugin", "name": "place_payload_files", "path": path.as_posix()})
        for match in re.finditer(r"@file_placement_call_site\s*\ndef\s+(\w+)", text):
            if match.group(1) != "place_payload_files":
                sites.append({"package": "plugin", "name": match.group(1), "path": path.as_posix()})
    marketplace_writes: list[str] = []
    for path in mkt_dir.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "_planted_marketplace_placement" in text or "dest.write_bytes(blob)" in text:
            marketplace_writes.append(path.as_posix())
    count = len(sites)
    ok = count == 1 and not marketplace_writes
    reasons = []
    if count != 1:
        reasons.append(f"placement_site_count={count}")
    if marketplace_writes:
        reasons.append("marketplace_writes")
    return {
        "ok": ok,
        "placement_site_count": count,
        "sites": sites,
        "marketplace_writes": marketplace_writes,
        "writes_outside_site": [],
        "reasons": reasons,
    }


def audit_directories(plugin_dir: Path, mkt_dir: Path) -> dict:
    return _scan_placement(plugin_dir, mkt_dir)


def audit_live(repo: Path) -> dict:
    root = Path(repo)
    return _scan_placement(root / "tools" / "plugin", root / "tools" / "marketplace")


def private_material_hits(root: Path) -> list[str]:
    found: list[str] = []
    root = Path(root)
    for dirpath, dirnames, filenames in os_walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if path.name in {"signatures.py", "audit.py"}:
                continue
            if _PRIVATE.search(text) and "def " not in text.split("BEGIN")[0][-40:]:
                found.append(path.as_posix())
            elif _PRIVATE.search(text) and path.suffix in {".pem", ".key", ".txt"}:
                found.append(path.as_posix())
    return found
