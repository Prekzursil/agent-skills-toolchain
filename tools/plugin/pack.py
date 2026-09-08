#!/usr/bin/env python3
"""Deterministic reproducible packer (IMP-0002).

Two builds of the same commit must produce byte-identical archives:

* members are sorted by NFC-normalised path;
* mtime/uid/gid/mode bits are fixed (zip epoch) unless ``--use-real-mtimes``;
* compression level is pinned;
* file bytes come from ``git cat-file -p <rev>:<path>`` — never ``git archive``
  (Windows/export CRLF worktree bug).

Library + CLI. Negative-control flag ``--use-real-mtimes`` re-enables real
timestamps so determinism tests can go red on purpose.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import casefold_paths as casefold_mod
import eol_policy as eol_policy_mod
import forbidden as forbidden_mod
import size_budget as size_budget_mod

#: Zip format minimum timestamp. Fixed so identical content → identical bytes.
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
COMPRESS_LEVEL = 9
DEFAULT_ALLOWLIST = Path(__file__).resolve().parent / "payload-allowlist.json"
FIXED_MODE = 0o644
#: Per-file ceiling for IMP-0003 pre-emit path-role scanner (not total budget).
DEFAULT_MAX_FILE_BYTES = forbidden_mod.DEFAULT_MAX_FILE_BYTES


class PackError(RuntimeError):
    """Fail-closed packer error."""


def nfc(path: str) -> str:
    """NFC path unify — delegates to IMP-0022 helper (separator + NFC only)."""
    return casefold_mod.nfc_path(path)


def glob_to_re(pattern: str) -> re.Pattern[str]:
    """Map allowlist globs to regex. ``*`` is slash-segment (``[^/]*``); ``**`` refused."""
    if "**" in pattern:
        raise PackError(f"recursive glob '**' is forbidden in allowlist: {pattern!r}")
    if pattern.startswith("/") or "\\" in pattern or "/../" in f"/{pattern}/":
        raise PackError(f"unsafe allowlist glob: {pattern!r}")
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            parts.append("[^/]*")
        elif ch == "?":
            parts.append("[^/]")
        elif ch in ".^$+{}[]|()\\":
            parts.append("\\" + ch)
        else:
            parts.append(ch)
        i += 1
    return re.compile("^" + "".join(parts) + "$")


def load_allowlist(path: Path | str) -> dict:
    p = Path(path)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackError(f"cannot load allowlist {p}: {exc}") from exc
    if doc.get("artifact") != "payload-allowlist":
        raise PackError("allowlist artifact field must be 'payload-allowlist'")
    if doc.get("policy") != "deny-by-default":
        raise PackError("allowlist policy must be deny-by-default")
    rules = doc.get("rules")
    if not isinstance(rules, list) or not rules:
        raise PackError("allowlist rules must be a non-empty list")
    return doc


def compile_rules(doc: dict) -> list[tuple[str, re.Pattern[str], str]]:
    out: list[tuple[str, re.Pattern[str], str]] = []
    for rule in doc["rules"]:
        glob = rule["glob"]
        out.append((glob, glob_to_re(glob), rule.get("reason", "")))
    return out


def match_rule(
    rel: str, rules: Sequence[tuple[str, re.Pattern[str], str]]
) -> str | None:
    rel_n = nfc(rel)
    for glob, rx, _ in rules:
        if rx.match(rel_n):
            return glob
    return None


def expand_members(
    candidates: Iterable[str], rules: Sequence[tuple[str, re.Pattern[str], str]]
) -> list[str]:
    """Select allowlisted paths, NFC-normalise, sort stably."""
    selected: set[str] = set()
    for raw in candidates:
        rel = nfc(raw)
        if match_rule(rel, rules) is None:
            continue
        selected.add(rel)
    return sorted(selected)


def _git(
    repo: Path, args: Sequence[str], *, binary: bool = False
) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", str(repo), *args]
    if any(a == "archive" for a in args):
        raise PackError("git archive is forbidden; use git cat-file -p")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=not binary,
        check=False,
    )


def git_ls_tree(repo: Path, rev: str, prefix: str = "") -> list[str]:
    """List blob paths at ``rev``. If ``prefix`` set, return paths relative to it."""
    proc = _git(repo, ["ls-tree", "-r", "--name-only", "-z", rev])
    if proc.returncode != 0:
        raise PackError(
            f"git ls-tree failed: {(proc.stderr or proc.stdout or '').strip()}"
        )
    raw = proc.stdout or ""
    paths = [p for p in raw.split("\0") if p]
    prefix = prefix.replace("\\", "/").rstrip("/")
    out: list[str] = []
    for p in paths:
        p = p.replace("\\", "/")
        if prefix:
            if p == prefix or not p.startswith(prefix + "/"):
                continue
            out.append(p[len(prefix) + 1 :])
        else:
            out.append(p)
    return out


def git_cat_file(repo: Path, rev: str, path: str) -> bytes:
    """Read blob bytes at ``rev:path``. Never uses git archive."""
    spec = f"{rev}:{path}"
    proc = _git(repo, ["cat-file", "-p", spec], binary=True)
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise PackError(f"git cat-file -p {spec!r} failed: {err}")
    return (
        proc.stdout
        if isinstance(proc.stdout, (bytes, bytearray))
        else proc.stdout.encode()
    )


def _zip_datetime_from_epoch(ts: float) -> tuple[int, int, int, int, int, int]:
    lt = time.localtime(ts)
    # zip requires year >= 1980
    year = max(lt.tm_year, 1980)
    return (year, lt.tm_mon, lt.tm_mday, lt.tm_hour, lt.tm_min, lt.tm_sec)


def write_zip_bytes(
    members: Sequence[tuple[str, bytes]],
    *,
    use_real_mtimes: bool = False,
    mtime_lookup: dict[str, float] | None = None,
) -> bytes:
    """Write a deterministic (or deliberately non-deterministic) zip to bytes."""
    bio = io.BytesIO()
    with zipfile.ZipFile(
        bio, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=COMPRESS_LEVEL
    ) as zf:
        for rel, blob in members:
            if use_real_mtimes:
                ts = (mtime_lookup or {}).get(rel, time.time())
                date_time = _zip_datetime_from_epoch(ts)
            else:
                date_time = ZIP_EPOCH
            info = zipfile.ZipInfo(filename=nfc(rel), date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # unix
            info.external_attr = FIXED_MODE << 16
            # Explicit zero uid/gid via create_version / flag bits already fixed;
            # standard ZipInfo does not emit uid/gid extras unless set.
            zf.writestr(info, blob)
    return bio.getvalue()


@dataclass
class PackResult:
    archive: Path
    sha256: str
    size_bytes: int
    members: list[str]
    rev: str
    budget: dict | None = None

    def as_dict(self) -> dict:
        d = {
            "archive": str(self.archive),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "member_count": len(self.members),
            "members": list(self.members),
            "rev": self.rev,
        }
        if self.budget is not None:
            d["budget"] = self.budget
        return d


def pack(
    *,
    repo: Path,
    rev: str = "HEAD",
    allowlist: Path | None = None,
    out: Path,
    prefix: str = "",
    use_real_mtimes: bool = False,
    max_file_bytes: int | None = None,
    skip_forbidden_scan: bool = False,
    skip_budget_check: bool = False,
    max_bytes: int | None = None,
    max_files: int | None = None,
) -> PackResult:
    """Expand allowlist against ``rev``, pack zip from ``git cat-file`` blob bytes.

    Pre-emit (IMP-0003): every selected member is classified by path role and
    per-file byte ceiling before any archive bytes are written.

    Post-emit (IMP-0005): declared max-bytes / max-file-count budget is enforced
    against the written archive; totals come from the budget checker, not a
    tautological copy of caller-supplied size.

    EOL (IMP-0017): every shipped ``*.sh`` member must contain zero CR bytes in
    the git blob and again in the packed zip (cat-file bytes, never archive).
    """
    repo = Path(repo).resolve()
    allowlist = Path(allowlist) if allowlist else DEFAULT_ALLOWLIST
    doc = load_allowlist(allowlist)
    rules = compile_rules(doc)
    candidates = git_ls_tree(repo, rev, prefix=prefix)
    members = expand_members(candidates, rules)
    if not members:
        raise PackError("no allowlisted members at this revision")

    # IMP-0022: refuse NFC+casefold collisions before any archive bytes exist.
    try:
        casefold_mod.assert_no_casefold_collisions(members)
    except casefold_mod.CasefoldCollisionError as exc:
        raise PackError(str(exc)) from exc

    ceiling = DEFAULT_MAX_FILE_BYTES if max_file_bytes is None else int(max_file_bytes)

    prefix_n = prefix.replace("\\", "/").rstrip("/")
    blobs: list[tuple[str, bytes]] = []
    mtimes: dict[str, float] = {}
    for rel in members:
        git_path = f"{prefix_n}/{rel}" if prefix_n else rel
        blob = git_cat_file(repo, rev, git_path)
        blobs.append((rel, blob))
        if use_real_mtimes:
            work = repo / git_path
            try:
                mtimes[rel] = work.stat().st_mtime
            except OSError:
                mtimes[rel] = time.time()

    if not skip_forbidden_scan:
        try:
            forbidden_mod.assert_members_clean(
                [(rel, len(blob)) for rel, blob in blobs],
                max_file_bytes=ceiling,
            )
        except forbidden_mod.ForbiddenError as exc:
            raise PackError(str(exc)) from exc

    # IMP-0017: refuse CRLF/CR shell blobs before any archive bytes exist.
    try:
        eol_policy_mod.assert_no_cr_in_shell_members(blobs, source="blob")
    except eol_policy_mod.EolPolicyError as exc:
        raise PackError(str(exc)) from exc

    raw = write_zip_bytes(blobs, use_real_mtimes=use_real_mtimes, mtime_lookup=mtimes)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)

    # IMP-0017 signal (2): re-scan extracted packed .sh bytes (not worktree).
    try:
        eol_policy_mod.assert_no_cr_in_packed_shells(out)
    except eol_policy_mod.EolPolicyError as exc:
        try:
            out.unlink()
        except OSError:
            pass
        raise PackError(str(exc)) from exc

    budget_info: dict | None = None
    if not skip_budget_check:
        try:
            if max_bytes is None or max_files is None:
                mb, mf = size_budget_mod.load_budget(doc)
                if max_bytes is None:
                    max_bytes = mb
                if max_files is None:
                    max_files = mf
            totals = size_budget_mod.check_budget(
                out, max_bytes=int(max_bytes), max_files=int(max_files)
            )
        except size_budget_mod.BudgetError as exc:
            try:
                out.unlink()
            except OSError:
                pass
            raise PackError(f"budget: {exc}") from exc
        budget_info = totals.as_dict()

    return PackResult(
        archive=out,
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        members=[m for m, _ in blobs],
        rev=rev,
        budget=budget_info,
    )


def archive_sha256(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Deterministic packer (git cat-file blob bytes; never git archive)"
    )
    ap.add_argument("--repo", type=Path, default=Path("."), help="git repository root")
    ap.add_argument("--rev", default="HEAD", help="git revision to pack (default HEAD)")
    ap.add_argument(
        "--allowlist",
        type=Path,
        default=DEFAULT_ALLOWLIST,
        help="payload-allowlist.json path",
    )
    ap.add_argument("--out", type=Path, required=True, help="output .zip path")
    ap.add_argument(
        "--prefix",
        default="",
        help="optional git path prefix; stripped for allowlist/archive member names",
    )
    ap.add_argument(
        "--use-real-mtimes",
        action="store_true",
        help="NEGATIVE CONTROL: stamp real mtimes (breaks byte-identical rebuilds)",
    )
    ap.add_argument("--json", action="store_true", help="print PackResult as JSON")
    args = ap.parse_args(list(argv) if argv is not None else None)
    try:
        result = pack(
            repo=args.repo,
            rev=args.rev,
            allowlist=args.allowlist,
            out=args.out,
            prefix=args.prefix,
            use_real_mtimes=args.use_real_mtimes,
        )
    except PackError as exc:
        print(f"FAILED:pack {exc}", file=sys.stderr)
        return 11
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    else:
        print(
            f"SUCCESS:pack members={len(result.members)} "
            f"sha256={result.sha256} archive={result.archive}"
        )
    return 0


if __name__ == "__main__":
    # Refuse accidental import-time use of git archive via env (belt + suspenders).
    if os.environ.get("IMP0002_FORCE_GIT_ARCHIVE") == "1":
        raise SystemExit("git archive is forbidden by IMP-0002")
    raise SystemExit(main())
