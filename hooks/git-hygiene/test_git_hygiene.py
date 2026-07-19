#!/usr/bin/env python
"""Regression suite for the git-hygiene Stop hook.

WHY THESE FIXTURES: every one is a MEASURED population on this box, 2026-07-18, not an
invented case. A naive detector ("report anything dirty or lacking an upstream") fires on
329 discovered repos -- 175 dirty, 111 without an upstream. Only a handful are real. A hook
that emits 175 lines gets disabled within a day, which is strictly worse than no hook, so the
CLASSIFIER -- not the scan -- is the product. These tests pin the classifier.

Measured populations each fixture stands for:
  vendored plugin cache   258 repos under ~/.claude/plugins/**  (all third-party clones)
  ephemeral worktrees      20 repos under ~/.claude/agent-worktrees/* (detached, 0 dirty)
  temp_subdir husks         8 no-remote clone husks in the plugin cache (see PR2)
  third-party dirty        ~37 dirty files across insta-mcp/hexstrike-ai/mcp_agent_mail/...
  unborn repo               1 (~/Documents/Misc: `git init`, no commits, no remote)
  genuine finds             agent-skills-toolchain 4 unpushed commits;
                            ast-harness-reconcile worktree 295 dirty;
                            quality-zero-platform 9 dirty + no upstream;
                            pbinfo-fix-wave1 11 dirty + no upstream

The KNOWN-POSITIVE CONTROL tests are mandatory and must never be skipped or weakened: this
program exists because an absence was trusted without one, seven times in a single session.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check  # noqa: E402


# --------------------------------------------------------------------------------------
# real-git helpers -- the control tests must run against real repos, not mocks
# --------------------------------------------------------------------------------------
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=GIT_ENV,
        timeout=30,
    )


def make_repo(
    path: Path,
    *,
    origin: str | None = None,
    commit: bool = True,
    dirty: int = 0,
    detached: bool = False,
) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-b", "main")
    if origin:
        git(path, "remote", "add", "origin", origin)
    if commit:
        (path / "kept.txt").write_text("committed\n", encoding="utf-8")
        git(path, "add", "kept.txt")
        git(path, "commit", "-m", "initial")
    if detached:
        head = git(path, "rev-parse", "HEAD").stdout.strip()
        if head:
            git(path, "checkout", "--detach", head)
    for i in range(dirty):
        (path / f"scratch{i}.txt").write_text("uncommitted\n", encoding="utf-8")
    return path


def state_of(path: Path, **over) -> check.RepoState:
    """Read a REAL repo, then allow surgical overrides for cases git can't cheaply stage."""
    st = check.read_repo_state(path)
    assert st is not None, f"read_repo_state returned None for a real repo: {path}"
    return dataclasses.replace(st, **over) if over else st


CFG = check.Config(owner="Prekzursil")


# --------------------------------------------------------------------------------------
# 1. THE FIXTURES THE UNIT REQUIRES
# --------------------------------------------------------------------------------------
class TestClassification:
    def test_yours_and_dirty_is_reported(self, tmp_path):
        r = make_repo(
            tmp_path / "quality-zero-platform",
            origin="https://github.com/Prekzursil/quality-zero-platform.git",
            dirty=9,
        )
        v = check.classify(state_of(r), CFG)
        assert v.ownership == check.YOURS
        assert v.report is True
        assert "9" in v.detail

    def test_vendored_and_dirty_is_never_reported(self, tmp_path):
        """insta-mcp: 12 dirty files, origin arjun1194/insta-mcp. Dirt in someone else's
        clone is the EXPECTED steady state -- reporting it is pure noise."""
        r = make_repo(
            tmp_path / "insta-mcp",
            origin="https://github.com/arjun1194/insta-mcp.git",
            dirty=12,
        )
        v = check.classify(state_of(r), CFG)
        assert v.ownership == check.VENDORED
        assert v.report is False

    def test_no_remote_with_commits_is_reported_as_highest_severity(self, tmp_path):
        """Work that exists ONLY on this disk. One failure from gone."""
        r = make_repo(tmp_path / "tiktok-mcp", origin=None, commit=True)
        v = check.classify(state_of(r), CFG)
        assert v.ownership == check.NO_REMOTE
        assert v.report is True
        assert v.severity == check.SEV_NO_REMOTE

    def test_clean_and_pushed_is_silent(self, tmp_path):
        r = make_repo(
            tmp_path / "event-link",
            origin="https://github.com/Prekzursil/event-link.git",
        )
        v = check.classify(state_of(r, upstream="origin/main", ahead=0), CFG)
        assert v.ownership == check.YOURS
        assert v.report is False

    def test_nested_repo_inside_a_synced_tree_is_vendored(self, tmp_path):
        """crypto-ctf/RsaCtfTool is a full clone of someone else's project sitting inside
        ~/.agents/skills. sync-from-live.ps1 already refuses to copy it (Test-InNestedRepo).
        The hook must reach the same verdict -- and MUST do so even when the nested clone
        carries a Prekzursil-looking origin, because position beats provenance here."""
        outer = make_repo(
            tmp_path / "skills",
            origin="https://github.com/Prekzursil/agent-skills-toolchain.git",
        )
        inner = make_repo(
            outer / "crypto-ctf" / "RsaCtfTool",
            origin="https://github.com/Prekzursil/RsaCtfTool.git",
            dirty=4,
        )
        v = check.classify(state_of(inner, nested_in=str(outer)), CFG)
        assert v.ownership == check.VENDORED
        assert v.report is False


