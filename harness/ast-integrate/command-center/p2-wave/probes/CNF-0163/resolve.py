"""Resolve file:line evidence anchors at the CITED revision via git cat-file.

Blob bytes come only from `git cat-file -p <rev>:<path>`. The archive porcelain
is forbidden: on this estate it has been measured to return CRLF worktree bytes
and would manufacture drift. Line endings are normalised before comparison so
CRLF cannot manufacture drift. Line drift is a distinct verdict from a missing
or worktree-only anchor.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

VERDICT_RESOLVED = "resolved"
VERDICT_DRIFTED = "drifted"
VERDICT_MISSING = "missing-at-revision"
VERDICT_WORKTREE = "worktree-only"
VERDICTS = (
    VERDICT_RESOLVED,
    VERDICT_DRIFTED,
    VERDICT_MISSING,
    VERDICT_WORKTREE,
)

BLOB_ARGV = ("git", "cat-file", "-p")


@dataclass
class Anchor:
    path: str
    line: int
    construct: Optional[str] = None
    revision: Optional[str] = None
    cited_by: list[str] = field(default_factory=list)
    id: str = ""

    def key(self) -> tuple:
        return (self.path, self.line, self.construct or "")


@dataclass
class Resolution:
    path: str
    line: int
    revision_cited: Optional[str]
    revision_used: Optional[str]
    construct: Optional[str]
    verdict: str
    blob_available: bool
    worktree_available: bool
    blob_line_count: Optional[int]
    worktree_line_count: Optional[int]
    drifted_to: Optional[int]
    blob_line_text: Optional[str]
    worktree_line_text: Optional[str]
    method: str
    cited_by: list[str]
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "line": self.line,
            "revision_cited": self.revision_cited,
            "revision_used": self.revision_used,
            "construct": self.construct,
            "verdict": self.verdict,
            "blob_available": self.blob_available,
            "worktree_available": self.worktree_available,
            "blob_line_count": self.blob_line_count,
            "worktree_line_count": self.worktree_line_count,
            "drifted_to": self.drifted_to,
            "blob_line_text": _clip(self.blob_line_text),
            "worktree_line_text": _clip(self.worktree_line_text),
            "method": self.method,
            "cited_by": list(self.cited_by),
            "note": self.note,
        }


def _clip(text: Optional[str], n: int = 160) -> Optional[str]:
    if text is None:
        return None
    text = text.replace("\r", "")
    return text if len(text) <= n else text[: n - 1] + "…"


def split_lines(data: bytes) -> list[str]:
    """EOL-agnostic split. CRLF, CR, and LF become the same logical lines."""
    text = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode(
        "utf-8", errors="replace"
    )
    if text.endswith("\n"):
        text = text[:-1]
    if text == "":
        return []
    return text.split("\n")


def git_available(repo: Path) -> bool:
    r = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        timeout=15,
    )
    return r.returncode == 0 and r.stdout.strip() == b"true"


def git_head(repo: Path) -> Optional[str]:
    r = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if r.returncode != 0:
        return None
    sha = (r.stdout or "").strip()
    return sha or None


def git_cat_file(repo: Path, rev: str, path: str) -> Optional[bytes]:
    """Return blob bytes. Never git archive."""
    spec = f"{rev}:{path}"
    r = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-p", spec],
        capture_output=True,
        timeout=30,
    )
    if r.returncode != 0:
        return None
    return r.stdout


def _line_at(lines: Optional[list[str]], n: int) -> Optional[str]:
    if lines is None or n < 1 or n > len(lines):
        return None
    return lines[n - 1]


def _has_construct(line: Optional[str], construct: Optional[str]) -> bool:
    if line is None:
        return False
    if not construct:
        return True
    return _norm(construct) in _norm(line)


def _norm(s: str) -> str:
    return s.replace("\r", "")


def _find_construct(lines: Optional[list[str]], construct: Optional[str]) -> list[int]:
    if not lines or not construct:
        return []
    needle = _norm(construct)
    return [i for i, ln in enumerate(lines, 1) if needle in _norm(ln)]


def classify(
    repo: Path,
    path: str,
    line: int,
    construct: Optional[str] = None,
    revision: Optional[str] = None,
    cited_by: Optional[list[str]] = None,
) -> Resolution:
    method = "git cat-file -p <rev>:<path>"
    cited_by = list(cited_by or [])
    construct = construct if construct else None
    if construct is not None:
        construct = construct.replace("\r\n", "\n")
        # Keep a possible trailing CR so the EOL control can prove we strip it.
    revision_cited = revision
    revision_used = revision
    if revision_used is None and git_available(repo):
        revision_used = git_head(repo)

    blob: Optional[bytes] = None
    if revision_used:
        blob = git_cat_file(repo, revision_used, path)
    blob_lines = split_lines(blob) if blob is not None else None

    wt_path = repo / path
    wt = wt_path.read_bytes() if wt_path.is_file() else None
    wt_lines = split_lines(wt) if wt is not None else None

    blob_text = _line_at(blob_lines, line)
    wt_text = _line_at(wt_lines, line)
    blob_hit = _has_construct(blob_text, construct)
    wt_hit = _has_construct(wt_text, construct)
    blob_elsewhere = _find_construct(blob_lines, construct) if construct else []
    wt_elsewhere = _find_construct(wt_lines, construct) if construct else []

    note = ""
    drifted_to: Optional[int] = None

    if blob_hit:
        verdict = VERDICT_RESOLVED
        note = "cited line exists in blob and contains the construct"
    elif blob_elsewhere:
        drifted_to = blob_elsewhere[0]
        verdict = VERDICT_DRIFTED
        note = (
            f"construct present in blob at line {drifted_to}, not at cited line {line}"
        )
    elif wt_hit or (not construct and wt_text is not None):
        verdict = VERDICT_WORKTREE
        if blob is None:
            note = (
                "anchor resolves in the worktree only; blob unavailable at cited "
                "revision (missing git history, missing path, or uncited rev)"
            )
        else:
            note = (
                "cited line/construct is in the worktree but not in the blob at "
                "the cited revision"
            )
    elif wt_elsewhere and blob is None:
        verdict = VERDICT_MISSING
        note = (
            "construct is in the worktree at a different line; no blob at the "
            "cited revision so this is not classified as blob-line-drift"
        )
    else:
        verdict = VERDICT_MISSING
        if blob is None:
            note = "path/line/construct absent at cited revision and not on the cited worktree line"
        else:
            note = "path exists in blob but cited line is past EOF or construct is absent"

    return Resolution(
        path=path,
        line=line,
        revision_cited=revision_cited,
        revision_used=revision_used,
        construct=construct,
        verdict=verdict,
        blob_available=blob is not None,
        worktree_available=wt is not None,
        blob_line_count=len(blob_lines) if blob_lines is not None else None,
        worktree_line_count=len(wt_lines) if wt_lines is not None else None,
        drifted_to=drifted_to,
        blob_line_text=blob_text,
        worktree_line_text=wt_text,
        method=method,
        cited_by=cited_by,
        note=note,
    )
