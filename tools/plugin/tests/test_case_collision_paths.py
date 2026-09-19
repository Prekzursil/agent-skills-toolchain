"""IMP-0022: NFC+casefold path collision detection for payload members."""

from __future__ import annotations

import json
import subprocess
import sys
import unicodedata
import zipfile
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
import casefold_paths as cf  # noqa: E402
import pack as pack_mod  # noqa: E402


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _allowlist_doc() -> dict:
    return {
        "artifact": "payload-allowlist",
        "policy": "deny-by-default",
        "rules": [
            {"glob": "schema/*.schema.json", "reason": "schemas"},
            {"glob": "bin/*.py", "reason": "bin"},
            {"glob": "README.md", "reason": "docs"},
            {"glob": "readme.md", "reason": "docs-case-variant (planted)"},
            {"glob": "LICENSE", "reason": "license"},
        ],
        "budget": {"max_bytes": 1_000_000, "max_files": 50},
        "forbidden_classes": {"vcs": [".git", ".git/*"]},
    }


def _init_clean_repo(tmp: Path) -> Path:
    repo = tmp / "payload-clean"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "imp0022@test.invalid")
    _git(repo, "config", "user.name", "IMP-0022")
    (repo / "schema").mkdir()
    (repo / "bin").mkdir()
    (repo / "schema" / "a.schema.json").write_text('{"id":"a"}\n', encoding="utf-8")
    (repo / "bin" / "tool.py").write_text("print(1)\n", encoding="utf-8")
    (repo / "README.md").write_text("# demo\n", encoding="utf-8")
    (repo / "LICENSE").write_text("MIT\n", encoding="utf-8")
    allow = _allowlist_doc()
    # Clean allowlist omits the planted readme.md rule.
    allow["rules"] = [r for r in allow["rules"] if r["glob"] != "readme.md"]
    (repo / "payload-allowlist.json").write_text(
        json.dumps(allow, indent=2) + "\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "clean-payload")
    return repo


def test_no_casefold_collisions_in_payload(tmp_path: Path) -> None:
    """Catalog node: clean allowlisted payload has zero NFC+casefold collisions."""
    repo = _init_clean_repo(tmp_path)
    allow = repo / "payload-allowlist.json"
    out = tmp_path / "clean.zip"
    result = pack_mod.pack(
        repo=repo, rev="HEAD", allowlist=allow, out=out, use_real_mtimes=False
    )
    report = cf.find_casefold_collisions(result.members)
    assert report.collision_count == 0
    assert report.colliding_path_count == 0
    # Re-check the on-disk archive member names independently.
    with zipfile.ZipFile(out) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
    assert cf.find_casefold_collisions(names).collision_count == 0


def test_nfc_then_casefold_not_lower() -> None:
    """Normalisation is NFC first, then casefold — never lower() alone."""
    # NFD "cafe" + combining acute vs NFC café must share a key after NFC.
    nfd = "cafe\u0301.md"
    nfc = "caf\u00e9.md"
    assert unicodedata.normalize("NFC", nfd) == nfc
    assert not unicodedata.is_normalized("NFC", nfd)
    assert cf.casefold_key(nfd) == cf.casefold_key(nfc)
    assert cf.casefold_key(nfd) == cf.nfc_path(nfd).casefold()
    # Prove the documented step is casefold, not a bare lower of the raw path.
    assert cf.casefold_key("README.md") == "README.md".casefold()
    assert cf.casefold_key("README.md") == "readme.md"


def test_planted_readme_pair_fires_set_check() -> None:
    """NEGATIVE CONTROL (set half): README.md + readme.md share one casefold key."""
    paths = ["LICENSE", "README.md", "readme.md", "bin/tool.py"]
    report = cf.find_casefold_collisions(paths)
    assert report.collision_count == 1
    group = report.collisions[0]
    assert set(group.paths) == {"README.md", "readme.md"}
    assert group.key == "readme.md"
    with pytest.raises(cf.CasefoldCollisionError) as ei:
        cf.assert_no_casefold_collisions(paths)
    msg = str(ei.value)
    assert "README.md" in msg and "readme.md" in msg


def test_packer_refuses_planted_case_collision(tmp_path: Path) -> None:
    """Packer pre-emit must raise PackError naming both colliding paths."""
    repo = tmp_path / "payload-collide"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "imp0022@test.invalid")
    _git(repo, "config", "user.name", "IMP-0022")
    (repo / "README.md").write_text("# Upper\n", encoding="utf-8")
    # On Linux both files can coexist in the worktree / git index.
    (repo / "readme.md").write_text("# lower\n", encoding="utf-8")
    (repo / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (repo / "payload-allowlist.json").write_text(
        json.dumps(_allowlist_doc(), indent=2) + "\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "collide")
    out = tmp_path / "should-not-exist.zip"
    with pytest.raises(pack_mod.PackError) as ei:
        pack_mod.pack(
            repo=repo,
            rev="HEAD",
            allowlist=repo / "payload-allowlist.json",
            out=out,
        )
    msg = str(ei.value)
    assert "README.md" in msg and "readme.md" in msg
    assert not out.exists()


def test_extraction_count_refuses_case_sensitive_dest(tmp_path: Path) -> None:
    """Signal (2) must not invent a shortfall on a case-sensitive filesystem."""
    archive = cf.write_collision_zip(
        [("README.md", b"A"), ("readme.md", b"B")],
        tmp_path / "planted.zip",
    )
    dest = tmp_path / "extract"
    # This Linux worker is case-sensitive; require_case_insensitive must fail closed.
    if not cf.filesystem_is_case_insensitive(tmp_path):
        with pytest.raises(RuntimeError, match="case-insensitive"):
            cf.extract_and_count(archive, dest, require_case_insensitive=True)
    # When explicitly allowed (diagnostic only), both files land → shortfall 0.
    result = cf.extract_and_count(archive, dest, require_case_insensitive=False)
    assert result.archive_entry_count == 2
    if not result.case_insensitive_dest:
        assert result.extracted_file_count == 2
        assert result.shortfall == 0
        assert result.collision_shortfall_observed is False