# --------------------------------------------------------------------------------------
# 2. THE MEASURED NOISE POPULATIONS -- each one silences a real false-positive class
# --------------------------------------------------------------------------------------
class TestMeasuredNoisePopulations:
    def test_ephemeral_agent_worktree_is_not_reported(self, tmp_path):
        """20 measured under ~/.claude/agent-worktrees: ALL detached HEAD (=> no upstream),
        ALL zero dirty. A naive 'no upstream' rule emits 20 lines of pure noise."""
        root = tmp_path / ".claude" / "agent-worktrees"
        r = make_repo(
            root / "agent-2041398331",
            origin="https://github.com/Prekzursil/Reframe.git",
            detached=True,
        )
        cfg = check.Config(owner="Prekzursil", ephemeral_markers=("/agent-worktrees/",))
        v = check.classify(state_of(r), cfg)
        assert v.ownership == check.EPHEMERAL
        assert v.report is False

    def test_detached_and_clean_is_silent_even_without_the_path_rule(self, tmp_path):
        """Defence in depth: a detached HEAD with nothing uncommitted has nothing at risk,
        so it stays silent on its own merits, not only because of where it lives."""
        r = make_repo(
            tmp_path / "somewhere" / "wt",
            origin="https://github.com/Prekzursil/Reframe.git",
            detached=True,
        )
        v = check.classify(
            state_of(r), check.Config(owner="Prekzursil", ephemeral_markers=())
        )
        assert v.report is False

    def test_plugin_cache_clone_is_vendored(self, tmp_path):
        """258 measured repos under ~/.claude/plugins. Vendor-owned, churned by the CLI."""
        r = make_repo(
            tmp_path / ".claude" / "plugins" / "cache" / "some-plugin",
            origin="https://github.com/somevendor/plugin.git",
            dirty=3,
        )
        cfg = check.Config(owner="Prekzursil", vendor_markers=("/.claude/plugins/",))
        v = check.classify(state_of(r), cfg)
        assert v.ownership == check.VENDORED
        assert v.report is False

    def test_temp_subdir_husk_with_no_remote_is_vendored_not_no_remote(self, tmp_path):
        """8 measured `temp_subdir_*.clone` husks in the plugin cache have NO remote at all.
        Ownership rules must be POSITION-FIRST, or these land in the highest-severity
        no-remote bucket and dominate the report. (Same husk population PR2 measured.)"""
        r = make_repo(
            tmp_path
            / ".claude"
            / "plugins"
            / "cache"
            / "temp_subdir_1783398195533_5qa899.clone",
            origin=None,
        )
        cfg = check.Config(owner="Prekzursil", vendor_markers=("/.claude/plugins/",))
        v = check.classify(state_of(r), cfg)
        assert v.ownership == check.VENDORED
        assert v.report is False

    def test_unborn_repo_with_no_commits_is_silent(self, tmp_path):
        """~/Documents/Misc is `git init` and nothing else: no remote, no commits, no dirt.
        Nothing is at risk, and `git rev-parse HEAD` FAILS there -- so this is both a
        noise case and a crash case."""
        r = tmp_path / "Misc"
        r.mkdir(parents=True)
        git(r, "init", "-b", "main")
        st = check.read_repo_state(r)
        assert st is not None, (
            "read_repo_state must survive an unborn HEAD, not return None"
        )
        assert st.unborn is True
        assert check.classify(st, CFG).report is False

    def test_unborn_repo_that_is_dirty_IS_reported(self, tmp_path):
        """The mirror image: `git init` + real files but never committed is exactly the
        'abandoned local work' the owner asked to catch. Silence here would be a miss."""
        r = tmp_path / "halfstarted"
        r.mkdir(parents=True)
        git(r, "init", "-b", "main")
        (r / "work.py").write_text("real work\n", encoding="utf-8")
        v = check.classify(state_of(r), CFG)
        assert v.report is True


