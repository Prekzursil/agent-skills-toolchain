"""Start/end tree hasher that labels a capture FROZEN or SAMPLED.

A working-tree snapshot taken while sibling agents are mutating the tree is a
timestamped SAMPLE, not a baseline. This tool hashes the tree at start and at
end. Equal hashes earn FROZEN and may be promoted via as_baseline(). Unequal
hashes earn SAMPLED, enumerate the changed paths, and as_baseline raises
BaselineRefused so a mutated capture cannot be called a baseline.

mid_hook(root) runs BETWEEN the two hashes so a probe can plant a rewrite.
include_relpaths, when set, restricts the walk to those POSIX relative paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

LABEL_FROZEN = "FROZEN"
LABEL_SAMPLED = "SAMPLED"
ANCHOR_FROZEN = "SHA-ANCHORED"
ANCHOR_SAMPLED = "SAMPLED-AT-TIME"
REFUSED_CODE = "SAMPLED-NOT-BASELINE"
EXCLUDE_DIRS = frozenset(
    {"__pycache__", ".git", ".pytest_cache", ".ruff_cache", "node_modules"}
)


class BaselineRefused(Exception):
    """Raised when as_baseline is asked to promote a SAMPLED capture."""

    def __init__(
        self,
        message: str,
        *,
        code: str = REFUSED_CODE,
        reason: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.reason = reason or message
        self.result = result


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _payload(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def _file_record(path: Path) -> dict[str, Any]:
    raw = _payload(path)
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _relpaths(root: Path, include_relpaths: Iterable[str] | None) -> list[str]:
    if include_relpaths is not None:
        found: list[str] = []
        for rel in sorted({str(p).replace("\\", "/") for p in include_relpaths}):
            candidate = root / rel
            if candidate.is_file() and not candidate.is_symlink():
                found.append(rel)
            elif candidate.is_file():
                found.append(rel)
        return found
    found = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for name in sorted(filenames):
            full = Path(dirpath) / name
            if not full.is_file():
                continue
            found.append(full.relative_to(root).as_posix())
    return found


def _inventory(root: Path, include_relpaths: Iterable[str] | None) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for rel in _relpaths(root, include_relpaths):
        files[rel] = _file_record(root / rel)
    return files


def _tree_hash(files: dict[str, dict[str, Any]]) -> str:
    hasher = hashlib.sha256()
    for rel in sorted(files):
        rec = files[rel]
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(rec["sha256"]).encode("ascii"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _snapshot(files: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "file_count": len(files),
        "files": files,
        "tree_hash": _tree_hash(files),
    }


def _diff(
    start_files: dict[str, dict[str, Any]],
    end_files: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    names = sorted(set(start_files) | set(end_files))
    changed: list[dict[str, Any]] = []
    for rel in names:
        before = start_files.get(rel)
        after = end_files.get(rel)
        if before is None and after is not None:
            kind = "added"
        elif before is not None and after is None:
            kind = "deleted"
        elif before is not None and after is not None and before["sha256"] != after["sha256"]:
            kind = "modified"
        else:
            continue
        changed.append(
            {
                "path": rel,
                "kind": kind,
                "start_sha256": None if before is None else before["sha256"],
                "end_sha256": None if after is None else after["sha256"],
            }
        )
    return changed, [row["path"] for row in changed]


def capture_tree(
    root: str | Path,
    mid_hook: Callable[[Path], None] | None = None,
    include_relpaths: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Hash `root` at start and end. Label FROZEN or SAMPLED.

    A start-only hasher would still claim FROZEN after a mid-capture rewrite.
    This function always takes the end hash, so a planted mutation cannot hide.
    """
    base = Path(root)
    if not base.is_dir():
        raise FileNotFoundError(f"capture root is not a directory: {base}")
    started_at = _utc_now()
    start_files = _inventory(base, include_relpaths)
    start_hash = _tree_hash(start_files)
    if mid_hook is not None:
        mid_hook(base)
    end_files = _inventory(base, include_relpaths)
    end_hash = _tree_hash(end_files)
    ended_at = _utc_now()
    frozen = start_hash == end_hash
    label = LABEL_FROZEN if frozen else LABEL_SAMPLED
    changed_paths, changed_path_names = _diff(start_files, end_files)
    if frozen:
        refused_code = None
        refused_reason = None
        sampled_at = None
        anchoring = ANCHOR_FROZEN
    else:
        refused_code = REFUSED_CODE
        refused_reason = (
            "start_tree_hash != end_tree_hash; capture is a timestamped sample, "
            "not a baseline"
        )
        sampled_at = ended_at
        anchoring = ANCHOR_SAMPLED
    return {
        "root": str(base),
        "start_tree_hash": start_hash,
        "end_tree_hash": end_hash,
        "hashes_equal": frozen,
        "label": label,
        "baseline_eligible": frozen,
        "baseline_refused": not frozen,
        "refused_code": refused_code,
        "refused_reason": refused_reason,
        "changed_paths": changed_paths,
        "changed_path_names": changed_path_names,
        "snapshot": _snapshot(end_files),
        "start_snapshot": _snapshot(start_files),
        "anchoring": anchoring,
        "sampled_at": sampled_at,
        "started_at": started_at,
        "ended_at": ended_at,
    }


def as_baseline(result: dict[str, Any]) -> dict[str, Any]:
    """Promote a FROZEN capture. Refuse SAMPLED."""
    if result.get("label") != LABEL_FROZEN or result.get("baseline_eligible") is not True:
        raise BaselineRefused(
            "refusing to call a mutated/SAMPLED capture a baseline",
            code=str(result.get("refused_code") or REFUSED_CODE),
            reason=str(
                result.get("refused_reason")
                or "start and end tree hashes differ"
            ),
            result=result,
        )
    promoted = dict(result)
    promoted["baseline"] = True
    return promoted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hash a tree at start and end.")
    parser.add_argument("root", type=Path)
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Restrict to this relative path (repeatable).",
    )
    args = parser.parse_args(argv)
    include = set(args.include) if args.include else None
    result = capture_tree(args.root, include_relpaths=include)
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if result["label"] == LABEL_FROZEN else 2


if __name__ == "__main__":
    sys.exit(main())
