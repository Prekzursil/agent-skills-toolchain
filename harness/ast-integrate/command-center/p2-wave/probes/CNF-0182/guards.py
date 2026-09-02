"""Secret scan and portability guards. Never print credential values."""
from __future__ import annotations

import re
from pathlib import Path

# Patterns match credential *values*, not the words "token"/"cookie" in prose.
SECRET_RES = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{24,}"),
    re.compile(r"(?i)set-cookie\s*:"),
]

PROFILE_RE = re.compile(
    r"(/Users/|/home/[^/\s\"']+|/root/|C:\\\\Users\\\\|[A-Za-z]:\\\\Users\\\\)",
    re.IGNORECASE,
)
ABS_WORKTREE_RE = re.compile(r"/opt/p2/")


def scan_text(text: str) -> list[str]:
    hits = []
    for cre in SECRET_RES:
        if cre.search(text):
            hits.append(cre.pattern)
    return hits


def scan_tree(root: Path) -> list[dict]:
    findings = []
    if not root.exists():
        return [{"path": str(root), "reason": "missing"}]
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in {".pyc", ".png", ".jpg"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pat in scan_text(text):
            findings.append({"path": path.as_posix(), "pattern": pat})
    return findings


def portability_hits(root: Path) -> list[dict]:
    hits = []
    if not root.exists():
        return [{"path": str(root), "reason": "missing"}]
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if PROFILE_RE.search(text) or ABS_WORKTREE_RE.search(text):
            hits.append({"path": path.as_posix(), "kind": "absolute-or-profile"})
    return hits
