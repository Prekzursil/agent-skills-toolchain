#!/usr/bin/env python3
"""Deduplicate CRCP outbox: keep max N versions per conversation, trash the rest.

Usage:
  python scripts/cleanup_outbox.py
  python scripts/cleanup_outbox.py --max-keep 5 --outbox PATH --trash PATH
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUTBOX = Path(__file__).resolve().parents[1] / "outbox"
DEFAULT_TRASH_ROOT = Path.home() / "Cowork" / "trash"
PAT = re.compile(r"^(chatgpt_conv|envelope)_([0-9a-fA-F\-]+)_(.+)\.json$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outbox", type=Path, default=DEFAULT_OUTBOX)
    parser.add_argument("--max-keep", type=int, default=5)
    parser.add_argument(
        "--trash",
        type=Path,
        default=None,
        help="Trash directory (default: ~/Cowork/trash/crcp-outbox-bloat-<ts>)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    outbox: Path = args.outbox
    if not outbox.is_dir():
        print(json.dumps({"error": f"outbox missing: {outbox}"}))
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    trash = args.trash or (DEFAULT_TRASH_ROOT / f"crcp-outbox-bloat-{stamp}")
    if not args.dry_run:
        trash.mkdir(parents=True, exist_ok=True)

    groups: dict[tuple[str, str], list[tuple[str, Path]]] = defaultdict(list)
    other: list[str] = []
    for path in outbox.iterdir():
        if not path.is_file():
            continue
        if path.name.startswith("."):
            other.append(path.name)
            continue
        match = PAT.match(path.name)
        if not match:
            other.append(path.name)
            continue
        kind, cid, file_stamp = match.group(1), match.group(2), match.group(3)
        groups[(kind, cid)].append((file_stamp, path))

    kept = 0
    moved = 0
    for files in groups.values():
        files.sort(key=lambda item: item[0], reverse=True)
        for index, (_stamp, path) in enumerate(files):
            if index < args.max_keep:
                kept += 1
                continue
            moved += 1
            if args.dry_run:
                continue
            dest = trash / path.name
            shutil.move(str(path), str(dest))

    report = {
        "outbox": str(outbox),
        "trash": str(trash),
        "max_keep_per_kind_cid": args.max_keep,
        "groups": len(groups),
        "kept": kept,
        "moved_to_trash": moved,
        "other_left": other,
        "remaining_files": len(list(outbox.iterdir())) if outbox.is_dir() else 0,
        "dry_run": args.dry_run,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
