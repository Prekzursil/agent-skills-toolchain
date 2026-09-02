#!/usr/bin/env python3
"""Planted two-tree control corpus. Not a substitute for the live trees.

Directory listings + content hashes are the evidence. Files are LF-only so
hashlib and sha256sum agree.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
CTRL_A = HERE / "fixtures" / "platform-redesign-control"
CTRL_B = HERE / "fixtures" / "harness-restore-control"

IDENTICAL = b"IDENTICAL-BYTES-RES-0127\n"
DIFF_A = b"TREE-A-DIFFERENT-RES-0127\n"
DIFF_B = b"TREE-B-DIFFERENT-RES-0127\n"
ONLY_A = b"ONLY-IN-PLATFORM-RES-0127\n"
ONLY_B = b"ONLY-IN-HARNESS-RES-0127\n"
RENAMED = b"RENAMED-SAME-BYTES-RES-0127\n"
SHARD = b"RESEARCH-SHARD-ONLY-A-RES-0127\n"

EXPECTED = {
    "only_in_a": [
        "only-in-platform.md",
        "renamed-same-bytes-a.md",
        "research/shard.md",
    ],
    "only_in_b": [
        "only-in-harness.md",
        "renamed-same-bytes-b.md",
    ],
    "in_both_identical": ["control-identical.md"],
    "in_both_different": ["control-different.md"],
}


def _write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def ensure_control_trees() -> tuple[Path, Path]:
    _write(CTRL_A / "control-identical.md", IDENTICAL)
    _write(CTRL_B / "control-identical.md", IDENTICAL)
    _write(CTRL_A / "control-different.md", DIFF_A)
    _write(CTRL_B / "control-different.md", DIFF_B)
    _write(CTRL_A / "only-in-platform.md", ONLY_A)
    _write(CTRL_B / "only-in-harness.md", ONLY_B)
    _write(CTRL_A / "renamed-same-bytes-a.md", RENAMED)
    _write(CTRL_B / "renamed-same-bytes-b.md", RENAMED)
    _write(CTRL_A / "research" / "shard.md", SHARD)
    # sentinel must not exist in either tree
    for root in (CTRL_A, CTRL_B):
        ghost = root / "ABSENT-SENTINEL-RES-0127.md"
        if ghost.exists():
            ghost.unlink()
    return CTRL_A, CTRL_B
