#!/usr/bin/env python
"""Regression suite for the coverage dimension of the git-hygiene Stop hook.

The measured blind spot: file-level drift compares ONE mapped live->repo pair, so a whole
skill living in an UNMAPPED live root (~/.claude/skills) or a registered MCP server whose
launcher never landed in the repo slipped out of version control unnoticed. cv-studio (a
skill) and a would-be linkedin MCP are the recorded escapes. These tests pin the two
name-bearing coverage scans that close the hole -- and, just as importantly, pin that a skill
present in ANY repo tree stays SILENT, so the fix does not trade a blind spot for a flood.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import check  # noqa: E402


def _mkskill(home: Path, root: str, name: str) -> None:
    (home / root / name).mkdir(parents=True, exist_ok=True)
    (home / root / name / "SKILL.md").write_text("x\n", encoding="utf-8")


def _tracked_for(*trees_names) -> frozenset:
    """Build a fake tracked set: each ("tree", "name") contributes tree/name/SKILL.md."""
    return frozenset(f"{tree}/{name}/SKILL.md" for tree, name in trees_names)


def _cfg(**over) -> check.Config:
    return dataclasses.replace(check.Config(), **over) if over else check.Config()


# --------------------------------------------------------------------------------------
# scan_skills_coverage
# --------------------------------------------------------------------------------------
class TestSkillsCoverage:
    def test_a_live_skill_in_no_repo_tree_is_flagged_by_name(self, tmp_path):
        _mkskill(tmp_path, ".claude/skills", "cv-studio")
        # non-empty tracked (some OTHER committed skill) so the stand-down guard is not tripped
        r = check.scan_skills_coverage(
            tmp_path, _tracked_for((".agents/skills", "other")), _cfg()
        )
        assert r.missing == 1
        assert r.names == ("cv-studio",)

    @pytest.mark.parametrize("tree", ["skills", ".agents/skills", "skills-claude-only"])
    def test_a_live_skill_present_in_any_repo_tree_is_silent(self, tmp_path, tree):
        _mkskill(tmp_path, ".claude/skills", "council")
        r = check.scan_skills_coverage(
            tmp_path, _tracked_for((tree, "council")), _cfg()
        )
        assert r.missing == 0

    def test_a_skill_in_two_repo_trees_is_not_double_counted(self, tmp_path):
        # A skill living in both skills/ and .agents/skills/ is covered once, not twice,
        # and certainly is not flagged.
        _mkskill(tmp_path, ".agents/skills", "audio-extract-mix")
        tracked = _tracked_for(
            ("skills", "audio-extract-mix"), (".agents/skills", "audio-extract-mix")
        )
        r = check.scan_skills_coverage(tmp_path, tracked, _cfg())
        assert r.missing == 0

    def test_a_skill_live_in_agents_root_but_absent_from_repo_is_flagged(
        self, tmp_path
    ):
        # cv-studio's real shape: live only under ~/.agents/skills, in no repo tree.
        _mkskill(tmp_path, ".agents/skills", "cv-studio")
        r = check.scan_skills_coverage(
            tmp_path, _tracked_for(("skills", "other")), _cfg()
        )
        assert r.names == ("cv-studio",)

    def test_empty_tracked_set_stands_down(self, tmp_path):
        _mkskill(tmp_path, ".claude/skills", "anything")
        r = check.scan_skills_coverage(tmp_path, frozenset(), _cfg())
        assert r.stood_down is True
        assert r.missing == 0

    def test_no_live_skills_is_silent(self, tmp_path):
        r = check.scan_skills_coverage(tmp_path, _tracked_for(("skills", "x")), _cfg())
        assert r.missing == 0
        assert r.stood_down is False

    def test_names_are_sorted_and_capped_with_total(self, tmp_path):
        for n in ["zeta", "alpha", "mike", "bravo", "yankee", "delta", "echo"]:
            _mkskill(tmp_path, ".claude/skills", n)
        r = check.scan_skills_coverage(
            tmp_path, _tracked_for(("skills", "other")), _cfg(coverage_name_cap=3)
        )
        assert r.missing == 7
        assert r.total_names == 7
        assert list(r.names) == ["alpha", "bravo", "delta"]


# --------------------------------------------------------------------------------------
# scan_mcp_coverage
# --------------------------------------------------------------------------------------
def _write_manifest(home: Path, servers: dict) -> None:
    (home / ".mcp.json").write_text(
        json.dumps({"mcpServers": servers}), encoding="utf-8"
    )


class TestMcpCoverage:
    def test_a_repo_server_with_an_untracked_launcher_is_flagged(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_manifest(
            tmp_path,
            {
                "linkedin": {
                    "command": "python",
                    "args": [str(repo / "tools/mcp/linkedin/server.py")],
                }
            },
        )
        r = check.scan_mcp_coverage(tmp_path, repo, frozenset({"README.md"}), _cfg())
        assert r.missing == 1
        assert r.names == ("linkedin",)

    def test_a_repo_server_with_a_tracked_launcher_is_silent(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_manifest(
            tmp_path,
            {
                "cloud-hub": {
                    "command": "python",
                    "args": [str(repo / "tools/mcp/cloud-hub/hub.py")],
                }
            },
        )
        tracked = frozenset({"tools/mcp/cloud-hub/hub.py"})
        r = check.scan_mcp_coverage(tmp_path, repo, tracked, _cfg())
        assert r.missing == 0

    def test_a_server_outside_the_repo_is_out_of_scope(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_manifest(
            tmp_path,
            {
                "ghidra": {
                    "command": "C:/Users/x/.local/opt/ghidra-mcp/.venv/py.exe",
                    "args": ["C:/Users/x/.local/opt/ghidra-mcp/bridge.py"],
                }
            },
        )
        r = check.scan_mcp_coverage(tmp_path, repo, frozenset(), _cfg())
        # empty tracked would normally stand down; assert it is not FLAGGING the out-of-repo one
        assert r.missing == 0

    def test_the_repo_path_may_live_in_command_not_args(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_manifest(
            tmp_path, {"custom": {"command": str(repo / "tools/mcp/custom/run.exe")}}
        )
        r = check.scan_mcp_coverage(tmp_path, repo, frozenset({"README.md"}), _cfg())
        assert r.names == ("custom",)

    def test_a_launcher_that_exists_on_disk_but_untracked_is_silent(self, tmp_path):
        # Belt-and-braces: an existing-but-untracked path is treated as covered (generated),
        # matching the docs scan's stance -- absence from git is not proof of absence on disk.
        repo = tmp_path / "repo"
        (repo / "tools/mcp/gen").mkdir(parents=True)
        (repo / "tools/mcp/gen/server.py").write_text("x\n", encoding="utf-8")
        _write_manifest(
            tmp_path,
            {
                "gen": {
                    "command": "python",
                    "args": [str(repo / "tools/mcp/gen/server.py")],
                }
            },
        )
        r = check.scan_mcp_coverage(tmp_path, repo, frozenset({"README.md"}), _cfg())
        assert r.missing == 0

    def test_missing_manifest_stands_down(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        r = check.scan_mcp_coverage(tmp_path, repo, frozenset({"x"}), _cfg())
        assert r.stood_down is True

    def test_malformed_manifest_stands_down(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (tmp_path / ".mcp.json").write_text("{not json", encoding="utf-8")
        r = check.scan_mcp_coverage(tmp_path, repo, frozenset({"x"}), _cfg())
        assert r.stood_down is True

    def test_empty_server_map_is_silent(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_manifest(tmp_path, {})
        r = check.scan_mcp_coverage(tmp_path, repo, frozenset({"x"}), _cfg())
        assert r.missing == 0
        assert r.stood_down is False

    def test_empty_tracked_set_stands_down(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_manifest(tmp_path, {"a": {"command": "python"}})
        r = check.scan_mcp_coverage(tmp_path, repo, frozenset(), _cfg())
        assert r.stood_down is True


# --------------------------------------------------------------------------------------
# message rendering -- names must survive into additionalContext
# --------------------------------------------------------------------------------------
class TestCoverageMessage:
    def test_clean_coverage_adds_no_line(self):
        assert check._coverage_lines([check.CoverageReport("skills")]) == []

    def test_missing_skill_is_named_in_the_message(self):
        cov = check.CoverageReport(
            "skills", missing=1, names=("cv-studio",), total_names=1
        )
        lines = check._coverage_lines([cov])
        assert any("cv-studio" in ln for ln in lines)
        assert any("skills" in ln for ln in lines)

    def test_cap_shows_plus_n_more(self):
        cov = check.CoverageReport(
            "skills", missing=9, names=("a", "b", "c"), total_names=9
        )
        lines = check._coverage_lines([cov])
        assert any("+6 more" in ln for ln in lines)

    def test_build_message_surfaces_coverage_when_only_coverage_dirty(self):
        cov = check.CoverageReport("mcp", missing=1, names=("linkedin",), total_names=1)
        msg = check.build_message([], [], None, [cov])
        assert msg is not None
        assert "linkedin" in msg
        assert "GIT-HYGIENE / mcp" in msg

    def test_coverage_leads_the_message_so_names_survive_the_line_cap(self):
        # A whole missing skill outranks doc rot: it must appear before the cap can drop it.
        cov = check.CoverageReport(
            "skills", missing=1, names=("cv-studio",), total_names=1
        )
        docs = check.DocsReport(cruft_files=1, cruft_examples=("x.orig",))
        msg = check.build_message([], [], docs, [cov])
        assert msg.index("cv-studio") < msg.index("x.orig")
