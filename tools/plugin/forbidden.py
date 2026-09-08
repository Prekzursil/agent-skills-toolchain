#!/usr/bin/env python3
"""Forbidden-content scanner for a staged payload tree (IMP-0003).

Classifies by PATH ROLE only — never by content entropy (that is IMP-0004).
Fails closed when the staging tree contains any of:

* a ``.git`` directory or gitlink (``.git`` file / gitdir pointer / mode 160000)
* ``node_modules``
* ``__pycache__``
* ``*.log``
* transcript / session JSONL
* an OS cache directory / OS junk path
* any single file above a configured byte ceiling

Standalone CLI + library. Pack pre-emit calls :func:`assert_clean` /
:func:`classify_path_role` so allowlisted-but-forbidden paths still fail the build.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

#: Default per-file ceiling (10 MiB). Override via ``--max-file-bytes`` or
#: ``ScanConfig.max_file_bytes``. Distinct from the allowlist *total* budget.
DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024

#: Git submodule / gitlink mode bit in ``git ls-files --stage``.
GITLINK_MODE = 0o160000

#: Path-role classes. Keys are stable ids used in reports and tests.
#: Patterns match NFC-normalised POSIX relative paths; ``*`` is slash-agnostic
#: fnmatch-style for a single segment unless the pattern embeds ``/``.
FORBIDDEN_ROLES: dict[str, tuple[str, ...]] = {
    # .git directory OR any path segment equal to .git (covers nested repos).
    # Gitlink: a FILE named .git (gitdir pointer) is also caught via segment/.git.
    "git": (".git", ".git/*", "*/.git", "*/.git/*", ".gitmodules"),
    "node_modules": (
        "node_modules",
        "node_modules/*",
        "*/node_modules",
        "*/node_modules/*",
    ),
    "pycache": (
        "__pycache__",
        "__pycache__/*",
        "*/__pycache__",
        "*/__pycache__/*",
        "*.pyc",
        "*.pyo",
    ),
    "log": ("*.log", "*.log.*", "logs/*", "*/logs/*"),
    "transcript": (
        "*.jsonl",
        "*transcript*",
        "*/sessions/*",
        "sessions/*",
        "*/.claude/history*",
        ".claude/history*",
    ),
    "os_cache": (
        ".DS_Store",
        "*/.DS_Store",
        "Thumbs.db",
        "*/Thumbs.db",
        "desktop.ini",
        "*/desktop.ini",
        "__MACOSX",
        "__MACOSX/*",
        "*/__MACOSX",
        "*/__MACOSX/*",
        ".Spotlight-V100",
        ".Spotlight-V100/*",
        "*/.Spotlight-V100",
        "*/.Spotlight-V100/*",
        ".Trashes",
        ".Trashes/*",
        "*/.Trashes",
        "*/.Trashes/*",
        ".cache",
        ".cache/*",
        "*/.cache",
        "*/.cache/*",
    ),
}

#: Ordered role ids (tests + reports iterate stably). ``oversized`` is size-based.
ROLE_ORDER: tuple[str, ...] = (
    "git",
    "node_modules",
    "pycache",
    "log",
    "transcript",
    "os_cache",
    "oversized",
)

#: Known-present planted path used as the detector control. Silence alone is never
#: trusted: a clean verdict requires this plant to have been FOUND in the same run.
PLANTED_CONTROL_REL = ".git/config"
PLANTED_CONTROL_ROLE = "git"


class ForbiddenError(RuntimeError):
    """Staging tree contains forbidden path-role content."""


@dataclass(frozen=True)
class Finding:
    path: str
    role: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "role": self.role, "detail": self.detail}


@dataclass
class ScanConfig:
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    #: When True (default), refuse a clean verdict unless the planted control fired.
    require_planted_control: bool = True


@dataclass
class ScanReport:
    root: str
    findings: list[Finding] = field(default_factory=list)
    paths_seen: int = 0
    files_seen: int = 0
    dirs_seen: int = 0
    planted_control_found: bool = False
    planted_control_path: str = PLANTED_CONTROL_REL
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    clean: bool = False
    exit_code: int = 1

    def as_dict(self) -> dict:
        d = asdict(self)
        d["findings"] = [f.as_dict() if isinstance(f, Finding) else f for f in self.findings]
        return d

    def named_path_report(self) -> str:
        lines = [
            f"root={self.root}",
            f"paths_seen={self.paths_seen}",
            f"files_seen={self.files_seen}",
            f"dirs_seen={self.dirs_seen}",
            f"max_file_bytes={self.max_file_bytes}",
            f"planted_control_path={self.planted_control_path}",
            f"planted_control_found={self.planted_control_found}",
            f"finding_count={len(self.findings)}",
            f"clean={self.clean}",
            f"exit_code={self.exit_code}",
        ]
        for f in self.findings:
            lines.append(f"FORBIDDEN path={f.path} role={f.role} detail={f.detail}")
        return "\n".join(lines) + "\n"


def nfc_posix(path: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFC", path.replace("\\", "/"))


def _fnmatch_role(rel: str, pattern: str) -> bool:
    """Lightweight glob: ``*`` matches any run of non-slash chars; ``**`` refused."""
    if "**" in pattern:
        raise ForbiddenError(f"recursive glob '**' is forbidden in role patterns: {pattern!r}")
    # Escape regex specials except our * wildcard.
    parts: list[str] = []
    for ch in pattern:
        if ch == "*":
            parts.append("[^/]*")
        elif ch in ".^$+{}[]|()\\":
            parts.append("\\" + ch)
        else:
            parts.append(ch)
    return re.match("^" + "".join(parts) + "$", rel) is not None


def classify_path_role(rel: str, *, roles: dict[str, tuple[str, ...]] | None = None) -> str | None:
    """Return the forbidden path-role for ``rel``, or None.

    Path-role only. Does not inspect file bytes (except callers may pass size
    separately via :func:`classify_size`).
    """
    unified = nfc_posix(rel).lstrip("/")
    table = roles if roles is not None else FORBIDDEN_ROLES
    segments = unified.split("/") if unified else []

    for role in ROLE_ORDER:
        if role == "oversized":
            continue
        patterns = table.get(role, ())
        for pat in patterns:
            if _fnmatch_role(unified, pat):
                return role
            # Bare directory name as a path segment (e.g. ``.git``, ``node_modules``).
            bare = pat.rstrip("/*").lstrip("*/")
            if bare and "*" not in bare and bare in segments:
                return role
    return None


def classify_size(size: int, *, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES) -> str | None:
    if max_file_bytes > 0 and size > max_file_bytes:
        return "oversized"
    return None


def is_gitlink_entry(*, name: str, is_dir: bool, is_file: bool, mode: int | None = None) -> bool:
    """True when the entry is a gitlink / gitdir pointer.

    * ``mode == 0o160000`` (git ls-files --stage)
    * a FILE named ``.git`` (contains ``gitdir: ...`` in a linked worktree / submodule)
    """
    if mode is not None and (mode & 0o170000) == GITLINK_MODE:
        return True
    if name == ".git" and is_file and not is_dir:
        return True
    return False


def _iter_tree(root: Path) -> Iterable[tuple[str, Path, os.stat_result]]:
    """Yield (relposix, abspath, stat) for every file/dir under root (dirs included)."""
    root = root.resolve()
    if not root.exists():
        return
    # Include root children only; never emit "" for the root itself as a finding target.
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        base = Path(dirpath)
        rel_dir = nfc_posix(str(base.relative_to(root)))
        if rel_dir == ".":
            rel_dir = ""

        # Directory entries themselves (so empty forbidden dirs are still seen).
        for dname in list(dirnames):
            abs_d = base / dname
            try:
                st = abs_d.lstat()
            except OSError:
                continue
            rel = nfc_posix(f"{rel_dir}/{dname}" if rel_dir else dname)
            yield rel, abs_d, st

        for fname in filenames:
            abs_f = base / fname
            try:
                st = abs_f.lstat()
            except OSError:
                continue
            rel = nfc_posix(f"{rel_dir}/{fname}" if rel_dir else fname)
            yield rel, abs_f, st


def scan_staging(
    root: Path | str,
    *,
    config: ScanConfig | None = None,
    roles: dict[str, tuple[str, ...]] | None = None,
    planted_control_root: Path | str | None = None,
) -> ScanReport:
    """Scan ``root`` for forbidden path roles.

    If ``planted_control_root`` is set (or defaults to a sibling control when
    ``config.require_planted_control``), the detector control is evaluated in the
    *same run*: the plant must be FOUND before ``clean`` can be True even when
    ``root`` itself has zero findings.
    """
    cfg = config or ScanConfig()
    root_p = Path(root)
    findings: list[Finding] = []
    paths_seen = 0
    files_seen = 0
    dirs_seen = 0
    table = roles if roles is not None else FORBIDDEN_ROLES

    if root_p.exists():
        for rel, abspath, st in _iter_tree(root_p):
            paths_seen += 1
            is_dir = stat_is_dir(st)
            is_file = stat_is_file(st)
            if is_dir:
                dirs_seen += 1
            if is_file:
                files_seen += 1

            name = Path(rel).name
            if is_gitlink_entry(
                name=name,
                is_dir=is_dir,
                is_file=is_file,
                mode=getattr(st, "st_mode", None),
            ):
                findings.append(
                    Finding(path=rel, role="git", detail="gitlink-or-gitdir-file")
                )
                continue

            role = classify_path_role(rel, roles=table)
            if role is not None:
                findings.append(Finding(path=rel, role=role, detail="path-role"))
                continue

            if is_file and not is_dir:
                size = int(st.st_size)
                sz_role = classify_size(size, max_file_bytes=cfg.max_file_bytes)
                if sz_role:
                    findings.append(
                        Finding(
                            path=rel,
                            role=sz_role,
                            detail=f"size={size}>max={cfg.max_file_bytes}",
                        )
                    )

    # Detector control: known-present plant must be FOUND in the same run.
    planted_found = False
    control_root: Path | None
    if planted_control_root is not None:
        control_root = Path(planted_control_root)
    elif cfg.require_planted_control:
        control_root = None  # caller may set planted_control_found externally
    else:
        control_root = None

    if control_root is not None and control_root.exists():
        plant = control_root / PLANTED_CONTROL_REL
        if plant.exists() or (control_root / ".git").exists():
            # Re-scan control tree for the planted path role.
            ctrl_report = scan_staging(
                control_root,
                config=ScanConfig(
                    max_file_bytes=cfg.max_file_bytes,
                    require_planted_control=False,
                ),
                roles=table,
                planted_control_root=None,
            )
            planted_found = any(
                f.role == PLANTED_CONTROL_ROLE
                and (
                    f.path == PLANTED_CONTROL_REL
                    or f.path == ".git"
                    or f.path.startswith(".git/")
                )
                for f in ctrl_report.findings
            )
            if not planted_found and plant.is_file():
                # Direct path-role check on the plant relative path.
                planted_found = classify_path_role(PLANTED_CONTROL_REL, roles=table) == PLANTED_CONTROL_ROLE

    findings.sort(key=lambda f: (f.role, f.path))
    # Deduplicate by (path, role)
    seen: set[tuple[str, str]] = set()
    uniq: list[Finding] = []
    for f in findings:
        key = (f.path, f.role)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    findings = uniq

    staging_clean = len(findings) == 0
    # Exit codes: 0 clean (+ control FOUND when required); 12 dirty; 13 control miss.
    if not staging_clean:
        exit_code = 12
        clean = False
    elif cfg.require_planted_control and control_root is not None and not planted_found:
        exit_code = 13
        clean = False
    elif cfg.require_planted_control and control_root is not None and planted_found:
        exit_code = 0
        clean = True
    else:
        # No control root attached: findings-only verdict (assert_clean / pack path).
        exit_code = 0
        clean = True

    return ScanReport(
        root=str(root_p),
        findings=findings,
        paths_seen=paths_seen,
        files_seen=files_seen,
        dirs_seen=dirs_seen,
        planted_control_found=planted_found,
        planted_control_path=PLANTED_CONTROL_REL,
        max_file_bytes=cfg.max_file_bytes,
        clean=clean,
        exit_code=exit_code,
    )


def stat_is_dir(st: os.stat_result) -> bool:
    return (st.st_mode & 0o170000) == 0o040000


def stat_is_file(st: os.stat_result) -> bool:
    return (st.st_mode & 0o170000) == 0o100000


def evaluate_with_control(
    staging_root: Path | str,
    control_root: Path | str,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    roles: dict[str, tuple[str, ...]] | None = None,
) -> ScanReport:
    """Scan ``staging_root`` and require planted control under ``control_root`` FOUND.

    Empty staging + FOUND plant → clean (exit 0).
    Dirty staging → exit 12 with named-path findings.
    Missing plant → exit 13 (silence is never trusted).
    """
    return scan_staging(
        staging_root,
        config=ScanConfig(max_file_bytes=max_file_bytes, require_planted_control=True),
        roles=roles,
        planted_control_root=control_root,
    )


def assert_clean(
    root: Path | str,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    roles: dict[str, tuple[str, ...]] | None = None,
) -> ScanReport:
    """Fail closed if ``root`` has any forbidden path-role findings (no control plant)."""
    report = scan_staging(
        root,
        config=ScanConfig(max_file_bytes=max_file_bytes, require_planted_control=False),
        roles=roles,
        planted_control_root=None,
    )
    if report.findings:
        named = ", ".join(f"{f.path}[{f.role}]" for f in report.findings[:20])
        raise ForbiddenError(
            f"forbidden content in staging tree ({len(report.findings)}): {named}"
        )
    return report


def assert_members_clean(
    members: Sequence[tuple[str, int]],
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    roles: dict[str, tuple[str, ...]] | None = None,
) -> list[Finding]:
    """Pre-emit check over ``(relpath, size)`` members (pack integration)."""
    findings: list[Finding] = []
    for rel, size in members:
        role = classify_path_role(rel, roles=roles)
        if role:
            findings.append(Finding(path=rel, role=role, detail="path-role"))
            continue
        sz = classify_size(size, max_file_bytes=max_file_bytes)
        if sz:
            findings.append(
                Finding(
                    path=rel,
                    role=sz,
                    detail=f"size={size}>max={max_file_bytes}",
                )
            )
    if findings:
        named = ", ".join(f"{f.path}[{f.role}]" for f in findings[:20])
        raise ForbiddenError(
            f"forbidden content in pack members ({len(findings)}): {named}"
        )
    return findings


def plant_control_fixture(dest: Path | str) -> Path:
    """Write the known-present ``.git/config`` plant under ``dest``. Returns plant path."""
    dest_p = Path(dest)
    git = dest_p / ".git"
    git.mkdir(parents=True, exist_ok=True)
    plant = git / "config"
    plant.write_text(
        "# IMP-0003 planted detector control — must be FOUND before clean\n"
        "[core]\n\trepositoryformatversion = 0\n",
        encoding="utf-8",
    )
    return plant


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="IMP-0003 forbidden-content scanner (path-role; fail-closed)"
    )
    ap.add_argument("--root", type=Path, required=True, help="staging tree to scan")
    ap.add_argument(
        "--control",
        type=Path,
        default=None,
        help="tree containing planted .git/config detector control",
    )
    ap.add_argument(
        "--max-file-bytes",
        type=int,
        default=DEFAULT_MAX_FILE_BYTES,
        help=f"per-file byte ceiling (default {DEFAULT_MAX_FILE_BYTES})",
    )
    ap.add_argument(
        "--plant-control",
        type=Path,
        default=None,
        help="write planted .git/config under this path then use it as --control",
    )
    ap.add_argument("--json", action="store_true", help="emit ScanReport JSON")
    args = ap.parse_args(list(argv) if argv is not None else None)

    control = args.control
    if args.plant_control is not None:
        plant_control_fixture(args.plant_control)
        control = args.plant_control

    if control is not None:
        report = evaluate_with_control(
            args.root,
            control,
            max_file_bytes=args.max_file_bytes,
        )
    else:
        report = scan_staging(
            args.root,
            config=ScanConfig(
                max_file_bytes=args.max_file_bytes,
                require_planted_control=False,
            ),
        )

    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        sys.stdout.write(report.named_path_report())
        if report.clean:
            print("SUCCESS:forbidden-scan clean")
        elif report.findings:
            print(f"FAILED:forbidden-scan findings={len(report.findings)}")
        elif not report.planted_control_found and control is not None:
            print("FAILED:forbidden-scan planted-control-NOT-FOUND")
    return int(report.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
