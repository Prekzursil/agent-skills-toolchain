#!/usr/bin/env python3
"""Line-ending policy for shipped scripts (IMP-0017).

Enforces two layers:

1. ``.gitattributes`` declares ``eol=lf`` for ``*.sh`` / ``*.ps1`` / ``*.py`` /
   ``*.md`` so checkouts normalize endings.
2. Packer-side assertion: every shipped ``*.sh`` member is scanned as **git
   blob bytes** (``git cat-file -p`` / ``git show``) for CR (``0x0D``). A
   working-tree scan is NOT accepted; ``git archive`` is forbidden (it can
   return CRLF worktree bytes on Windows).

Library + CLI. ``pack.pack`` calls :func:`assert_no_cr_in_shell_members` on
blob bytes before emit and :func:`assert_no_cr_in_packed_shells` after the
zip is written.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

#: Suffixes treated as shell scripts that must be LF-only in the shipped blob.
SHELL_SUFFIXES = (".sh",)

#: Required ``eol=lf`` patterns in ``.gitattributes`` (IMP-0017 catalog).
REQUIRED_EOL_LF_GLOBS = ("*.sh", "*.ps1", "*.py", "*.md")


class EolPolicyError(RuntimeError):
    """Fail-closed EOL policy violation."""


@dataclass
class CrFinding:
    path: str
    cr_count: int
    bytes: int
    source: str  # "blob" | "packed"

    def as_dict(self) -> dict:
        return asdict(self)


def is_shell_path(rel: str) -> bool:
    """True when ``rel`` is a shipped shell script path (POSIX, NFC-agnostic)."""
    name = rel.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return any(name.endswith(sfx) for sfx in SHELL_SUFFIXES)


def count_cr(data: bytes) -> int:
    """Count raw CR bytes (0x0D), including those inside CRLF pairs."""
    return data.count(b"\x0d")


def _git(
    repo: Path, args: Sequence[str], *, binary: bool = False
) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", str(repo), *args]
    if any(a == "archive" for a in args):
        raise EolPolicyError("git archive is forbidden; use git cat-file -p / git show")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=not binary,
        check=False,
    )


def git_cat_file_blob(repo: Path, rev: str, path: str) -> bytes:
    """Read committed blob bytes via ``git cat-file -p`` — never worktree/archive."""
    spec = f"{rev}:{path}"
    proc = _git(repo, ["cat-file", "-p", spec], binary=True)
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise EolPolicyError(f"git cat-file -p {spec!r} failed: {err}")
    out = proc.stdout
    return out if isinstance(out, (bytes, bytearray)) else out.encode()


def git_show_blob(repo: Path, rev: str, path: str) -> bytes:
    """Alternate blob reader via ``git show`` (same bytes as cat-file for blobs)."""
    spec = f"{rev}:{path}"
    proc = _git(repo, ["show", spec], binary=True)
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise EolPolicyError(f"git show {spec!r} failed: {err}")
    out = proc.stdout
    return out if isinstance(out, (bytes, bytearray)) else out.encode()


def parse_gitattributes_eol_lf(text: str) -> set[str]:
    """Return globs that declare ``eol=lf`` (ignores comments / blank lines)."""
    found: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Attributes may be space-separated; last tokens are attribute assignments.
        parts = line.split()
        if len(parts) < 2:
            continue
        glob, *attrs = parts
        for attr in attrs:
            if attr == "eol=lf" or attr.startswith("eol=lf"):
                found.add(glob)
                break
    return found


def assert_gitattributes_eol_lf(text: str) -> None:
    """Fail closed when required ``eol=lf`` globs are missing from attributes text."""
    found = parse_gitattributes_eol_lf(text)
    missing = [g for g in REQUIRED_EOL_LF_GLOBS if g not in found]
    if missing:
        raise EolPolicyError(
            "gitattributes missing eol=lf for: " + ", ".join(missing)
        )


def load_repo_gitattributes(repo: Path, rev: str = "HEAD") -> str:
    """Load ``.gitattributes`` blob text at ``rev`` (cat-file, not worktree)."""
    data = git_cat_file_blob(repo, rev, ".gitattributes")
    return data.decode("utf-8", errors="replace")


def find_cr_in_shell_members(
    members: Iterable[tuple[str, bytes]], *, source: str = "blob"
) -> list[CrFinding]:
    """Scan member blobs for CR in shell paths. Does not read the worktree."""
    findings: list[CrFinding] = []
    for rel, blob in members:
        if not is_shell_path(rel):
            continue
        n = count_cr(blob)
        if n:
            findings.append(
                CrFinding(path=rel, cr_count=n, bytes=len(blob), source=source)
            )
    return findings


def assert_no_cr_in_shell_members(
    members: Iterable[tuple[str, bytes]], *, source: str = "blob"
) -> None:
    """Raise :class:`EolPolicyError` if any shipped ``.sh`` blob contains CR."""
    findings = find_cr_in_shell_members(members, source=source)
    if findings:
        detail = "; ".join(
            f"{f.path} cr={f.cr_count} ({f.source})" for f in findings
        )
        raise EolPolicyError(f"CRLF/CR forbidden in shipped shell blobs: {detail}")


def scan_shipped_shell_blobs(
    repo: Path,
    rev: str,
    paths: Sequence[str],
    *,
    reader: str = "cat-file",
) -> list[CrFinding]:
    """Byte-scan listed paths as blobs (cat-file or show). Paths are git paths."""
    findings: list[CrFinding] = []
    read = git_cat_file_blob if reader == "cat-file" else git_show_blob
    for path in paths:
        if not is_shell_path(path):
            continue
        blob = read(repo, rev, path)
        n = count_cr(blob)
        if n:
            findings.append(
                CrFinding(
                    path=path, cr_count=n, bytes=len(blob), source=f"blob:{reader}"
                )
            )
    return findings


def assert_no_cr_in_shipped_shell_blobs(
    repo: Path, rev: str, paths: Sequence[str], *, reader: str = "cat-file"
) -> int:
    """Assert zero CR in shipped shell blobs. Returns number of shells scanned."""
    shells = [p for p in paths if is_shell_path(p)]
    findings = scan_shipped_shell_blobs(repo, rev, shells, reader=reader)
    if findings:
        detail = "; ".join(f"{f.path} cr={f.cr_count}" for f in findings)
        raise EolPolicyError(
            f"CR found in shipped shell blobs via git {reader}: {detail}"
        )
    return len(shells)


def scan_packed_shells(archive: Path | str) -> list[CrFinding]:
    """Signal (2): scan ``.sh`` members inside a packed zip (extracted bytes)."""
    findings: list[CrFinding] = []
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            if name.endswith("/") or not is_shell_path(name):
                continue
            data = zf.read(name)
            n = count_cr(data)
            if n:
                findings.append(
                    CrFinding(
                        path=name, cr_count=n, bytes=len(data), source="packed"
                    )
                )
    return findings


def assert_no_cr_in_packed_shells(archive: Path | str) -> int:
    """Post-emit assertion: packed ``.sh`` members must contain zero CR bytes."""
    findings = scan_packed_shells(archive)
    if findings:
        detail = "; ".join(f"{f.path} cr={f.cr_count}" for f in findings)
        raise EolPolicyError(f"CR found in packed shell members: {detail}")
    with zipfile.ZipFile(archive) as zf:
        return sum(1 for n in zf.namelist() if is_shell_path(n) and not n.endswith("/"))


_ATTR_SH_LF_RE = re.compile(r"(?m)^\s*\*\.sh\s+.*\beol=lf\b")


def gitattributes_has_sh_eol_lf(text: str) -> bool:
    return _ATTR_SH_LF_RE.search(text) is not None


def mutate_remove_sh_eol_lf(text: str) -> str:
    """MUTATION helper: strip ``*.sh … eol=lf`` lines from attributes text."""
    lines = []
    for raw in text.splitlines(keepends=True):
        stripped = raw.strip()
        if stripped.startswith("#") or not stripped:
            lines.append(raw)
            continue
        parts = stripped.split()
        if parts and parts[0] == "*.sh" and any(a.startswith("eol=") for a in parts[1:]):
            continue
        lines.append(raw)
    return "".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="IMP-0017 EOL policy (blob / packed)")
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument(
        "--check-gitattributes",
        action="store_true",
        help="assert required eol=lf globs via cat-file of .gitattributes",
    )
    ap.add_argument(
        "--scan-blobs",
        nargs="*",
        default=None,
        help="git paths to scan as blobs for CR (shell only)",
    )
    ap.add_argument(
        "--scan-zip",
        type=Path,
        default=None,
        help="packed zip to scan for CR in .sh members",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)
    report: dict = {"ok": True, "findings": []}
    try:
        if args.check_gitattributes:
            text = load_repo_gitattributes(args.repo, args.rev)
            assert_gitattributes_eol_lf(text)
            report["gitattributes_ok"] = True
            report["eol_lf_globs"] = sorted(parse_gitattributes_eol_lf(text))
        if args.scan_blobs is not None:
            paths = list(args.scan_blobs)
            n = assert_no_cr_in_shipped_shell_blobs(args.repo, args.rev, paths)
            report["shells_scanned"] = n
        if args.scan_zip is not None:
            n = assert_no_cr_in_packed_shells(args.scan_zip)
            report["packed_shells_scanned"] = n
    except EolPolicyError as exc:
        report["ok"] = False
        report["error"] = str(exc)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(f"FAILED:eol-policy {exc}", file=sys.stderr)
        return 12
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("SUCCESS:eol-policy " + json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
