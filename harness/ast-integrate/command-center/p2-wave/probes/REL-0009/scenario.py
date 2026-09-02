#!/usr/bin/env python3
"""Fixture builders for REL-0009 archive-gate controls."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "release"))

from archive_gate import append_zero_blob, pack_tree  # noqa: E402

CLEAN_SRC = HERE / "fixtures" / "clean"
GITIGNORED_NAME = "untracked-packed.bin"
GITIGNORED_MARKER = "REL-0009-GITIGNORED-PACKED-MUST-APPEAR-IN-ARCHIVE\n"
BLOB_ARCNAME = "docs/unrelated-200m.bin"
BLOB_SIZE = 200 * 1024 * 1024
DOTGIT_HEAD = "ref: refs/heads/main\n"
DOTGIT_CONFIG = "[core]\n\trepositoryformatversion = 0\n"


def copy_clean(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(CLEAN_SRC, dest)
    return dest


def pack_clean(dest_zip: Path, work: Path) -> Path:
    src = copy_clean(work / "clean-src")
    return pack_tree(src, dest_zip)


def pack_dotgit(dest_zip: Path, work: Path) -> Path:
    src = copy_clean(work / "dotgit-src")
    git = src / ".git"
    git.mkdir(parents=True, exist_ok=True)
    (git / "HEAD").write_text(DOTGIT_HEAD, encoding="utf-8")
    (git / "config").write_text(DOTGIT_CONFIG, encoding="utf-8")
    return pack_tree(src, dest_zip)


def pack_blob(dest_zip: Path, work: Path) -> Path:
    """Clean allowlisted payload plus a 200 MiB unrelated blob on an allowlisted path.

    The blob matches docs/** so the failure is the byte ceiling, not the allowlist,
    and the ceiling report names docs/unrelated-200m.bin.
    """
    pack_clean(dest_zip, work)
    append_zero_blob(dest_zip, BLOB_ARCNAME, BLOB_SIZE)
    return dest_zip


def pack_gitignored(dest_zip: Path, work: Path) -> tuple[Path, Path]:
    """Working tree with a gitignored file; sloppy packer still ships it.

    Returns (archive, tree_root). The gate must see the ignored file in the
    archive listing. A gitignore-respecting tree walk of tree_root must not.
    """
    src = copy_clean(work / "gitignored-src")
    (src / ".gitignore").write_text(GITIGNORED_NAME + "\n", encoding="utf-8")
    (src / GITIGNORED_NAME).write_text(GITIGNORED_MARKER, encoding="utf-8")
    pack_tree(src, dest_zip)
    return dest_zip, src


def gitignore_walk(root: Path) -> list[str]:
    """Minimal gitignore walker used only as the negative (tree) control.

    The gate never calls this. Patterns are basename or path globs from
    root/.gitignore, comments and blanks skipped.
    """
    gi = root / ".gitignore"
    patterns = []
    if gi.is_file():
        for line in gi.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line.replace("\\", "/"))
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == ".gitignore":
            hits.append(rel)
            continue
        skipped = False
        for pat in patterns:
            if rel == pat or path.name == pat or rel.endswith("/" + pat):
                skipped = True
                break
        if not skipped:
            hits.append(rel)
    hits.sort()
    return hits
