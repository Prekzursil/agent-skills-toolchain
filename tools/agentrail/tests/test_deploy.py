"""Deploy: the guard refuses to truncate an existing shim. Ledger-proven data-loss class."""

from __future__ import annotations

import pytest

from agentrail.deploy import (
    DEPLOY_ACTIONS,
    MARKER,
    SHIM_NAME,
    decide,
    deploy_shim,
    render_shim,
)
from fakes import FakeFileSystem

TARGET = "/home/u/.local/bin/agentrail.cmd"


def test_a_missing_target_is_written() -> None:
    decision = decide(TARGET, exists=False)
    assert decision.action == "write"
    assert decision.writes is True


def test_an_existing_target_is_left_untouched_by_default() -> None:
    """`New-Item -Force` on a FILE truncates it -- the whole reason this guard exists."""
    decision = decide(TARGET, exists=True)
    assert decision.action == "skip-exists"
    assert decision.writes is False
    assert "refusing to truncate" in decision.rationale


def test_overwrite_is_an_explicit_opt_in() -> None:
    decision = decide(TARGET, exists=True, overwrite=True)
    assert decision.action == "overwrite"
    assert decision.writes is True
    assert "--overwrite was passed explicitly" in decision.rationale


def test_every_action_is_declared() -> None:
    actions = {
        decide(TARGET, exists=False).action,
        decide(TARGET, exists=True).action,
        decide(TARGET, exists=True, overwrite=True).action,
    }
    assert actions == set(DEPLOY_ACTIONS)


@pytest.mark.parametrize("target", ["", "   "])
def test_an_empty_target_is_refused(target: str) -> None:
    with pytest.raises(ValueError, match="deploy target must be non-empty"):
        decide(target, exists=False)


def test_the_shim_puts_both_package_roots_on_pythonpath() -> None:
    body = render_shim(["C:/Users/u/source/agent-skills-toolchain/tools"])
    assert "agentspec" in body
    assert "python -m agentrail %*" in body
    assert "@echo off" in body
    assert "C:\\Users\\u\\source\\agent-skills-toolchain\\tools" in body
    assert "fully-gated" in body


def test_the_shim_probes_every_candidate_root_in_order() -> None:
    """A shim pinned to ONE root dies the moment that root is a pruned git worktree."""
    body = render_shim(["/a/tools", "/b/tools"])
    probes = [line for line in body.splitlines() if line.startswith("if not defined")]
    assert len(probes) == 3, "two candidate probes plus the not-found guard"
    assert "\\a\\tools" in probes[0]
    assert "\\b\\tools" in probes[1]
    assert body.index("\\a\\tools") < body.index("\\b\\tools")
    assert MARKER in body


def test_the_shim_fails_loudly_with_a_terminal_marker_when_no_root_exists() -> None:
    body = render_shim(["/a/tools"])
    assert "FAILED:agentrail env-missing-agentrail" in body
    assert "exit /b 1" in body
    assert "agentrail deploy --overwrite" in body


def test_the_shim_expands_no_batch_variable_it_never_sets() -> None:
    """MEASURED BUG: a stray ``%MARKER%`` expanded to the EMPTY STRING in the deployed shim.

    ``cmd`` substitutes ``%NAME%`` silently, so a Python-side placeholder that leaks into the
    template does not error -- it just deletes itself from the message. This asserts the only
    percent-expansions present are ones the shim sets, or the argument forwarder.
    """
    import re

    body = render_shim(["/a/tools"])
    allowed = {"AGENTRAIL_TOOLS", "PYTHONPATH"}
    referenced = set(re.findall(r"%([A-Za-z_][A-Za-z0-9_]*)%", body))
    assert referenced <= allowed, f"undefined batch variable(s): {referenced - allowed}"
    assert "python -m agentrail %*" in body
    assert MARKER in body


def test_blank_and_duplicate_candidate_roots_are_dropped() -> None:
    """Two probes for one root would make the shim LOOK like it has a fallback."""
    body = render_shim(["  ", "/a/tools/", "/a/tools"])
    probes = [line for line in body.splitlines() if line.startswith("if not defined")]
    assert len(probes) == 2, "one candidate probe plus the not-found guard"


def test_the_shim_renderer_refuses_an_empty_candidate_list() -> None:
    with pytest.raises(ValueError, match="at least one non-empty tools_dir"):
        render_shim(["  ", ""])


def test_deploy_writes_once_and_then_refuses() -> None:
    fs = FakeFileSystem()
    first = deploy_shim(fs, target=TARGET, tools_dirs=["/tools"])
    assert first.action == "write"
    assert len(fs.writes) == 1

    second = deploy_shim(fs, target=TARGET, tools_dirs=["/tools"])
    assert second.action == "skip-exists"
    assert len(fs.writes) == 1, "the existing shim must not be rewritten"


def test_deploy_overwrites_only_when_told_to() -> None:
    fs = FakeFileSystem({TARGET: b"old content"})
    decision = deploy_shim(fs, target=TARGET, tools_dirs=["/tools"], overwrite=True)
    assert decision.action == "overwrite"
    assert fs.files[TARGET] != b"old content"
    assert SHIM_NAME in TARGET
