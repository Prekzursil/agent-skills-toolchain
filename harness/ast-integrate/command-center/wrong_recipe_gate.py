#!/usr/bin/env python3
"""Sentence-role gate for verification recipes that are wrong on this Windows box.

`git archive` returns CRLF worktree bytes here, not the LF blob. Prescriptive
uses of that recipe must fire. Documentary mentions that name the recipe in
order to forbid it must stay silent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

ARCHIVE = "git archive"
PRESCRIPTIVE = "PRESCRIPTIVE"
DOCUMENTARY = "DOCUMENTARY"
PACKAGING = "PACKAGING"

DEFAULT_RELATIVE = (
    "command-center/RELEASE-CHECKLIST.md",
    "command-center/PROGRAM-CHARTER.md",
    "command-center/BASELINE-SNAPSHOT.md",
)

# (text, expected_role) — independence: reviewer held-out text is NOT listed.
LABELLED_CONTROLS: tuple[tuple[str, str], ...] = (
    (
        "Verify formatting against the LF blob (git archive).",
        PRESCRIPTIVE,
    ),
    (
        "Before tagging, confirm ruff is clean against the LF blob (git archive).",
        PRESCRIPTIVE,
    ),
    (
        "Do not verify formatting against `git archive`. Use `git cat-file -p <rev>:<path>`.",
        DOCUMENTARY,
    ),
    (
        "DO NOT USE `git archive` FOR THIS — it returns the OPPOSITE of the blob on this box.",
        DOCUMENTARY,
    ),
    (
        "Not `git archive`: on this box it applies export-time EOL conversion.",
        DOCUMENTARY,
    ),
    (
        "Package a source tarball with git archive HEAD --format=tar for distribution.",
        PACKAGING,
    ),
)

_DOC_MARKERS = (
    "do not use",
    "do not verify",
    "don't use",
    "never use",
    "forbid",
    "forbids",
    "wrong on this box",
    "was wrong",
    "opposite of the blob",
    "not `git archive`",
    "not git archive",
    "not as an instruction",
    "not so anyone repeats",
    "quoted here because it is the defect",
    "names git archive only to forbid",
    "in order to forbid",
    "hands back",
    "postmortem",
    "measured defect",
    "export-time eol",
    "crlf",
)


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def classify_line(text: str) -> str | None:
    raw = text or ""
    low = _norm(raw)
    if ARCHIVE not in low:
        return None
    if any(m in low for m in _DOC_MARKERS):
        return DOCUMENTARY
    if "format=tar" in low or "tarball" in low or "distribution" in low:
        return PACKAGING
    if any(
        tok in low
        for tok in (
            "verify",
            "confirm",
            "check",
            "against the lf blob",
            "against the lf",
            "(git archive)",
        )
    ):
        return PRESCRIPTIVE
    return DOCUMENTARY


def scan_text(text: str, *, path: str = "") -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for i, line in enumerate((text or "").splitlines(), 1):
        role = classify_line(line)
        if role is None:
            continue
        hits.append(
            {
                "path": path,
                "line": i,
                "role": role,
                "text": line.strip(),
            }
        )
    return hits


def scan_path(path: Path | str, repo: Path | None = None) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.is_file():
        return []
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    rel = str(path)
    if repo is not None:
        try:
            rel = p.resolve().relative_to(Path(repo).resolve()).as_posix()
        except ValueError:
            rel = p.as_posix()
    return scan_text(text, path=rel.replace("\\", "/"))


def prescriptive(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [h for h in hits if h.get("role") == PRESCRIPTIVE]


def default_targets(repo: Path) -> list[Path]:
    out: list[Path] = []
    for rel in DEFAULT_RELATIVE:
        p = Path(repo) / rel
        if p.is_file():
            out.append(p)
    root = Path(repo) / "command-center"
    if root.is_dir():
        for p in sorted(root.glob("*.md")):
            if p not in out:
                out.append(p)
    return out


def self_test() -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for text, expected in LABELLED_CONTROLS:
        hits = scan_text(text, path="labelled-control")
        roles = [h["role"] for h in hits]
        if expected not in roles or (expected == PRESCRIPTIVE and DOCUMENTARY in roles and PRESCRIPTIVE not in roles):
            failures.append(
                {
                    "text": text,
                    "expected": expected,
                    "got": roles,
                }
            )
        elif expected == PRESCRIPTIVE and PRESCRIPTIVE not in roles:
            failures.append({"text": text, "expected": expected, "got": roles})
        elif expected != PRESCRIPTIVE and PRESCRIPTIVE in roles:
            failures.append({"text": text, "expected": expected, "got": roles})
        elif expected not in roles:
            failures.append({"text": text, "expected": expected, "got": roles})
    # Tighten: exact first-hit role must match.
    tight: list[dict[str, Any]] = []
    for text, expected in LABELLED_CONTROLS:
        hits = scan_text(text, path="labelled-control")
        got = hits[0]["role"] if hits else None
        if got != expected:
            tight.append({"text": text, "expected": expected, "got": got})
    return tight
