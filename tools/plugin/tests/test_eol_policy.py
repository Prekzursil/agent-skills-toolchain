"""IMP-0017: line-ending policy — blob CR gate + gitattributes + packer refuse.

Catalog nodes:
* test_no_cr_in_shipped_shell_blobs — HEAD blob byte-scan (cat-file), not worktree
* NEGATIVE CONTROL — CRLF shell blob → packer refuses
* MUTATION — remove ``*.sh eol=lf`` from attributes → rule check goes red
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
REPO = PLUGIN.parents[1]
sys.path.insert(0, str(PLUGIN))
import eol_policy as eol  # noqa: E402
import pack as pack_mod  # noqa: E402


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
    )


def _init_shell_repo(tmp: Path, *, shell_bytes: bytes) -> Path:
    """Fixture payload repo with a committed shell blob (literal bytes)."""
    repo = tmp / "payload"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "imp0017@test.invalid")
    _git(repo, "config", "user.name", "IMP-0017")
    # Disable conversion so we can plant a CRLF blob when needed.
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "config", "core.eol", "lf")
    (repo / "bin").mkdir()
    sh = repo / "bin" / "tool.sh"
    sh.write_bytes(shell_bytes)
    (repo / "LICENSE").write_bytes(b"MIT\n")
    (repo / ".gitattributes").write_text(
        "*.sh eol=lf\n*.ps1 eol=lf\n*.py eol=lf\n*.md eol=lf\n",
        encoding="utf-8",
    )
    allow = {
        "artifact": "payload-allowlist",
        "policy": "deny-by-default",
        "rules": [
            {"glob": "bin/*.sh", "reason": "shell"},
            {"glob": "LICENSE", "reason": "license"},
        ],
        "budget": {"max_bytes": 100_000, "max_files": 20},
        "forbidden_classes": {"vcs": [".git", ".git/*"]},
    }
    (repo / "payload-allowlist.json").write_text(
        json.dumps(allow, indent=2) + "\n", encoding="utf-8"
    )
    # Plant blob via hash-object so attributes cannot rewrite CRLF → LF.
    digest = (
        subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=repo,
            input=shell_bytes,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    subprocess.run(
        ["git", "update-index", "--add", "--cacheinfo", f"100755,{digest},bin/tool.sh"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    _git(repo, "add", "LICENSE", ".gitattributes", "payload-allowlist.json")
    _git(repo, "commit", "-m", "shell-payload")
    return repo


def test_no_cr_in_shipped_shell_blobs() -> None:
    """Catalog node: every shipped ``*.sh`` at HEAD has zero CR in the blob."""
    # Signal (1): cat-file blob bytes — never worktree read for the gate.
    attrs = eol.load_repo_gitattributes(REPO, "HEAD")
    eol.assert_gitattributes_eol_lf(attrs)

    # Expand allowlist under tools/plugin prefix the same way the packer does.
    doc = pack_mod.load_allowlist(PLUGIN / "payload-allowlist.json")
    rules = pack_mod.compile_rules(doc)
    candidates = pack_mod.git_ls_tree(REPO, "HEAD", prefix="tools/plugin")
    members = pack_mod.expand_members(candidates, rules)
    shell_members = [m for m in members if eol.is_shell_path(m)]
    assert shell_members, "allowlist must ship at least one .sh (IMP-0017 fixture)"

    git_paths = [f"tools/plugin/{m}" for m in shell_members]
    scanned = eol.assert_no_cr_in_shipped_shell_blobs(
        REPO, "HEAD", git_paths, reader="cat-file"
    )
    assert scanned == len(shell_members)

    # Cross-check via git show (still blob bytes, not archive).
    scanned_show = eol.assert_no_cr_in_shipped_shell_blobs(
        REPO, "HEAD", git_paths, reader="show"
    )
    assert scanned_show == scanned

    # Explicit byte proof: cat-file of the sample script has no 0x0D.
    blob = eol.git_cat_file_blob(REPO, "HEAD", "tools/plugin/bin/astplugin-ok.sh")
    assert b"\x0d" not in blob
    assert blob.startswith(b"#!/")


def test_negative_control_packer_refuses_crlf_shell_blob(tmp_path: Path) -> None:
    """NEGATIVE CONTROL: CRLF shell blob → pack raises PackError / refuses."""
    crlf = b"#!/usr/bin/env bash\r\necho hi\r\n"
    assert b"\r\n" in crlf
    repo = _init_shell_repo(tmp_path, shell_bytes=crlf)

    # Prove the BLOB (not worktree) carries CR.
    blob = pack_mod.git_cat_file(repo, "HEAD", "bin/tool.sh")
    assert b"\x0d" in blob

    out = tmp_path / "out.zip"
    with pytest.raises(pack_mod.PackError, match=r"CRLF/CR forbidden|CR found"):
        pack_mod.pack(
            repo=repo,
            rev="HEAD",
            allowlist=repo / "payload-allowlist.json",
            out=out,
        )
    # Pre-emit refusal: no successful archive should remain.
    assert not out.is_file()


def test_negative_control_lf_shell_packs_clean(tmp_path: Path) -> None:
    """Good-state twin: LF shell blob packs and packed zip has zero CR."""
    lf = b"#!/usr/bin/env bash\necho hi\n"
    repo = _init_shell_repo(tmp_path, shell_bytes=lf)
    out = tmp_path / "clean.zip"
    result = pack_mod.pack(
        repo=repo,
        rev="HEAD",
        allowlist=repo / "payload-allowlist.json",
        out=out,
    )
    assert "bin/tool.sh" in result.members
    assert eol.assert_no_cr_in_packed_shells(out) >= 1


def test_mutation_remove_gitattributes_sh_rule_detected() -> None:
    """MUTATION: delete ``*.sh eol=lf`` → gitattributes assertion goes red."""
    text = eol.load_repo_gitattributes(REPO, "HEAD")
    eol.assert_gitattributes_eol_lf(text)  # healthy

    mutated = eol.mutate_remove_sh_eol_lf(text)
    assert not eol.gitattributes_has_sh_eol_lf(mutated)
    with pytest.raises(eol.EolPolicyError, match=r"\*\.sh"):
        eol.assert_gitattributes_eol_lf(mutated)


def test_blob_reader_forbids_git_archive(tmp_path: Path) -> None:
    """Reviewer residual: gate path must refuse git archive."""
    repo = _init_shell_repo(tmp_path, shell_bytes=b"#!/bin/sh\ntrue\n")
    with pytest.raises(eol.EolPolicyError, match="archive is forbidden"):
        eol._git(repo, ["archive", "HEAD"])
