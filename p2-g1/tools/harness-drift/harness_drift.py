"""Deterministic two-directional differ: the LIVE harness tree vs this repo.

WHY THIS EXISTS
---------------
``~/.claude/platform-redesign-2026-07-19/prompt2-readiness/20260720-174550/
16-DRIFT-CLASSIFIED.json`` classified 338 files by handing the comparison to LLM
agents. A measured fan-out of that same classification scored 86% with **100% of the
errors in the dangerous direction** -- 31 files called deploy-safe that were actually
two-way DIVERGED. The blind spot was one-directional reading: checking whether the
repo had extra content and never checking whether live ALSO had unique lines. This
module is the exact algorithm that retires that judgement call.

GUARANTEES
----------
1. **Two-directional by construction.** Every non-identical text pair goes through
   :class:`difflib.SequenceMatcher` and BOTH ``only_repo`` and ``only_live`` line
   counts are recorded. ``REPO-AHEAD`` requires ``only_live == 0``; ``LIVE-AHEAD``
   requires ``only_repo == 0``. Anything else is ``DIVERGED``.
2. **Line endings are normalised first.** CRLF/CR -> LF and a leading UTF-8 BOM is
   dropped, so a Windows working tree vs an LF blob does not manufacture hundreds of
   phantom differences. Byte-different but normalised-identical is ``NOISE-ONLY``.
3. **Errs toward DIVERGED.** A moved (not edited) block reads as both an insert and a
   delete, so it lands in ``DIVERGED`` rather than any "safe to overwrite" bucket.
   Under-claiming safety is cheap; destroying unique work is not.
4. **Undecodable pairs are never called safe** -> ``DIVERGED-BINARY``.

MAPPING
-------
:data:`AREA_MAP` is lifted verbatim from this repo's own authoritative table at
``scripts/sync-from-live.ps1`` lines 155-159. It is NOT the mapping the 2026-07-20
artifact used: that one compared ``skills/`` against ``~/.claude/skills`` (a symlink
to the curated ``skills.daily`` subset) and ``.agents/skills`` against
``~/.claude/.agents/skills``; neither pair appears in the repo's map, and the artifact
covered none of ``agents/`` or ``commands/``.

USAGE
-----
    python tools/harness-drift/harness_drift.py --out drift.json
    python tools/harness-drift/harness_drift.py --out drift.json --area hooks
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

#: ``(repo-relative root, live root relative to $HOME, area label)``.
#: Source of truth: ``scripts/sync-from-live.ps1`` lines 155-159.
AREA_MAP: tuple[tuple[str, str, str], ...] = (
    ("rules", ".claude/rules", "rules"),
    ("agents", ".claude/agents", "agents"),
    ("commands", ".claude/commands", "commands"),
    ("hooks", ".claude/hooks", "hooks"),
    (".agents/skills", ".agents/skills", "skills"),
)

#: Generated / third-party / machine-local dirs. From ``sync-from-live.ps1`` 172-174.
EXCLUDE_DIRS = frozenset(
    {
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".git",
        ".pytest_cache",
        "site-packages",
        "dist",
        "build",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".next",
        "target",
        ".gradle",
    }
)

#: Generated files and agent-written backups. From ``sync-from-live.ps1`` 175-183.
EXCLUDE_FILE_RE = re.compile(
    r"(?i)("
    r"\.py[co]$|\.so$|\.dll$|\.exe$|\.egg-info$|\.log$|\.tmp$"
    r"|^\.DS_Store$|^Thumbs\.db$"
    r"|\.sqlite3?$|\.db$"
    r"|\.bak$|\.bak-|\.bak\.|\.orig$|\.rej$|~$|\.old$|\.save$"
    r")"
)

#: Dated / labelled snapshot dirs. ``sync-from-live.ps1`` does not exclude these, but
#: every file inside one is a historical copy, so counting them inflates LIVE-ONLY
#: with rows that must never be synced anywhere. Deliberately NARROW: a bare leading
#: underscore is not enough -- ``hooks/_dispatch`` and ``hooks/_shared`` are live code.
BACKUP_DIR_RE = re.compile(
    r"(?i)^_.*(backup|bak|attic|quarantine|retired|archived|pre-frontmatter|\d{8})"
)

V_IDENTICAL = "IDENTICAL"
V_NOISE = "NOISE-ONLY"
V_REPO_AHEAD = "REPO-AHEAD"
V_LIVE_AHEAD = "LIVE-AHEAD"
V_DIVERGED = "DIVERGED"
V_DIVERGED_BIN = "DIVERGED-BINARY"
V_REPO_ONLY = "REPO-ONLY"
V_LIVE_ONLY = "LIVE-ONLY"

_CHUNK = 1 << 16


def is_symlink(path: Path) -> bool:
    """Indirection so the symlink branches are testable without OS privilege.

    Creating a real symlink on Windows needs Developer Mode or elevation, so a test
    that depends on one is a test that silently skips. Tests patch this instead.
    """
    return path.is_symlink()


@dataclass
class Row:
    """One comparison unit."""

    area: str
    repo_path: str
    live_path: str
    verdict: str
    repo_bytes: int | None = None
    live_bytes: int | None = None
    repo_sha256: str | None = None
    live_sha256: str | None = None
    only_repo_lines: int = 0
    only_live_lines: int = 0
    changed_hunks: int = 0
    note: str = ""


@dataclass
class Summary:
    """Machine-readable run header."""

    schema: str = "harness-drift/v2-deterministic"
    generated_utc: str = ""
    repo_root: str = ""
    repo_head: str = ""
    live_home: str = ""
    areas: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    counts_by_area: dict[str, dict[str, int]] = field(default_factory=dict)
    total_rows: int = 0
    skipped_symlinks: list[str] = field(default_factory=list)
    skipped_nested_repos: list[str] = field(default_factory=list)
    missing_live_roots: list[str] = field(default_factory=list)


def sha256_of(path: Path) -> tuple[str, int]:
    """Return ``(hexdigest, byte size)`` for *path*, streamed."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def normalise(raw: bytes) -> list[str] | None:
    """Decode *raw* to BOM-free, LF-split lines, or ``None`` if not UTF-8."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def two_directional_diff(
    repo_lines: list[str], live_lines: list[str]
) -> tuple[int, int, int]:
    """Return ``(only_repo, only_live, hunks)`` -- unique lines on BOTH sides.

    A pure move yields both counts > 0, so it classifies as ``DIVERGED``: the safe
    direction. ``autojunk`` is off so long files are not silently under-matched.
    """
    matcher = difflib.SequenceMatcher(a=repo_lines, b=live_lines, autojunk=False)
    only_repo = 0
    only_live = 0
    hunks = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        hunks += 1
        if tag in ("replace", "delete"):
            only_repo += i2 - i1
        if tag in ("replace", "insert"):
            only_live += j2 - j1
    return only_repo, only_live, hunks


def classify(only_repo: int, only_live: int) -> str:
    """Map the two-directional counts onto the verdict vocabulary."""
    if only_repo and only_live:
        return V_DIVERGED
    if only_repo:
        return V_REPO_AHEAD
    if only_live:
        return V_LIVE_AHEAD
    return V_NOISE


def _posix(path: Path | str) -> str:
    return str(path).replace(os.sep, "/")


def compare_pair(area: str, repo_rel: str, repo_file: Path, live_file: Path) -> Row:
    """Compare one repo/live pair. Byte-equality short-circuits before any decode."""
    repo_sha, repo_size = sha256_of(repo_file)
    live_sha, live_size = sha256_of(live_file)
    row = Row(
        area=area,
        repo_path=repo_rel,
        live_path=_posix(live_file),
        verdict=V_IDENTICAL,
        repo_bytes=repo_size,
        live_bytes=live_size,
        repo_sha256=repo_sha,
        live_sha256=live_sha,
    )
    if repo_sha == live_sha:
        return row
    repo_lines = normalise(repo_file.read_bytes())
    live_lines = normalise(live_file.read_bytes())
    if repo_lines is None or live_lines is None:
        row.verdict = V_DIVERGED_BIN
        row.note = "not UTF-8 decodable; byte comparison only"
        return row
    only_repo, only_live, hunks = two_directional_diff(repo_lines, live_lines)
    row.only_repo_lines = only_repo
    row.only_live_lines = only_live
    row.changed_hunks = hunks
    row.verdict = classify(only_repo, only_live)
    if row.verdict == V_NOISE:
        row.note = "byte-different, normalised-identical (line endings and/or BOM)"
    return row


def walk_tree(root: Path, summary: Summary, label: str) -> dict[str, Path]:
    """Return ``{posix relative path: absolute Path}`` for comparable files."""
    found: dict[str, Path] = {}
    if not root.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        keep: list[str] = []
        for name in sorted(dirnames):
            child = here / name
            if name in EXCLUDE_DIRS or BACKUP_DIR_RE.match(name):
                continue
            if is_symlink(child):
                summary.skipped_symlinks.append(f"{label}:{_posix(child)}")
                continue
            if (child / ".git").exists():
                summary.skipped_nested_repos.append(f"{label}:{_posix(child)}")
                continue
            keep.append(name)
        dirnames[:] = keep
        for name in sorted(filenames):
            if EXCLUDE_FILE_RE.search(name):
                continue
            full = here / name
            if is_symlink(full):
                summary.skipped_symlinks.append(f"{label}:{_posix(full)}")
                continue
            found[full.relative_to(root).as_posix()] = full
    return found


def _head_of(repo_root: Path) -> str:
    """``git rev-parse HEAD`` for *repo_root*, or ``UNKNOWN`` if git cannot answer."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"
    return done.stdout.strip()


