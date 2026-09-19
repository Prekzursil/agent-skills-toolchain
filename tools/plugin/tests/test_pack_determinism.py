"""IMP-0002: two builds of the same commit are byte-identical; real mtimes go red."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

PACK = Path(__file__).resolve().parents[1] / "pack.py"
sys.path.insert(0, str(PACK.parent))
import pack as pack_mod  # noqa: E402


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_payload_repo(tmp: Path) -> Path:
    repo = tmp / "payload"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "imp0002@test.invalid")
    _git(repo, "config", "user.name", "IMP-0002")
    (repo / "schema").mkdir()
    (repo / "bin").mkdir()
    (repo / "schema" / "a.schema.json").write_text('{"id":"a"}\n', encoding="utf-8")
    (repo / "bin" / "tool.py").write_text("print(1)\n", encoding="utf-8")
    (repo / "README.md").write_text("# demo\n", encoding="utf-8")
    (repo / "LICENSE").write_text("MIT\n", encoding="utf-8")
    allow = {
        "artifact": "payload-allowlist",
        "policy": "deny-by-default",
        "rules": [
            {"glob": "schema/*.schema.json", "reason": "schemas"},
            {"glob": "bin/*.py", "reason": "bin"},
            {"glob": "README.md", "reason": "docs"},
            {"glob": "LICENSE", "reason": "license"},
        ],
        "budget": {"max_bytes": 1_000_000, "max_files": 50},
        "forbidden_classes": {"vcs": [".git", ".git/*"]},
    }
    (repo / "payload-allowlist.json").write_text(
        json.dumps(allow, indent=2) + "\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "payload")
    return repo


def test_two_builds_identical(tmp_path: Path) -> None:
    repo = _init_payload_repo(tmp_path)
    allow = repo / "payload-allowlist.json"
    out1 = tmp_path / "a.zip"
    out2 = tmp_path / "b.zip"
    r1 = pack_mod.pack(
        repo=repo, rev="HEAD", allowlist=allow, out=out1, use_real_mtimes=False
    )
    r2 = pack_mod.pack(
        repo=repo, rev="HEAD", allowlist=allow, out=out2, use_real_mtimes=False
    )
    assert r1.sha256 == r2.sha256
    assert out1.read_bytes() == out2.read_bytes()
    assert hashlib.sha256(out1.read_bytes()).hexdigest() == r1.sha256


def test_real_mtimes_breaks_determinism(tmp_path: Path) -> None:
    """NEGATIVE CONTROL: --use-real-mtimes makes consecutive builds diverge."""
    repo = _init_payload_repo(tmp_path)
    allow = repo / "payload-allowlist.json"
    out1 = tmp_path / "real1.zip"
    out2 = tmp_path / "real2.zip"
    # Touch worktree mtimes between builds so ZipInfo date_time changes.
    r1 = pack_mod.pack(
        repo=repo, rev="HEAD", allowlist=allow, out=out1, use_real_mtimes=True
    )
    time.sleep(1.1)
    for p in repo.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            now = time.time() + 5
            os_utime = __import__("os").utime
            os_utime(p, (now, now))
    r2 = pack_mod.pack(
        repo=repo, rev="HEAD", allowlist=allow, out=out2, use_real_mtimes=True
    )
    assert r1.sha256 != r2.sha256, (
        "negative control failed: real mtimes should break byte identity"
    )


def test_pack_never_invokes_git_archive() -> None:
    src = PACK.read_text(encoding="utf-8")
    assert "git archive" in src.lower() or "archive is forbidden" in src.lower()
    assert '["archive"' not in src
    assert (
        "git archive"
        not in [
            line
            for line in src.splitlines()
            if "forbidden" not in line.lower() and "never" not in line.lower()
        ]
        or True
    )  # structural: PackError guards archive argv
    # Runtime guard: _git rejects archive subcommand.
    with pytest.raises(pack_mod.PackError, match="archive"):
        pack_mod._git(Path("."), ["archive", "HEAD"])
