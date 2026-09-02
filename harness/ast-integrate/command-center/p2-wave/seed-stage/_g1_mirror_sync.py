#!/usr/bin/env python3
"""rsync-free mirror sync: state of record (WIN) -> execution mirror (ROOT).

Copies every file whose (size, mtime) differs, preserving mtimes (shutil.copy2), creating
directories as needed. Never deletes in the mirror (persistent-mirror semantics, like the
owner's `_g1_rsync.sh` without --delete). Skips .git, node_modules, __pycache__ and
command-center/p2-wave/ovh-monitor (ledgers are read/written in WIN directly).

Usage: python3 _g1_mirror_sync.py [--paths rel1 rel2 ...]   (default: whole tree)
Prints `MIRROR-OK copied=<n> scanned=<n> src=... dst=...`.
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g1_paths import MIRROR, SCRATCH_DIR_NAMES, WIN  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "__pycache__"}
SKIP_REL = {Path("command-center/p2-wave/ovh-monitor")}
PROBES_REL = Path("command-center/p2-wave/probes")


def _skip_dir(rel_dir: Path, name: str) -> bool:
    if name in SKIP_DIRS or (rel_dir / name) in SKIP_REL:
        return True
    # probe run-time scratch is regenerated in the mirror; never copy it from the record
    return name in SCRATCH_DIR_NAMES and PROBES_REL in (rel_dir / name).parents


def sync_tree(src_root: Path, dst_root: Path, rel: Path = Path(".")) -> tuple[int, int]:
    copied = scanned = 0
    base = src_root / rel
    if base.is_file():
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        st = base.stat()
        try:
            dt = dst.stat()
            same = dt.st_size == st.st_size and int(dt.st_mtime) == int(st.st_mtime)
        except FileNotFoundError:
            same = False
        if not same:
            shutil.copy2(base, dst)
            copied += 1
        return copied, 1
    for dirpath, dirnames, filenames in os.walk(base):
        dp = Path(dirpath)
        rel_dir = dp.relative_to(src_root)
        dirnames[:] = [d for d in dirnames if not _skip_dir(rel_dir, d)]
        (dst_root / rel_dir).mkdir(parents=True, exist_ok=True)
        for name in filenames:
            scanned += 1
            src = dp / name
            dst = dst_root / rel_dir / name
            try:
                st = src.stat()
            except OSError:
                continue
            try:
                dt = dst.stat()
                if dt.st_size == st.st_size and int(dt.st_mtime) == int(st.st_mtime):
                    continue
            except FileNotFoundError:
                pass
            try:
                shutil.copy2(src, dst)
                copied += 1
            except OSError as exc:
                print(f"MIRROR-SKIP {src}: {exc}", file=sys.stderr)
    return copied, scanned


def main() -> int:
    t0 = time.time()
    args = sys.argv[1:]
    rels = [Path(p) for p in args[1:]] if args[:1] == ["--paths"] else [Path(".")]
    copied = scanned = 0
    for rel in rels:
        c, s = sync_tree(WIN, MIRROR, rel)
        copied += c
        scanned += s
    print(f"MIRROR-OK copied={copied} scanned={scanned} src={WIN} dst={MIRROR} secs={time.time() - t0:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