# --------------------------------------------------------------------------------------
# 3. THE GENUINE FINDS -- measured live; these must NEVER be silenced
# --------------------------------------------------------------------------------------
class TestGenuineFindsMustSurvive:
    def test_unpushed_commits_are_reported(self, tmp_path):
        """agent-skills-toolchain measured 4 commits ahead of origin. That is this very
        program's own work sitting unpushed."""
        r = make_repo(
            tmp_path / "agent-skills-toolchain",
            origin="https://github.com/Prekzursil/agent-skills-toolchain.git",
        )
        v = check.classify(state_of(r, upstream="origin/harness/upgrade", ahead=4), CFG)
        assert v.report is True
        assert v.severity == check.SEV_UNPUSHED

    def test_yours_worktree_with_dirty_work_is_reported(self, tmp_path):
        """ast-harness-reconcile: a WORKTREE of agent-skills-toolchain with 295 dirty files.
        Blanket-excluding worktrees to silence the 20 agent scratch dirs would discard the
        single largest pile of uncommitted harness work on the box."""
        r = make_repo(
            tmp_path / "ast-harness-reconcile",
            origin="https://github.com/Prekzursil/agent-skills-toolchain.git",
            dirty=5,
        )
        v = check.classify(state_of(r, is_worktree=True, dirty=295), CFG)
        assert v.report is True
        assert "295" in v.detail

    def test_dirty_with_no_upstream_outranks_dirty_alone(self, tmp_path):
        """pbinfo-fix-wave1 (11 dirty, no upstream) is more at risk than a dirty repo whose
        branch is already pushed, and must sort above it."""
        risky = make_repo(
            tmp_path / "pbinfo-fix-wave1",
            origin="https://github.com/Prekzursil/pbinfo-fix-wave1.git",
            dirty=11,
        )
        safe = make_repo(
            tmp_path / "Reframe",
            origin="https://github.com/Prekzursil/Reframe.git",
            dirty=13,
        )
        vr = check.classify(state_of(risky), CFG)
        vs = check.classify(state_of(safe, upstream="origin/main"), CFG)
        assert vr.report and vs.report
        assert vr.severity < vs.severity, "lower severity value must sort first"


