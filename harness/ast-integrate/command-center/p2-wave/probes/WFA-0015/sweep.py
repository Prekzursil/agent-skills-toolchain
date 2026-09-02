#!/usr/bin/env python3
"""Content-hash worktree sweep. Preservation is bytes, never ancestry.

PRESERVED is emitted only when a byte-identical copy is found in the
origin/* blob index or the PR-MERGED blob index AND that location is
recorded on the row. Commit ancestry (ahead/behind, squash-merge) is
never consulted and is never a delete authorisation.

This module has no git write, worktree-remove, branch-delete, prune, or
gc operations.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

PRESERVED = "PRESERVED"
UNIQUE = "UNIQUE-NOWHERE-ELSE"
NOT_WORKFLOW = "NOT-WORKFLOW"

WORKFLOW_PREFIXES = (
    ".github/workflows/",
    "skills/",
    "rules/",
    "plugins/",
    "hooks/",
    "workflows/",
    ".claude/workflows/",
    ".agents/skills/",
    "command-center/wfa/",
)
WORKFLOW_NAMES = {
    "SKILL.md",
    "AGENTS.md",
    "plugin.json",
    "marketplace.json",
}
WORKFLOW_SUFFIXES = (
    ".yml",
    ".yaml",
    ".skill.md",
)
FUSION_MARKERS = (
    "fusion",
    "orchestration stage",
    "council-stage",
    "multi-stage workflow",
    "gate pipeline",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def posix_rel(path: str) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def is_workflow_bearing(relpath: str, data: bytes | None = None) -> bool:
    rel = posix_rel(relpath)
    name = rel.rsplit("/", 1)[-1]
    if name in WORKFLOW_NAMES:
        return True
    lower = rel.lower()
    if any(lower.startswith(p) for p in WORKFLOW_PREFIXES):
        return True
    if name.endswith(WORKFLOW_SUFFIXES) and (
        "/workflow" in lower or lower.startswith("workflow") or "skills/" in lower
    ):
        return True
    if data:
        text = data.decode("utf-8", errors="replace").lower()
        if any(m in text for m in FUSION_MARKERS):
            return True
    return False


@dataclass
class BlobIndex:
    """Maps sha256 -> locations. Locations are origin/* or pr-merged refs."""

    by_sha: dict[str, list[str]] = field(default_factory=dict)

    def add(self, digest: str, location: str) -> None:
        bucket = self.by_sha.setdefault(digest, [])
        if location not in bucket:
            bucket.append(location)

    def locations(self, digest: str) -> list[str]:
        return list(self.by_sha.get(digest) or [])

    def ingest_tree(self, root: Path, prefix: str) -> int:
        n = 0
        if not root.is_dir():
            return 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
            for name in filenames:
                path = Path(dirpath) / name
                rel = posix_rel(str(path.relative_to(root)))
                data = path.read_bytes()
                self.add(sha256_bytes(data), f"{prefix}:{rel}")
                n += 1
        return n


@dataclass
class FileRow:
    worktree: str
    relpath: str
    sha256: str
    size: int
    dirty: bool
    workflow_bearing: bool
    classification: str
    preserved_at: list[str]
    sibling_hits: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "worktree": self.worktree,
            "relpath": self.relpath,
            "sha256": self.sha256,
            "size": self.size,
            "dirty": self.dirty,
            "workflow_bearing": self.workflow_bearing,
            "classification": self.classification,
            "preserved_at": list(self.preserved_at),
            "sibling_hits": list(self.sibling_hits),
        }


def classify_sha(digest: str, index: BlobIndex) -> tuple[str, list[str]]:
    locs = index.locations(digest)
    if locs:
        return PRESERVED, locs
    return UNIQUE, []


def iter_files(root: Path) -> Iterable[tuple[str, bytes]]:
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
        for name in filenames:
            path = Path(dirpath) / name
            rel = posix_rel(str(path.relative_to(root)))
            yield rel, path.read_bytes()


def sibling_index(trees: dict[str, Path], exclude: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, root in trees.items():
        if name == exclude:
            continue
        for rel, data in iter_files(root):
            digest = sha256_bytes(data)
            out.setdefault(digest, []).append(f"worktree:{name}:{rel}")
    return out


def sweep_worktrees(
    trees: dict[str, Path],
    origin_index: BlobIndex,
    dirty_paths: dict[str, set[str]] | None = None,
) -> list[FileRow]:
    """Classify every file in every worktree. Does not mutate trees."""
    rows: list[FileRow] = []
    dirty_paths = dirty_paths or {}
    for wt, root in sorted(trees.items()):
        sib = sibling_index(trees, wt)
        marked_dirty = dirty_paths.get(wt) or set()
        for rel, data in iter_files(root):
            digest = sha256_bytes(data)
            wf = is_workflow_bearing(rel, data)
            if wf:
                klass, locs = classify_sha(digest, origin_index)
            else:
                klass, locs = NOT_WORKFLOW, []
                if origin_index.locations(digest):
                    locs = origin_index.locations(digest)
            rows.append(
                FileRow(
                    worktree=wt,
                    relpath=rel,
                    sha256=digest,
                    size=len(data.replace(b"\r\n", b"\n")),
                    dirty=rel in marked_dirty,
                    workflow_bearing=wf,
                    classification=klass,
                    preserved_at=locs if klass == PRESERVED else [],
                    sibling_hits=list(sib.get(digest) or []),
                )
            )
    return rows


def assert_preserved_invariant(rows: Iterable[FileRow]) -> None:
    for row in rows:
        if row.classification == PRESERVED and not row.preserved_at:
            raise AssertionError(
                f"PRESERVED without location: {row.worktree}:{row.relpath}"
            )
        if row.preserved_at and row.classification != PRESERVED:
            if row.classification == NOT_WORKFLOW:
                continue
            raise AssertionError(
                f"locations recorded but class is {row.classification}: "
                f"{row.worktree}:{row.relpath}"
            )


def salvage_verdict(wt: str, rows: Iterable[FileRow]) -> dict:
    wf = [r for r in rows if r.worktree == wt and r.workflow_bearing]
    unique = [r for r in wf if r.classification == UNIQUE]
    preserved = [r for r in wf if r.classification == PRESERVED]
    if unique:
        verdict = "SALVAGEABLE-UNIQUE-WORKFLOW"
        reason = (
            f"{len(unique)} workflow-bearing file(s) have no byte-identical copy "
            "in origin/* or PR-MERGED; content exists nowhere else on the B surface."
        )
    elif preserved:
        verdict = "CONTENT-PRESERVED-ELSEWHERE"
        reason = (
            "every workflow-bearing file has a recorded origin/* or PR-MERGED "
            "byte-identical location; still not a delete authorisation"
        )
    elif wf:
        verdict = "WORKFLOW-PRESENT-UNCLASSIFIED"
        reason = "workflow files present but neither PRESERVED nor UNIQUE"
    else:
        verdict = "NO-WORKFLOW-BEARING-FILES"
        reason = "no workflow-bearing files in this tree"
    return {
        "worktree": wt,
        "verdict": verdict,
        "workflow_file_count": len(wf),
        "unique_count": len(unique),
        "preserved_count": len(preserved),
        "unique_relpaths": [r.relpath for r in unique],
        "reason": reason,
        "delete_recommended": False,
    }
