"""Completion-oracle / control-plane scanner (IMP-0192)."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Finding:
    path: str
    plane: str
    name: str
    kind: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "plane": self.plane,
            "name": self.name,
            "kind": self.kind,
        }


def _scan_source(text: str, rel: str) -> list[Finding]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    hits: list[Finding] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "judge":
            hits.append(
                Finding(rel, "completion_oracle", "judge", "function")
            )
    return hits


def scan_path(path: Path, repo: Path | None = None) -> list[Finding]:
    path = Path(path)
    rel = path.as_posix()
    if repo is not None:
        try:
            rel = path.resolve().relative_to(Path(repo).resolve()).as_posix()
        except ValueError:
            rel = path.as_posix()
    return _scan_source(path.read_text(encoding="utf-8"), rel)


def scan_library(repo: Path) -> dict[str, Any]:
    root = Path(repo) / "tools" / "agentrail" / "agentrail"
    findings: list[Finding] = []
    files = 0
    if root.is_dir():
        for path in sorted(root.rglob("*.py")):
            files += 1
            findings.extend(scan_path(path, repo))
    return {
        "files_scanned": files,
        "finding_count": len(findings),
        "findings": [f.as_dict() for f in findings],
        "by_plane": {},
    }


def scan_generated_artifacts(repo: Path) -> dict[str, Any]:
    return {
        "files_scanned": 0,
        "finding_count": 0,
        "findings": [],
    }