def _only_row(
    area: str, repo_rel: str, live_path: Path, source: Path, live: bool
) -> Row:
    """Build a one-sided row for a file present in exactly one tree."""
    sha, size = sha256_of(source)
    return Row(
        area=area,
        repo_path=repo_rel,
        live_path=_posix(live_path),
        verdict=V_LIVE_ONLY if live else V_REPO_ONLY,
        repo_bytes=None if live else size,
        live_bytes=size if live else None,
        repo_sha256=None if live else sha,
        live_sha256=sha if live else None,
        note="absent from repo tree" if live else "absent from live tree",
    )


def run(
    repo_root: Path, live_home: Path, only_areas: set[str] | None = None
) -> tuple[Summary, list[Row]]:
    """Execute the full comparison and return ``(summary, rows)``."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    summary = Summary(
        generated_utc=now,
        repo_root=_posix(repo_root),
        repo_head=_head_of(repo_root),
        live_home=_posix(live_home),
    )
    rows: list[Row] = []
    for repo_rel_root, live_rel_root, label in AREA_MAP:
        if only_areas is not None and label not in only_areas:
            continue
        summary.areas.append(label)
        live_root = live_home / live_rel_root
        if not live_root.is_dir():
            summary.missing_live_roots.append(f"{label}:{_posix(live_root)}")
        repo_files = walk_tree(repo_root / repo_rel_root, summary, f"repo/{label}")
        live_files = walk_tree(live_root, summary, f"live/{label}")
        for rel in sorted(set(repo_files) | set(live_files)):
            repo_file = repo_files.get(rel)
            live_file = live_files.get(rel)
            repo_rel = f"{repo_rel_root}/{rel}"
            if repo_file is not None and live_file is not None:
                rows.append(compare_pair(label, repo_rel, repo_file, live_file))
            elif repo_file is not None:
                rows.append(
                    _only_row(label, repo_rel, live_root / rel, repo_file, live=False)
                )
            else:
                live_only = live_files[rel]
                rows.append(_only_row(label, repo_rel, live_only, live_only, live=True))
    for row in rows:
        summary.counts[row.verdict] = summary.counts.get(row.verdict, 0) + 1
        per_area = summary.counts_by_area.setdefault(row.area, {})
        per_area[row.verdict] = per_area.get(row.verdict, 0) + 1
    summary.total_rows = len(rows)
    return summary, rows


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Writes ``{"summary": ..., "rows": [...]}`` to ``--out``."""
    parser = argparse.ArgumentParser(description="Deterministic harness drift differ")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--live-home", default=str(Path.home()))
    parser.add_argument("--out", required=True, help="path for the classification JSON")
    parser.add_argument("--area", action="append", help="restrict to one area label")
    args = parser.parse_args(argv)

    summary, rows = run(
        Path(args.repo_root).resolve(),
        Path(args.live_home).resolve(),
        set(args.area) if args.area else None,
    )
    payload = {"summary": asdict(summary), "rows": [asdict(r) for r in rows]}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"rows={summary.total_rows} head={summary.repo_head[:12]}")
    for verdict, count in sorted(summary.counts.items(), key=lambda kv: -kv[1]):
        print(f"  {verdict:<16} {count}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via main()
    sys.exit(main())
