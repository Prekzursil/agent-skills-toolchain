#!/usr/bin/env python3
"""Name missing shards. Never average over whatever happens to be on disk.

TST-0148 contract: for a multi-shard artifact set, COMPLETE is allowed only when
every id in the on-disk shard manifest is present as a regular file in the set
root. If any id is absent, the status is INCOMPLETE and ``missing_ids`` enumerates
those ids. The reducer must not emit a score, majority, or mean over the shards
that happen to be present.

ADV-0009 consumes the same library and CLI: silent (COMPLETE, exit 0) on a full
set, fires (status != COMPLETE, exit 1) when a named shard is missing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

COMPLETE = "COMPLETE"
INCOMPLETE = "INCOMPLETE"


def _as_path(value: Path | str) -> Path:
    return value if isinstance(value, Path) else Path(value)


def _basename(rel: object) -> str:
    return Path(str(rel or "").replace("\\", "/")).name


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("shard manifest root must be a JSON object")
    return raw


def _shard_rows(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in manifest.get("shards") or []:
        if isinstance(item, dict) and str(item.get("id") or "").strip():
            rows.append(item)
    return rows


def list_regular_files(set_root: Path) -> list[str]:
    """Sorted basenames of regular files in set_root. Not recursive."""
    if not set_root.is_dir():
        return []
    names = [p.name for p in set_root.iterdir() if p.is_file()]
    names.sort()
    return names


def diff_against_manifest(
    set_root: Path, shards: Iterable[Mapping[str, Any]]
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (expected_ids, present_ids, missing_ids, extra_names).

    Identity is the shard ``id``. Presence is a regular file whose basename
    matches the manifest ``path`` basename. Extra files are reported but never
    converted into a score.
    """
    expected_ids: list[str] = []
    present_ids: list[str] = []
    missing_ids: list[str] = []
    expected_names: set[str] = set()
    for shard in shards:
        sid = str(shard.get("id") or "").strip()
        name = _basename(shard.get("path"))
        if not sid:
            continue
        expected_ids.append(sid)
        if name:
            expected_names.add(name)
        dest = set_root / name if name else set_root
        if name and dest.is_file():
            present_ids.append(sid)
        else:
            missing_ids.append(sid)
    on_disk = set(list_regular_files(set_root))
    extra_names = sorted(on_disk - expected_names)
    return expected_ids, present_ids, missing_ids, extra_names


def reduce_shard_set(set_root: Path | str, manifest_path: Path | str) -> dict[str, Any]:
    """Read the manifest from disk and classify the set root.

    COMPLETE only if ``missing_ids`` is empty. ``score`` is always None.
    ``computed_over_present`` is always False.
    """
    root = _as_path(set_root)
    man_path = _as_path(manifest_path)
    listing = list_regular_files(root)
    if not man_path.is_file():
        return {
            "status": INCOMPLETE,
            "missing_ids": ["MANIFEST"],
            "present_ids": [],
            "expected_ids": [],
            "directory_listing": listing,
            "computed_over_present": False,
            "score": None,
            "set_id": None,
            "set_root": str(root),
            "manifest_path": str(man_path),
        }
    manifest = _load_manifest(man_path)
    shards = _shard_rows(manifest)
    expected_ids, present_ids, missing_ids, extra_names = diff_against_manifest(
        root, shards
    )
    status = COMPLETE if not missing_ids else INCOMPLETE
    return {
        "status": status,
        "missing_ids": missing_ids,
        "present_ids": present_ids,
        "expected_ids": expected_ids,
        "directory_listing": listing,
        "extra_names": extra_names,
        "computed_over_present": False,
        "score": None,
        "set_id": manifest.get("set_id"),
        "set_root": str(root),
        "manifest_path": str(man_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Classify a multi-shard artifact set. COMPLETE iff every manifest "
            "id is present as a regular file. Missing ids are named; present "
            "shards are never averaged into a score."
        )
    )
    parser.add_argument(
        "--set-root",
        required=True,
        help="Directory that should contain the shard files",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="On-disk shard manifest JSON (read live; not an in-memory claim)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = reduce_shard_set(args.set_root, args.manifest)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "status": INCOMPLETE,
            "missing_ids": ["MANIFEST"],
            "present_ids": [],
            "expected_ids": [],
            "directory_listing": [],
            "computed_over_present": False,
            "score": None,
            "set_id": None,
            "set_root": str(args.set_root),
            "manifest_path": str(args.manifest),
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == COMPLETE else 1


if __name__ == "__main__":
    raise SystemExit(main())
