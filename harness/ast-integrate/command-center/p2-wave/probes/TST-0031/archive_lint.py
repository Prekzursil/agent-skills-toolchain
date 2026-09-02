#!/usr/bin/env python3
"""Lint: ban `git archive` as a blob/hash/format source (TST-0031).

Use-versus-mention (paid for repeatedly on this estate):
  * Markdown: only fenced code is a prescription; prose naming the trap is a mention.
  * Shell/CI: comment lines and trailing comments are mentions; packaging
    (`--format=tar` / `-o *.tar.gz`) is the legitimate whole-tree use.
  * Python: a string counts only when it reaches a subprocess argv.
  * Explicit negation (never/not/unlike git archive) is a mention.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

INVOKE = re.compile(r"(?<![\w`'\"])git\s+(?:-C\s+\S+\s+)?archive\b")
PACKAGING = re.compile(
    r"--format\s*=\s*tar|--output=|-o\s+\S+\.(tar|tgz|zip)\b",
    re.I,
)
COMMENT_START = re.compile(r"^\s*(#|//|rem\b|::)", re.I)
TRAILING_COMMENT = re.compile(r"\s+(#|//)\s.*$")
NEGATED = re.compile(
    r"\b(not|never|no|avoid|unlike|rather than|instead of|banned|do not)\b"
    r".{0,40}git\s+archive",
    re.I,
)
SHELLISH = {".ps1", ".sh", ".bash", ".bat", ".cmd", ".yml", ".yaml"}
SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
}


def _code_body(line: str) -> str:
    return TRAILING_COMMENT.sub("", line)


def _is_invocation(line: str) -> bool:
    code = _code_body(line)
    if not INVOKE.search(code):
        return False
    if NEGATED.search(code) or NEGATED.search(line):
        return False
    return True


def _md_fenced_lines(text: str) -> set[int]:
    out: set[int] = set()
    infence = False
    for i, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            infence = not infence
            continue
        if infence:
            out.add(i)
    return out


def _py_invocation_lines(src: str) -> set[int]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = getattr(fn, "attr", None) or getattr(fn, "id", None)
        if name not in {
            "run",
            "check_output",
            "Popen",
            "call",
            "check_call",
            "system",
        }:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                if sub.value.strip() == "archive" or INVOKE.search(sub.value):
                    out.add(getattr(sub, "lineno", node.lineno))
    return out


def classify_line(path: Path, lineno: int, line: str, *, py_lines: set[int], md_fenced: set[int]) -> str | None:
    """Return 'provenance' | 'packaging' | 'mention' | None (no git archive)."""
    suffix = path.suffix.lower()
    if suffix == ".py":
        if "git archive" not in line and not re.search(r"\barchive\b", line):
            return None
        if lineno in py_lines:
            return "packaging" if PACKAGING.search(_code_body(line)) else "provenance"
        if INVOKE.search(line) or "git archive" in line:
            return "mention"
        return None
    if suffix == ".md":
        if not INVOKE.search(line):
            return None
        if lineno in md_fenced and _is_invocation(line) and not COMMENT_START.match(line):
            return "packaging" if PACKAGING.search(_code_body(line)) else "provenance"
        return "mention"
    if suffix in SHELLISH:
        if not INVOKE.search(line):
            return None
        if COMMENT_START.match(line) or not _is_invocation(line):
            return "mention"
        return "packaging" if PACKAGING.search(_code_body(line)) else "provenance"
    if INVOKE.search(line):
        return "mention"
    return None


def scan_text(rel: str, text: str) -> list[dict[str, Any]]:
    path = Path(rel)
    py_lines = _py_invocation_lines(text) if path.suffix.lower() == ".py" else set()
    md_fenced = _md_fenced_lines(text) if path.suffix.lower() == ".md" else set()
    findings: list[dict[str, Any]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        kind = classify_line(path, i, line, py_lines=py_lines, md_fenced=md_fenced)
        if kind is None:
            continue
        findings.append(
            {
                "path": rel.replace("\\", "/"),
                "line": i,
                "kind": kind,
                "text": line.rstrip()[:240],
            }
        )
    return findings


def scan_path(path: Path, *, repo: Path | None = None) -> list[dict[str, Any]]:
    rel = path.name
    if repo is not None:
        try:
            rel = path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            rel = str(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_text(rel, text)


def scan_tree(root: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in {".md", ".py", ".sh", ".bash", ".yml", ".yaml", ".ps1"}:
            continue
        findings.extend(scan_path(path, repo=root))
    provenance = [f for f in findings if f["kind"] == "provenance"]
    return {
        "root": str(root),
        "findings": findings,
        "provenance": provenance,
        "provenance_count": len(provenance),
        "clean": len(provenance) == 0,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="TST-0031 git-archive-as-blob-source lint")
    p.add_argument("paths", nargs="+")
    ns = p.parse_args(argv)
    all_prov: list[dict[str, Any]] = []
    for raw in ns.paths:
        path = Path(raw)
        if path.is_dir():
            doc = scan_tree(path)
            all_prov.extend(doc["provenance"])
        elif path.is_file():
            all_prov.extend(
                [f for f in scan_path(path) if f["kind"] == "provenance"]
            )
    print(json.dumps({"provenance_count": len(all_prov), "provenance": all_prov}, indent=1))
    return 1 if all_prov else 0


if __name__ == "__main__":
    raise SystemExit(main())
