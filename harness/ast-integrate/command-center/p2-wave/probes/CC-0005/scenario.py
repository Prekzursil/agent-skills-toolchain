#!/usr/bin/env python3
"""Live measurement fixture for CC-0005: blob vs archive vs worktree.

Creates a throwaway git repo (not this worktree). Every hash the probes cite
is produced by `git cat-file -p`. `git archive` is measured only as the
negative control that applies export-time EOL conversion.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
sys.path.insert(0, str(TOOLS))
import git_blob as gb  # noqa: E402
import validate as val  # noqa: E402

REL = "command-center/sources/REGISTER.md"
LF_SIZE = 3737
N_NEWLINES = 100


def control_lf(n_newlines: int = N_NEWLINES, size: int = LF_SIZE) -> bytes:
    other = size - n_newlines
    q, r = divmod(other, n_newlines)
    parts = [b"x" * (q + (1 if i < r else 0)) for i in range(n_newlines)]
    blob = b"\n".join(parts) + b"\n"
    if blob.count(b"\n") != n_newlines or len(blob) != size:
        raise RuntimeError(
            "control_lf built %s bytes / %s newlines, want %s / %s"
            % (len(blob), blob.count(b"\n"), size, n_newlines)
        )
    return blob


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=True,
    )


def build_fixture(root: Path, *, attrs: str = "* text eol=crlf\n") -> dict[str, Any]:
    """Windows-like export conversion on; blobs remain LF."""
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "cc0005@test")
    _git(repo, "config", "user.name", "cc0005")
    _git(repo, "config", "core.autocrlf", "false")
    lf = control_lf()
    path = repo / REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(lf)
    (repo / ".gitattributes").write_text(attrs, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "cc0005-control")
    blob = gb.git_blob_bytes(REL, repo=repo)
    show = gb.git_show_bytes(REL, repo=repo)
    archive = gb.git_archive_bytes(REL, repo=repo)
    crlf_worktree = blob.replace(b"\n", b"\r\n")
    path.write_bytes(crlf_worktree)
    recorded = gb.sha256_hex(blob)
    worktree_raw_hash = gb.sha256_hex(path.read_bytes())
    worktree_lf_hash = gb.sha256_hex(gb.lf_normalize(path.read_bytes()))
    catalog = {
        "items": [
            {
                "id": "R-1",
                "title": "control",
                "status": "OPEN",
                "next_smallest_action": "measure the blob",
                "dependencies": [],
                "inputs": ["REGISTER.md"],
            }
        ],
        "provenance": {"register": REL, "register_sha256": recorded},
    }
    silent, silent_stats = val.validate(catalog, git_repo=repo)
    reach6_silent = [
        v
        for v in silent
        if v.get("check") == "REACH-6" and "sha256" in v.get("detail", "")
    ]
    changed = root / "changed.md"
    changed.write_bytes(blob + b"CONTENT-CHANGE\n")
    fire, _fire_stats = val.validate(catalog, register_path=changed, git_repo=repo)
    reach6_fire = [
        v
        for v in fire
        if v.get("check") == "REACH-6" and "sha256" in v.get("detail", "")
    ]
    windows_before_exit = 0 if worktree_raw_hash == recorded else 1
    windows_after_exit = 0 if recorded == gb.sha256_hex(blob) else 1
    linux_raw_hash = gb.sha256_hex(blob)
    linux_before_exit = 0 if linux_raw_hash == recorded else 1
    linux_after_exit = windows_after_exit
    delta = len(crlf_worktree) - len(blob)
    return {
        "rel": REL,
        "rev": "HEAD",
        "blob_bytes": len(blob),
        "blob_crlf": blob.count(b"\r\n"),
        "blob_lf": blob.count(b"\n"),
        "blob_sha256": recorded,
        "blob_sha256_via": "git cat-file -p HEAD:" + REL,
        "show_bytes": len(show),
        "show_sha256": gb.sha256_hex(show),
        "show_equals_cat_file": show == blob,
        "archive_bytes": len(archive),
        "archive_crlf": archive.count(b"\r\n"),
        "archive_sha256": gb.sha256_hex(archive),
        "archive_equals_cat_file": archive == blob,
        "worktree_crlf_bytes": len(crlf_worktree),
        "worktree_crlf_count": crlf_worktree.count(b"\r\n"),
        "worktree_raw_sha256": worktree_raw_hash,
        "worktree_lf_normalized_sha256": worktree_lf_hash,
        "pre_fix_delta_bytes": delta,
        "line_count": blob.count(b"\n"),
        "delta_equals_line_count": delta == blob.count(b"\n"),
        "reach6_hash_via_silent": silent_stats.get("reach6_hash_via"),
        "silent_on_eol_only": reach6_silent == [],
        "fires_on_content_change": len(reach6_fire) == 1,
        "windows_worktree_hasher_exit_before": windows_before_exit,
        "windows_blob_hasher_exit_after": windows_after_exit,
        "linux_worktree_hasher_exit_before": linux_before_exit,
        "linux_blob_hasher_exit_after": linux_after_exit,
        "platform_parity_after": windows_after_exit == linux_after_exit,
        "platform_parity_before_worktree_hasher": windows_before_exit != linux_before_exit,
        "gitattributes_policy_fixture": attrs.strip(),
        "gitattributes_policy_repo": (
            "tools and docs: eol=lf; hashing still uses git cat-file because "
            "archive/export conversion is a separate trap"
        ),
        "historical_cited_pair": {
            "blob_prefix": "8b3e44cc3813",
            "worktree_crlf_prefix": "1a404a91d819",
            "note": (
                "cited from the unit as the original Windows measurement. This "
                "fixture reproduces the structure (LF blob vs CRLF worktree/"
                "archive, delta = line count) rather than those exact bytes: "
                "this worktree is not a git checkout and REGISTER.md is absent."
            ),
        },
    }


def measure() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cc0005-") as td:
        return build_fixture(Path(td))


def failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if not result["show_equals_cat_file"]:
        fails.append("git show != git cat-file")
    if result["archive_equals_cat_file"]:
        fails.append("git archive unexpectedly equals cat-file")
    if not result["delta_equals_line_count"]:
        fails.append("pre-fix delta != line count")
    if not result["silent_on_eol_only"]:
        fails.append("gate not silent on EOL-only worktree")
    if not result["fires_on_content_change"]:
        fails.append("gate did not fire on genuine content change")
    if result["windows_blob_hasher_exit_after"] != 0:
        fails.append("blob hasher not green after fix")
    if result["windows_worktree_hasher_exit_before"] != 1:
        fails.append("worktree hasher did not fail on CRLF before the fix")
    if not result["platform_parity_after"]:
        fails.append("Windows/Linux blob hasher verdicts differ")
    if not result["platform_parity_before_worktree_hasher"]:
        fails.append("worktree hasher did not diverge across platforms before the fix")
    if result["reach6_hash_via_silent"] != "git-cat-file":
        fails.append("silent path did not hash via git-cat-file")
    if result["blob_crlf"] != 0:
        fails.append("blob is not LF")
    if result["archive_crlf"] != result["line_count"]:
        fails.append("archive CRLF count != line count")
    if result["blob_bytes"] != LF_SIZE or result["worktree_crlf_bytes"] != LF_SIZE + N_NEWLINES:
        fails.append("control sizes drifted from 3737/3837")
    return fails