# --------------------------------------------------------------------------------------
# 4. KNOWN-POSITIVE CONTROLS -- MANDATORY. Never skip, never weaken.
# --------------------------------------------------------------------------------------
class TestKnownPositiveControls:
    def test_control_scanner_finds_a_planted_repo(self, tmp_path):
        """Before ANY 'all clean' result may be trusted, prove the scanner finds a repo we
        planted ourselves. Without this, a broken walker and a clean box are identical."""
        planted = make_repo(
            tmp_path / "roots" / "planted-known-positive",
            origin="https://github.com/Prekzursil/planted.git",
            dirty=3,
        )
        found = check.discover_repos([tmp_path / "roots"], CFG, max_depth=3)
        assert any(Path(p).resolve() == planted.resolve() for p, _ in found), (
            "DETECTOR IS BROKEN: the scanner did not find a repo planted at "
            f"{planted}. Any 'no problems found' verdict from this scanner is void."
        )

    def test_control_planted_repo_survives_the_whole_pipeline(self, tmp_path):
        """End-to-end control: plant -> discover -> read -> classify -> message. Proves no
        stage silently drops it. A control that only exercises discovery would not catch a
        classifier that reports nothing."""
        make_repo(
            tmp_path / "roots" / "planted-e2e",
            origin="https://github.com/Prekzursil/planted-e2e.git",
            dirty=2,
        )
        verdicts = check.survey([tmp_path / "roots"], CFG, max_depth=3)
        reported = [v for v in verdicts if v.report]
        assert reported, (
            "END-TO-END CONTROL FAILED: planted dirty repo produced no verdict"
        )
        msg = check.build_message(reported, [])
        assert msg and "planted-e2e" in msg

    def test_control_nested_detection_actually_fires(self, tmp_path):
        """Prove the nested-repo detector can SEE a nested repo. If it silently never fires,
        every vendored clone would be graded on its origin alone."""
        outer = make_repo(
            tmp_path / "roots" / "outer",
            origin="https://github.com/Prekzursil/outer.git",
        )
        make_repo(
            outer / "vendor" / "inner",
            origin="https://github.com/thirdparty/inner.git",
            dirty=1,
        )
        found = check.discover_repos([tmp_path / "roots"], CFG, max_depth=4)
        nested = [(p, n) for p, n in found if n]
        assert nested, (
            "DETECTOR IS BROKEN: no repo was reported as nested, so the nested-repo rule "
            "is untested by every other assertion in this file."
        )

    def test_control_silence_is_earned_not_assumed(self, tmp_path):
        """The negative control's twin: an empty root must yield silence, but only AFTER the
        positive control above proved the same scanner CAN find something."""
        (tmp_path / "empty").mkdir()
        assert check.survey([tmp_path / "empty"], CFG, max_depth=3) == []

    def test_control_survey_threads_a_REAL_nested_repo_to_vendored(self, tmp_path):
        """WIRING control -- the two nested-repo tests above exercise discovery and
        classification SEPARATELY; a bug in survey() that failed to pass discover()'s
        enclosing-path into classify() would pass both and still misfile every nested clone
        as its own top-level repo. This drives the full survey() with NO manual nested_in
        override, and asserts the seam holds."""
        outer = make_repo(
            tmp_path / "roots" / "myrepo",
            origin="https://github.com/Prekzursil/myrepo.git",
            dirty=1,
        )
        make_repo(
            outer / "vendor" / "thirdparty",
            origin="https://github.com/someoneelse/thirdparty.git",
            dirty=1,
        )
        by_name = {
            v.name: v for v in check.survey([tmp_path / "roots"], CFG, max_depth=4)
        }
        assert "thirdparty" in by_name, "the nested repo was not discovered at all"
        assert by_name["thirdparty"].ownership == check.VENDORED
        assert by_name["thirdparty"].report is False
        assert by_name["myrepo"].report is True, "the enclosing repo is still yours"


# --------------------------------------------------------------------------------------
# 5. SYNC DRIFT -- the half that makes live-authored harness work visible
# --------------------------------------------------------------------------------------
class TestSyncDrift:
    def test_live_only_file_is_drift(self, tmp_path):
        live, repo = tmp_path / "live", tmp_path / "repo"
        (live / "sub").mkdir(parents=True)
        repo.mkdir()
        (live / "sub" / "new-rule.md").write_text("authored live\n", encoding="utf-8")
        d = check.scan_sync_drift([(live, repo, "rules")], check.Config(owner="x"))
        assert d and d[0].live_only == 1 and d[0].actionable == 1

    def test_identical_file_is_not_drift(self, tmp_path):
        live, repo = tmp_path / "live", tmp_path / "repo"
        live.mkdir()
        repo.mkdir()
        (live / "a.md").write_text("same\n", encoding="utf-8")
        (repo / "a.md").write_text("same\n", encoding="utf-8")
        d = check.scan_sync_drift([(live, repo, "rules")], check.Config(owner="x"))
        assert not d or d[0].actionable == 0

    def test_excluded_junk_is_not_drift(self, tmp_path):
        """sync-from-live.ps1 excludes .venv/__pycache__/*.pyc/*.bak-* and nested repos.
        The hook MUST use the same exclusions or it reports work that sync would never
        carry -- the 357MB-vs-14MB gap that script documents."""
        live, repo = tmp_path / "live", tmp_path / "repo"
        (live / ".venv" / "lib").mkdir(parents=True)
        (live / "__pycache__").mkdir(parents=True)
        repo.mkdir()
        (live / ".venv" / "lib" / "dep.py").write_text("x\n", encoding="utf-8")
        (live / "__pycache__" / "m.pyc").write_text("x\n", encoding="utf-8")
        (live / "notes.md.bak-fleet-20260713").write_text("x\n", encoding="utf-8")
        d = check.scan_sync_drift([(live, repo, "skills")], check.Config(owner="x"))
        assert not d or d[0].actionable == 0

    def test_nested_repo_inside_a_live_tree_is_excluded_from_drift(self, tmp_path):
        live, repo = tmp_path / "live", tmp_path / "repo"
        nested = live / "crypto-ctf" / "RsaCtfTool"
        nested.mkdir(parents=True)
        repo.mkdir()
        (nested / ".git").mkdir()
        (nested / "src.py").write_text("third party\n", encoding="utf-8")
        d = check.scan_sync_drift([(live, repo, "skills")], check.Config(owner="x"))
        assert not d or d[0].actionable == 0

    def test_truncation_is_declared_not_hidden(self, tmp_path):
        """A budget-limited scan must SAY it was budget-limited. Reporting a partial count
        as if complete is the failure this whole program exists to stop."""
        live, repo = tmp_path / "live", tmp_path / "repo"
        live.mkdir()
        repo.mkdir()
        for i in range(40):
            (live / f"f{i}.md").write_text("x\n", encoding="utf-8")
        d = check.scan_sync_drift(
            [(live, repo, "rules")], check.Config(owner="x"), cap=10
        )
        assert d and d[0].truncated is True


