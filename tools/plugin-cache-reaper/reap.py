#!/usr/bin/env python3
"""Reap abandoned plugin-install staging clones from ~/.claude/plugins/cache.

WHAT THIS IS: a MITIGATION, not a fix.

The writer is Claude Code itself (measured on the native binary, version
2.1.220 at C:/Users/Prekzursil/.local/bin/claude.exe) -- vendor code we cannot
patch. When a plugin whose marketplace entry declares a remote source is
materialised, the CLI clones into a staging directory directly under
``~/.claude/plugins/cache``:

    temp_subdir_<epoch_ms>_<rand6>.clone   for a ``git-subdir`` plugin source
    temp_git_<epoch_ms>_<rand6>            for a ``url`` / ``git`` plugin source

Measured behaviour (see tools/plugin-cache-reaper/README.md for the exact
commands and output):

* SUCCESS path      -> the staging dir IS removed. No leak.
* clone FAILS fast  -> the staging dir IS removed. No leak.
* process is KILLED mid-clone -> the staging dir SURVIVES, holding a partial
  ``.git`` and nothing checked out. This is the leak.

The reproduced husk resembles the live ones in the way that matters -- a partial
``.git`` with no worktree -- but NOT in shape. An earlier version of this note
claimed "a husk's only child is ``.git``"; measuring six live husks gave child
counts of 20, 1, 4, 19, 22 and 15, so exactly one of six matched. How far a clone
got before it died varies, so the child count varies with it. Nothing here depends
on that: candidacy is decided by NAME (``STAGING_RE``) alone and never by counting
children, so the reaper is unaffected. The claim was false and is corrected in
place rather than quietly dropped.

There is no on-exit handler and no start-up sweep in the CLI, so every
interrupted materialisation leaks one staging tree forever. This module is the
sweep the vendor does not do.

Safety rules encoded here, because the target is a live user directory:

* Only entries whose name matches STAGING_RE are ever candidates. A real plugin
  cache entry is ``cache/<marketplace>/<plugin>/<version>`` and can never match.
* Candidates are found with a SINGLE non-recursive scan of the cache root. We
  never glob into the husks: they hold deep ``.git`` trees that blow MAX_PATH
  (the ENAMETOOLONG hazard already documented in tools/glob-argv-guard).
* An age gate with TWO independent signals, AND-ed: the epoch-ms embedded in the
  directory NAME and the directory's own mtime must BOTH be older than the
  threshold. A single signal is not enough -- an in-flight clone has a fresh
  mtime, and a clock-skewed name must not be able to authorise a delete on its
  own. See rules/common/single-signal-verification.md.
* Dry-run is the default. ``--apply`` is required to delete anything.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

# The staging "kind" tokens the CLI can emit. Recovered from the string pool of
# the 2.1.220 native binary at offset 109756512 ("local", "npm", "github",
# "git", "subdir", "unknown", "temp_", "_") -- i.e. the name is built as
# f"temp_{kind}_{Date.now()}_{rand6}". Only ``subdir`` and ``git`` have been
# observed live; the rest are accepted because the binary can emit them.
KINDS = ("git", "subdir", "github", "npm", "local", "unknown")

STAGING_RE = re.compile(
    r"^temp_(?P<kind>"
    + "|".join(KINDS)
    + r")_(?P<ms>\d{13})_[0-9a-z]{6}(?P<clone>\.clone)?$"
)

DEFAULT_MIN_AGE_MINUTES = 120

# Resolved once at import so no function needs a platform branch (a branch that
# can only be taken on one OS is a branch the coverage gate can never close).
IS_WINDOWS = os.name == "nt"


@dataclass(frozen=True)
class Candidate:
    """One reapable staging directory."""

    path: Path
    kind: str
    name_ms: int
    mtime_ms: int
    size_bytes: int


def parse_staging_name(name: str) -> tuple[str, int] | None:
    """Return ``(kind, epoch_ms)`` for a staging dir name, else ``None``."""
    match = STAGING_RE.match(name)
    if match is None:
        return None
    return match.group("kind"), int(match.group("ms"))


def is_reapable(*, name_ms: int, mtime_ms: int, now_ms: int, min_age_ms: int) -> bool:
    """AND-gate the two independent age signals.

    ``name_ms`` comes from the directory name (what the writer stamped) and
    ``mtime_ms`` from the filesystem (what actually last touched it). Both must
    clear the threshold, so neither a skewed clock nor a stale name can retire a
    clone that is still being written.
    """
    return (now_ms - name_ms) >= min_age_ms and (now_ms - mtime_ms) >= min_age_ms


def long_path(path: Path, *, windows: bool = IS_WINDOWS) -> str:
    """Return a filesystem string safe for paths longer than MAX_PATH.

    On Windows the extended-length ``\\\\?\\`` prefix is required or a nested
    ``.git`` tree inside a husk raises ENOENT/ENAMETOOLONG. Elsewhere the plain
    string is correct. ``windows`` is injectable so both branches are testable
    on one platform.
    """
    text = str(path)
    if not windows or text.startswith("\\\\?\\"):
        return text
    return "\\\\?\\" + text


def tree_size_bytes(path: Path, *, windows: bool = IS_WINDOWS) -> int:
    """Sum file sizes under ``path`` without ever raising on a long path."""
    total = 0
    stack = [long_path(path, windows=windows)]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                else:
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                continue
    return total


def _force_remove(target: str) -> None:
    """Delete one file, clearing the read-only bit git sets on pack files."""
    try:
        os.unlink(target)
    except PermissionError:
        os.chmod(target, stat.S_IWRITE)
        os.unlink(target)


def remove_tree(path: Path, *, windows: bool = IS_WINDOWS) -> None:
    """Recursively delete ``path``, long-path- and read-only-safe.

    Implemented directly rather than via ``shutil.rmtree``: the ``onerror``
    callback needed for the read-only ``.git`` objects is removed in Python 3.14
    and its replacement ``onexc`` does not exist in the 3.11 the CI lane pins.
    """
    root = long_path(path, windows=windows)
    dirs: list[str] = []
    stack = [root]
    while stack:
        current = stack.pop()
        dirs.append(current)
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                stack.append(entry.path)
            else:
                _force_remove(entry.path)
    for directory in reversed(dirs):
        try:
            os.rmdir(directory)
        except OSError:
            pass


def default_cache_root() -> Path:
    """The live plugin cache for this user."""
    return Path.home() / ".claude" / "plugins" / "cache"


def validate_root(root: Path) -> None:
    """Refuse to operate anywhere that is not a plugin cache directory.

    A typo in ``--root`` must not turn this into a generic deleter, so the last
    two path components are asserted rather than trusted.
    """
    parts = root.parts
    if len(parts) < 2 or parts[-1] != "cache" or parts[-2] != "plugins":
        raise ValueError(f"refusing to scan {root}: not a .../plugins/cache path")


def find_candidates(
    root: Path,
    *,
    now_ms: int,
    min_age_ms: int,
    windows: bool = IS_WINDOWS,
    measure: bool = True,
) -> list[Candidate]:
    """One non-recursive scan of ``root`` -> the reapable staging dirs."""
    validate_root(root)
    found: list[Candidate] = []
    try:
        entries = list(os.scandir(long_path(root, windows=windows)))
    except OSError:
        return found
    for entry in entries:
        parsed = parse_staging_name(entry.name)
        if parsed is None:
            continue
        if not entry.is_dir(follow_symlinks=False):
            continue
        kind, name_ms = parsed
        mtime_ms = int(entry.stat(follow_symlinks=False).st_mtime * 1000)
        if not is_reapable(
            name_ms=name_ms, mtime_ms=mtime_ms, now_ms=now_ms, min_age_ms=min_age_ms
        ):
            continue
        path = root / entry.name
        size = tree_size_bytes(path, windows=windows) if measure else 0
        found.append(
            Candidate(
                path=path,
                kind=kind,
                name_ms=name_ms,
                mtime_ms=mtime_ms,
                size_bytes=size,
            )
        )
    return sorted(found, key=lambda c: c.name_ms)


def reap(
    root: Path,
    *,
    now_ms: int,
    min_age_ms: int,
    apply: bool,
    windows: bool = IS_WINDOWS,
    measure: bool = True,
) -> dict[str, object]:
    """Find (and optionally delete) abandoned staging dirs. Returns a report."""
    candidates = find_candidates(
        root, now_ms=now_ms, min_age_ms=min_age_ms, windows=windows, measure=measure
    )
    removed: list[str] = []
    if apply:
        for candidate in candidates:
            remove_tree(candidate.path, windows=windows)
            removed.append(candidate.path.name)
    by_kind: dict[str, int] = {}
    for candidate in candidates:
        by_kind[candidate.kind] = by_kind.get(candidate.kind, 0) + 1
    return {
        "root": str(root),
        "applied": apply,
        "count": len(candidates),
        "bytes": sum(c.size_bytes for c in candidates),
        "by_kind": by_kind,
        "removed": removed,
        "oldest": candidates[0].path.name if candidates else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reap.py",
        description=(
            "Reap abandoned Claude Code plugin-install staging clones. "
            "MITIGATION for a vendor leak, not a fix. Dry-run unless --apply."
        ),
    )
    parser.add_argument("--root", type=Path, default=None, help="cache dir to scan")
    parser.add_argument(
        "--min-age-minutes",
        type=int,
        default=DEFAULT_MIN_AGE_MINUTES,
        help=f"only reap dirs older than this (default {DEFAULT_MIN_AGE_MINUTES})",
    )
    parser.add_argument("--apply", action="store_true", help="actually delete")
    parser.add_argument(
        "--no-measure", action="store_true", help="skip the byte tally (faster)"
    )
    return parser


def main(argv: list[str] | None = None, *, now_ms: int | None = None) -> int:
    """CLI entry point. Emits an AGENTS.md-section-4 terminal-state marker."""
    args = build_parser().parse_args(argv)
    if args.min_age_minutes < 1:
        print(
            "FAILED:plugin-cache-reap --min-age-minutes must be >= 1", file=sys.stderr
        )
        return 2
    root = args.root if args.root is not None else default_cache_root()
    if now_ms is None:  # pragma: no cover - wall clock
        import time

        now_ms = int(time.time() * 1000)
    try:
        report = reap(
            root,
            now_ms=now_ms,
            min_age_ms=args.min_age_minutes * 60_000,
            apply=args.apply,
            measure=not args.no_measure,
        )
    except ValueError as exc:
        print(f"FAILED:plugin-cache-reap {exc}", file=sys.stderr)
        return 2
    verb = "reaped" if args.apply else "would reap"
    print(
        f"SUCCESS:plugin-cache-reap {verb} {report['count']} staging dirs "
        f"({report['bytes']} bytes) under {report['root']} by_kind={report['by_kind']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
