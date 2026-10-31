"""Static scan for banned wall-clock and PID constructs in saved workflows."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

WALL = (
    (re.compile(r"Date\.now\s*\("), "Date.now()"),
    (re.compile(r"new\s+Date\s*\("), "new Date("),
    (re.compile(r"time\.time_ns\s*\("), "time.time_ns()"),
    (re.compile(r"time\.time\s*\("), "time.time()"),
    (re.compile(r"datetime\.utcnow\s*\("), "datetime.utcnow()"),
    (re.compile(r"datetime\.now\s*\("), "datetime.now()"),
)
PID = (
    (re.compile(r"os\.getpid\s*\("), "os.getpid()"),
    (re.compile(r"process\.pid"), "process.pid"),
    (re.compile(r"(?<![A-Za-z0-9_])getpid\s*\("), "getpid()"),
)


def _rel(path: Path, repo: Path | None) -> str:
    if repo is not None:
        try:
            return path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def scan_text(text: str, path: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for i, line in enumerate(text.splitlines(), 1):
        for rx, needle in WALL:
            if rx.search(line):
                hits.append(
                    {
                        "kind": "wall-clock",
                        "path": path,
                        "line": i,
                        "needle": needle,
                    }
                )
        for rx, needle in PID:
            if rx.search(line):
                hits.append(
                    {
                        "kind": "pid",
                        "path": path,
                        "line": i,
                        "needle": needle,
                    }
                )
    return hits


def scan_file(path: Path, repo: Path | None = None) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.is_file():
        return []
    text = target.read_text(encoding="utf-8", errors="replace")
    return scan_text(text, _rel(target, repo))


def scan_paths(paths: list[Path], repo: Path | None = None) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for path in paths:
        hits.extend(scan_file(Path(path), repo=repo))
    return hits
