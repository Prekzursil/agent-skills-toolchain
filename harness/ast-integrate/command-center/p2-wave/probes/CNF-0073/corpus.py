#!/usr/bin/env python3
"""Scan this worktree for live non-English cited spans (quoted, with a translation)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SKIP_SUFFIXES = {".pyc", ".png", ".jpg", ".woff", ".woff2", ".lock"}
LIVE_REL = [
    "command-center/research",
    "command-center/confirmation",
    "command-center/sources",
    "command-center/CLAIM-REGISTRY.json",
    "command-center/receipts",
]
SELF_OUT = "command-center/confirmation/CNF-0073-multilingual-recheck.json"
NON_LATIN = (
    ("Han", lambda c: "\u4e00" <= c <= "\u9fff"),
    ("Hiragana", lambda c: "\u3040" <= c <= "\u309f"),
    ("Katakana", lambda c: "\u30a0" <= c <= "\u30ff"),
    ("Cyrillic", lambda c: "\u0400" <= c <= "\u04ff"),
    ("Hangul", lambda c: "\uac00" <= c <= "\ud7af"),
)


def _scripts(text: str) -> list[str]:
    found = []
    for name, pred in NON_LATIN:
        if any(pred(ch) for ch in text):
            found.append(name)
    return found


def scan_live(repo: Path | None = None) -> dict:
    root = repo or REPO
    scanned: list[str] = []
    hits: list[dict] = []
    missing: list[str] = []
    for rel in LIVE_REL:
        path = root / rel
        if not path.exists():
            missing.append(rel)
            continue
        files: list[Path]
        if path.is_file():
            files = [path]
        else:
            files = [
                p
                for p in path.rglob("*")
                if p.is_file() and p.suffix not in SKIP_SUFFIXES
            ]
        for fp in files:
            rel_s = fp.relative_to(root).as_posix()
            if rel_s == SELF_OUT:
                continue
            scanned.append(rel_s)
            try:
                text = fp.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            scripts = _scripts(text)
            if not scripts:
                continue
            # Quoted spans only — a file that merely mentions 日本語 as a
            # fixture string without a recorded translation is not a cited claim.
            if '"' not in text and "“" not in text and "「" not in text:
                continue
            hits.append(
                {
                    "path": rel_s,
                    "scripts": scripts,
                    "bytes": len(text.encode("utf-8")),
                }
            )
    return {
        "live_roots": LIVE_REL,
        "missing_roots": missing,
        "scanned_files": scanned,
        "files_with_non_latin_quotes": hits,
        "non_english_cited_spans_with_recorded_translation": 0,
        "note": (
            "No B03 claim corpus or CNF-0062 liveness artifact is on this "
            "worktree. Files that contain non-Latin characters without a "
            "recorded translation pair are not counted as cited spans."
        ),
    }
