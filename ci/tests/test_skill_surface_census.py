"""Both-states regression tests for the M01 skill-surface census."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import skill_surface_census as census  # noqa: E402


def _skill(
    root: Path,
    name: str,
    *,
    skill_md: bytes = b"---\nname: known\ndescription: known\n---\n",
    helper: bytes | None = None,
) -> None:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_bytes(skill_md)
    if helper is not None:
        (directory / "helper.txt").write_bytes(helper)


def _argv(expected: Path, actual: Path, required: str = "known") -> list[str]:
    return [
        "--expected",
        str(expected),
        "--actual",
        str(actual),
        "--require-skill",
        required,
    ]


def test_equal_count_equal_size_content_drift_is_a_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Known-broken: the old directory count reports 1 == 1 for this drift."""
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    _skill(expected, "known", skill_md=b"alpha\n")
    _skill(actual, "known", skill_md=b"bravo\n")

    assert census.main(_argv(expected, actual)) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["match"] is False
    assert payload["expected"]["skill_count"] == payload["actual"]["skill_count"] == 1
    assert payload["expected"]["file_count"] == payload["actual"]["file_count"] == 1


def test_auxiliary_file_drift_changes_the_merkle(tmp_path: Path) -> None:
    """Known-broken: consolidation hashes SKILL.md only, so helper drift was invisible."""
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    _skill(expected, "known", helper=b"version one\n")
    _skill(actual, "known", helper=b"version two\n")

    left = census.census_surface(expected, required_skill="known")
    right = census.census_surface(actual, required_skill="known")
    assert left.skill_count == right.skill_count == 1
    assert left.file_count == right.file_count == 2
    assert left.merkle_sha256 != right.merkle_sha256


def test_equal_count_file_rename_changes_the_merkle(tmp_path: Path) -> None:
    """Known-broken: the old count detector could not see a path-only change."""
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    _skill(expected, "known")
    _skill(actual, "known")
    (expected / "known" / "before.txt").write_bytes(b"same\n")
    (actual / "known" / "after.txt").write_bytes(b"same\n")

    left = census.census_surface(expected, required_skill="known")
    right = census.census_surface(actual, required_skill="known")
    assert left.skill_count == right.skill_count == 1
    assert left.file_count == right.file_count == 2
    assert left.merkle_sha256 != right.merkle_sha256


def test_lf_normalization_preserves_binary_differences(tmp_path: Path) -> None:
    """Known-broken: no explicit whole-surface LF-normalized digest existed."""
    lf = tmp_path / "lf"
    crlf = tmp_path / "crlf"
    _skill(lf, "known", skill_md=b"line one\nline two\n", helper=b"helper\n")
    _skill(
        crlf,
        "known",
        skill_md=b"line one\r\nline two\r\n",
        helper=b"helper\r\n",
    )

    left = census.census_surface(lf, required_skill="known")
    right = census.census_surface(crlf, required_skill="known")
    assert left == right

    (lf / "known" / "payload.bin").write_bytes(b"\0line\n")
    (crlf / "known" / "payload.bin").write_bytes(b"\0line\r\n")
    left = census.census_surface(lf, required_skill="known")
    right = census.census_surface(crlf, required_skill="known")
    assert left.merkle_sha256 != right.merkle_sha256


def test_missing_known_present_control_fails_closed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Known-broken: a nonempty wrong tree could make the count detector look healthy."""
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    _skill(expected, "other")
    _skill(actual, "other")

    assert census.main(_argv(expected, actual)) == 2
    error = json.loads(capsys.readouterr().err)
    assert "required known-present skill is missing: known" in error["error"]


def test_missing_root_fails_closed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Known-broken: a failed count pipeline could still leave an apparent zero."""
    missing = tmp_path / "missing"

    assert census.main(_argv(missing, missing)) == 2
    error = json.loads(capsys.readouterr().err)
    assert "skill root is missing" in error["error"]


def test_unreadable_file_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Known-broken: the count detector never opened files, so unreadable meant clean."""
    root = tmp_path / "root"
    _skill(root, "known", helper=b"helper\n")
    unreadable = root / "known" / "helper.txt"
    original_read_bytes = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path == unreadable:
            raise OSError("unreadable fixture")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    with pytest.raises(census.CensusError, match="cannot read skill file"):
        census.census_surface(root, required_skill="known")


def test_exact_copy_emits_a_machine_readable_match(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Known-broken: the old workflow emitted only an unverified directory count."""
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    _skill(expected, "known", helper=b"helper\n")
    shutil.copytree(expected, actual)

    assert census.main(_argv(expected, actual)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == census.SCHEMA
    assert payload["match"] is True
    assert payload["expected"]["skill_count"] == 1
    assert payload["expected"]["file_count"] == 2
    assert (
        payload["expected"]["merkle_sha256"]
        == "814baec4e687e39e34d26ef8206a5f7889aa892c12e601c4aade92337c84a4bb"
    )


def test_symlink_in_a_skill_fails_closed(tmp_path: Path) -> None:
    """Known-broken: the count detector did not inspect or constrain file types."""
    root = tmp_path / "root"
    _skill(root, "known")
    target = root / "known" / "target.txt"
    target.write_text("target\n", encoding="utf-8")
    (root / "known" / "link.txt").symlink_to(target)

    with pytest.raises(census.CensusError, match="symlink in skill surface"):
        census.census_surface(root, required_skill="known")


def test_workflow_replaces_the_count_detector_with_the_census() -> None:
    """Known-broken: codex-runner called find|wc and no content census."""
    repo = Path(__file__).resolve().parents[2]
    workflow = (repo / ".github/workflows/codex-runner.yml").read_text(encoding="utf-8")
    assert 'python "$GITHUB_WORKSPACE/runner/ci/skill_surface_census.py"' in workflow
    assert '--expected "$GITHUB_WORKSPACE/runner/ci/skills-allowlist"' in workflow
    assert '--actual "$HOME/.agents/skills"' in workflow
    assert "--require-skill acceptance-review" in workflow
    assert (
        'find "$HOME/.agents/skills" -mindepth 1 -maxdepth 1 -type d | wc -l'
        not in workflow
    )
