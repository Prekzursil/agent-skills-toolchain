"""IMP-0003: forbidden-content scanner — one case per path-role class.

NEGATIVE CONTROL: empty staging → clean AND planted-item control FOUND same run.
MUTATION: delete the .git rule → suite goes red (classifier misses .git/config).
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
import forbidden as F  # noqa: E402


def _write(p: Path, text: str = "x\n") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_class_git_directory(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    _write(stage / ".git" / "config", "[core]\n")
    report = F.scan_staging(
        stage,
        config=F.ScanConfig(require_planted_control=False),
    )
    assert any(f.role == "git" and f.path.startswith(".git") for f in report.findings)
    assert report.exit_code == 12
    assert report.clean is False


def test_class_git_gitlink_file(tmp_path: Path) -> None:
    """A FILE named .git (gitdir pointer) is a gitlink — forbidden."""
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "sub").mkdir()
    (stage / "sub" / ".git").write_text(
        "gitdir: ../.git/worktrees/sub\n", encoding="utf-8"
    )
    report = F.scan_staging(stage, config=F.ScanConfig(require_planted_control=False))
    assert any(f.role == "git" and f.path.endswith(".git") for f in report.findings)
    assert F.is_gitlink_entry(name=".git", is_dir=False, is_file=True) is True
    assert F.is_gitlink_entry(name=".git", is_dir=True, is_file=False) is False
    assert (
        F.is_gitlink_entry(name="x", is_dir=False, is_file=True, mode=0o160000) is True
    )


def test_class_node_modules(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    _write(stage / "node_modules" / "leftpad" / "index.js", "module.exports=1\n")
    report = F.scan_staging(stage, config=F.ScanConfig(require_planted_control=False))
    assert any(f.role == "node_modules" for f in report.findings)
    assert F.classify_path_role("vendor/node_modules/pkg/a.js") == "node_modules"


def test_class_pycache(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    _write(stage / "lib" / "__pycache__" / "x.cpython-312.pyc", "not-really")
    report = F.scan_staging(stage, config=F.ScanConfig(require_planted_control=False))
    assert any(f.role == "pycache" for f in report.findings)
    assert F.classify_path_role("pkg/__pycache__/m.pyc") == "pycache"


def test_class_log(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    _write(stage / "build.log", "noise\n")
    report = F.scan_staging(stage, config=F.ScanConfig(require_planted_control=False))
    assert any(f.role == "log" and f.path == "build.log" for f in report.findings)
    assert F.classify_path_role("run.log") == "log"


def test_class_transcript_jsonl(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    _write(stage / "sessions" / "agent.jsonl", '{"role":"user"}\n')
    report = F.scan_staging(stage, config=F.ScanConfig(require_planted_control=False))
    assert any(f.role == "transcript" for f in report.findings)
    assert F.classify_path_role("chat.transcript.bak") == "transcript"
    assert F.classify_path_role("session.jsonl") == "transcript"


def test_class_os_cache(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    _write(stage / ".DS_Store", "mac")
    _write(stage / ".cache" / "pip" / "wheel", "x")
    report = F.scan_staging(stage, config=F.ScanConfig(require_planted_control=False))
    roles = {f.role for f in report.findings}
    assert "os_cache" in roles
    assert F.classify_path_role("Thumbs.db") == "os_cache"
    assert F.classify_path_role("__MACOSX/._foo") == "os_cache"


def test_class_oversized_file(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    big = stage / "ok-name.bin"
    ceiling = 1024
    big.write_bytes(b"Z" * (ceiling + 1))
    report = F.scan_staging(
        stage,
        config=F.ScanConfig(max_file_bytes=ceiling, require_planted_control=False),
    )
    assert any(
        f.role == "oversized" and f.path == "ok-name.bin" for f in report.findings
    )
    assert F.classify_size(ceiling + 1, max_file_bytes=ceiling) == "oversized"
    assert F.classify_size(ceiling, max_file_bytes=ceiling) is None


def test_legitimate_paths_are_not_forbidden() -> None:
    for rel in (
        "README.md",
        "lib/astplugin/cli.py",
        "schema/payload-allowlist.schema.json",
        "bin/astplugin.py",
        "LICENSE",
    ):
        assert F.classify_path_role(rel) is None


def test_negative_control_empty_staging_clean_and_planted_found(tmp_path: Path) -> None:
    """NEGATIVE CONTROL: empty staging → clean AND planted control FOUND in same run."""
    staging = tmp_path / "empty-stage"
    staging.mkdir()
    control = tmp_path / "control"
    F.plant_control_fixture(control)

    report = F.evaluate_with_control(staging, control)
    assert report.findings == []
    assert report.planted_control_found is True
    assert report.clean is True
    assert report.exit_code == 0
    # Named-path report must mention the plant FOUND (silence is never the only signal).
    text = report.named_path_report()
    assert "planted_control_found=True" in text
    assert report.planted_control_path == ".git/config"


def test_negative_control_missing_plant_refuses_clean(tmp_path: Path) -> None:
    staging = tmp_path / "empty"
    staging.mkdir()
    control = tmp_path / "control-empty"
    control.mkdir()
    report = F.evaluate_with_control(staging, control)
    assert report.findings == []
    assert report.planted_control_found is False
    assert report.clean is False
    assert report.exit_code == 13


def test_assert_clean_raises_on_forbidden(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    _write(stage / "x.log", "x")
    with pytest.raises(F.ForbiddenError, match="forbidden content"):
        F.assert_clean(stage)


def test_assert_members_clean_pack_preemit() -> None:
    F.assert_members_clean([("README.md", 10), ("bin/a.py", 20)])
    with pytest.raises(F.ForbiddenError, match="node_modules"):
        F.assert_members_clean([("node_modules/x/index.js", 5)])
    with pytest.raises(F.ForbiddenError, match="oversized"):
        F.assert_members_clean(
            [("big.bin", 100)],
            max_file_bytes=50,
        )


def test_mutation_delete_git_rule_goes_red(tmp_path: Path) -> None:
    """MUTATION: delete the .git role patterns → classifier misses plant → suite red."""
    stage = tmp_path / "stage"
    _write(stage / ".git" / "config", "[core]\n")

    # Healthy: git role fires.
    healthy = F.classify_path_role(".git/config")
    assert healthy == "git"

    mutated = copy.deepcopy(F.FORBIDDEN_ROLES)
    del mutated["git"]
    # After mutation the plant is invisible to path-role classification.
    assert F.classify_path_role(".git/config", roles=mutated) is None

    report = F.scan_staging(
        stage,
        config=F.ScanConfig(require_planted_control=False),
        roles=mutated,
    )
    git_hits = [f for f in report.findings if f.role == "git"]
    # Suite expectation that would go red under mutation:
    with pytest.raises(AssertionError):
        assert git_hits, "expected .git finding (mutation deleted git rule)"


def test_cli_fixture_tree_exit_codes(tmp_path: Path) -> None:
    dirty = tmp_path / "dirty"
    _write(dirty / "node_modules" / "a" / "b.js", "1")
    control = tmp_path / "ctl"
    F.plant_control_fixture(control)
    empty = tmp_path / "empty"
    empty.mkdir()

    rc_dirty = F.main(["--root", str(dirty), "--control", str(control)])
    assert rc_dirty == 12

    rc_clean = F.main(["--root", str(empty), "--control", str(control)])
    assert rc_clean == 0
