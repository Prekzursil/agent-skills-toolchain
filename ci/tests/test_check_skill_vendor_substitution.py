"""Regression tests for the vendor-substitution CI gate."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_skill_vendor_substitution as gate  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
EXEMPTIONS = REPO / "ci" / "skill-vendor-substitution-exemptions.txt"
EXEMPTED_RELATIVE = (
    "writing-skills/SKILL.md",
    "systematic-debugging/SKILL.md",
)
CORRUPTION_LINE = "Register as an MCP server (Codex / Codex / Cursor):\n"


def _root(tmp_path: Path, text: str) -> Path:
    root = tmp_path / "skills"
    skill = root / "fixture"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(text, encoding="utf-8", newline="\n")
    return root


def _copy_exempted_files(root: Path) -> None:
    for relative in EXEMPTED_RELATIVE:
        dest = root / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            (REPO / "skills" / relative).read_text(encoding="utf-8"),
            encoding="utf-8",
            newline="\n",
        )


def test_corrupted_fixture_is_red(tmp_path: Path) -> None:
    code, report, _ = gate.run([_root(tmp_path, "Codex / Codex / Cursor\n")], None)
    assert code == gate.EXIT_VIOLATION
    assert report and report.violations


def test_uncorrupted_fixture_is_green(tmp_path: Path) -> None:
    text = "Claude Code / Codex / Cursor\neverything-claude-code\n~/.claude/\n"
    code, report, _ = gate.run([_root(tmp_path, text)], None)
    assert code == gate.EXIT_OK
    assert report and not report.violations


def test_matching_is_case_sensitive(tmp_path: Path) -> None:
    code, report, _ = gate.run([_root(tmp_path, "codex / codex\n")], None)
    assert code == gate.EXIT_OK
    assert report and not report.violations


def test_empty_root_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    code, report, error = gate.run([root], None)
    assert code == gate.EXIT_CONFIG
    assert report is None
    assert "empty walk" in error


def test_stale_exemption_fails_closed(tmp_path: Path) -> None:
    root = _root(tmp_path, "ordinary text\n")
    exemptions = tmp_path / "exemptions.txt"
    exemptions.write_text(
        "fixture/SKILL.md:Codex / Codex:1 # stale test pin\n",
        encoding="utf-8",
        newline="\n",
    )
    code, report, error = gate.run([root], exemptions)
    assert code == gate.EXIT_CONFIG
    assert report is None
    assert gate.RULE_STALE_EXEMPTION in error


@pytest.mark.parametrize(
    "text",
    ["CodexSource\n", "CodexThread\n", "Codex is a supported vendor.\n"],
)
def test_legitimate_codex_names_do_not_fire(tmp_path: Path, text: str) -> None:
    code, report, _ = gate.run([_root(tmp_path, text)], None)
    assert code == gate.EXIT_OK
    assert report and not report.violations


def test_exemption_missing_count_fails_closed(tmp_path: Path) -> None:
    root = _root(tmp_path, "Codex / Codex\n")
    exemptions = tmp_path / "exemptions.txt"
    exemptions.write_text(
        "fixture/SKILL.md:Codex / Codex # missing count is not a pin\n",
        encoding="utf-8",
        newline="\n",
    )
    code, report, error = gate.run([root], exemptions)
    assert code == gate.EXIT_CONFIG
    assert report is None
    assert "relative/path:marker:count" in error


def test_exemption_undershoot_fails_closed(tmp_path: Path) -> None:
    root = _root(tmp_path, "Codex / Codex\n")
    exemptions = tmp_path / "exemptions.txt"
    exemptions.write_text(
        "fixture/SKILL.md:Codex / Codex:2 # pin above observed\n",
        encoding="utf-8",
        newline="\n",
    )
    code, report, error = gate.run([root], exemptions)
    assert code == gate.EXIT_CONFIG
    assert report is None
    assert gate.RULE_STALE_EXEMPTION in error
    assert "observed 1 < pinned 2" in error


def test_exempted_files_at_pinned_count_are_green(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    _copy_exempted_files(root)
    code, report, error = gate.run([root], EXEMPTIONS)
    assert code == gate.EXIT_OK, error
    assert report and not report.violations


def test_exempted_file_appended_corruption_is_red(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    _copy_exempted_files(root)
    target = root / "writing-skills" / "SKILL.md"
    target.write_text(
        target.read_text(encoding="utf-8") + CORRUPTION_LINE,
        encoding="utf-8",
        newline="\n",
    )
    code, report, error = gate.run([root], EXEMPTIONS)
    assert code == gate.EXIT_VIOLATION, error
    assert report and report.violations
    assert any(
        item.marker == "Codex / Codex" and item.skill == "writing-skills"
        for item in report.violations
    )
