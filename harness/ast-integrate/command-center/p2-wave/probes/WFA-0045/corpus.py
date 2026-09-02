#!/usr/bin/env python3
"""Resolve the 10-file saved-workflow corpus: live home first, else fixtures."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "saved"
REPO = HERE.parents[3]

LIVE_CANDIDATES = [
    Path.home() / ".claude" / "workflows",
    Path.home() / ".claude" / "workflows",
    Path.home() / ".claude" / "workflows",
    REPO / "workflows",
]

REQUIRED_NAMES = {"plan-gate.mjs", "design-gate.mjs"}


def _js_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    files = [
        p
        for p in sorted(directory.iterdir())
        if p.is_file() and p.suffix in {".js", ".mjs"} and not p.name.startswith(".")
    ]
    return files


def live_corpus() -> list[Path] | None:
    for directory in LIVE_CANDIDATES:
        files = _js_files(directory)
        names = {p.name for p in files}
        if len(files) >= 10 and REQUIRED_NAMES <= names:
            picked = []
            by_name = {p.name: p for p in files}
            for req in sorted(REQUIRED_NAMES):
                picked.append(by_name[req])
            rest = [p for p in files if p.name not in REQUIRED_NAMES]
            picked.extend(rest)
            return picked[:10]
        if len(files) == 10:
            return files
    return None


def fixture_corpus() -> list[Path]:
    files = _js_files(FIXTURES)
    if len(files) != 10:
        raise SystemExit(f"fixture corpus must be 10 files, got {len(files)} in {FIXTURES}")
    names = {p.name for p in files}
    missing = REQUIRED_NAMES - names
    if missing:
        raise SystemExit(f"fixture corpus missing required names: {sorted(missing)}")
    return files


def load_corpus() -> tuple[list[Path], str]:
    live = live_corpus()
    if live:
        return live, "live"
    return fixture_corpus(), "fixture-dialect-corpus"