# --------------------------------------------------------------------------------------
# 6. HOOK CONTRACT -- AGENTS.md §6: inject, never block; always fail-open
# --------------------------------------------------------------------------------------
class TestHookContract:
    def _run(self, payload: dict, env_extra: dict | None = None):
        env = {
            **os.environ,
            "GIT_HYGIENE_ROOTS": "",
            "GIT_HYGIENE_SYNC": "off",
            **(env_extra or {}),
        }
        return subprocess.run(
            [sys.executable, str(Path(check.__file__))],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=90,
        )

    def test_exits_zero_and_never_blocks(self, tmp_path):
        r = self._run(
            {
                "hook_event_name": "Stop",
                "cwd": str(tmp_path),
                "session_id": "s",
                "stop_hook_active": False,
            }
        )
        assert r.returncode == 0, f"a Stop hook must never block; got {r.returncode}"

    def test_emits_the_dispatcher_envelope_when_it_has_something_to_say(self, tmp_path):
        make_repo(
            tmp_path / "roots" / "planted-envelope",
            origin="https://github.com/Prekzursil/planted-envelope.git",
            dirty=2,
        )
        r = self._run(
            {"hook_event_name": "Stop", "cwd": str(tmp_path)},
            {"GIT_HYGIENE_ROOTS": str(tmp_path / "roots")},
        )
        assert r.returncode == 0
        obj = json.loads(r.stdout)
        ctx = obj["hookSpecificOutput"]["additionalContext"]
        assert obj["hookSpecificOutput"]["hookEventName"] == "Stop"
        assert "planted-envelope" in ctx

    def test_silent_when_nothing_to_report(self, tmp_path):
        (tmp_path / "roots").mkdir()
        r = self._run(
            {"hook_event_name": "Stop", "cwd": str(tmp_path)},
            {"GIT_HYGIENE_ROOTS": str(tmp_path / "roots")},
        )
        assert r.returncode == 0 and r.stdout.strip() == ""

    def test_fail_open_on_garbage_stdin(self):
        r = subprocess.run(
            [sys.executable, str(Path(check.__file__))],
            input="not json at all",
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_HYGIENE_ROOTS": "", "GIT_HYGIENE_SYNC": "off"},
            timeout=60,
        )
        assert r.returncode == 0

    def test_respects_the_disable_switch(self, tmp_path):
        make_repo(
            tmp_path / "roots" / "planted-disabled",
            origin="https://github.com/Prekzursil/planted-disabled.git",
            dirty=2,
        )
        r = self._run(
            {"hook_event_name": "Stop", "cwd": str(tmp_path)},
            {"GIT_HYGIENE_ROOTS": str(tmp_path / "roots"), "GIT_HYGIENE": "off"},
        )
        assert r.returncode == 0 and r.stdout.strip() == ""


# --------------------------------------------------------------------------------------
# 7. MESSAGE SHAPE -- a hook nobody reads is a hook nobody keeps
# --------------------------------------------------------------------------------------
class TestMessage:
    def test_message_is_bounded_and_names_the_fix(self, tmp_path):
        vs = []
        for i in range(50):
            r = make_repo(
                tmp_path / f"r{i}",
                origin=f"https://github.com/Prekzursil/r{i}.git",
                dirty=i + 1,
            )
            vs.append(check.classify(state_of(r), CFG))
        msg = check.build_message([v for v in vs if v.report], [])
        assert len(msg.splitlines()) <= check.MAX_LINES
        assert "50" in msg, "must say how many were suppressed, not silently truncate"

    def test_no_message_when_everything_is_clean(self):
        assert check.build_message([], []) is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
