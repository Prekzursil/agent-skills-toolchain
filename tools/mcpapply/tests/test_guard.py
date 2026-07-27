"""The write preconditions, including the FAIL-CLOSED behaviour on an unknown state."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence

import pytest

from mcpapply.guard import (
    default_runner,
    list_argv,
    make_guard,
    running_host_refusal,
    user_scope_promotion_refusal,
)

_TASKLIST = '"claude.exe","1234","Console","1","70,000 K"\n"chrome.exe","9","Console","1","1 K"\n'
_PS = "bash\nclaude\npython3\n"
_QUIET_WINDOWS = '"explorer.exe","4","Console","1","1 K"\n'
_QUIET_POSIX = "bash\npython3\n"


def _runner(output: str):
    def run(argv: Sequence[str]) -> str:
        assert argv  # the guard must always pass a real argv
        return output

    return run


def test_the_listing_command_matches_the_platform():
    assert list_argv("nt")[0] == "tasklist"
    assert list_argv("posix")[0] == "ps"


def test_a_running_host_is_detected_in_the_windows_csv_listing():
    refusal = running_host_refusal(os_name="nt", runner=_runner(_TASKLIST))
    assert "claude.exe" in refusal
    assert "close every Claude Code window" in refusal


def test_a_running_host_is_detected_in_the_posix_listing():
    assert "claude" in running_host_refusal(os_name="posix", runner=_runner(_PS))


def test_a_quiet_box_permits_the_write():
    assert running_host_refusal(os_name="nt", runner=_runner(_QUIET_WINDOWS)) == ""
    assert running_host_refusal(os_name="posix", runner=_runner(_QUIET_POSIX)) == ""


def test_a_full_path_in_the_listing_still_matches_the_leaf_name():
    for listing in ("/usr/local/bin/claude\n", "C:\\Users\\o\\claude.exe\n"):
        assert running_host_refusal(os_name="posix", runner=_runner(listing)) != ""


def test_blank_lines_are_ignored():
    assert running_host_refusal(os_name="posix", runner=_runner("\n\n   \n")) == ""


def test_force_accepts_the_race_but_only_when_asked():
    runner = _runner(_TASKLIST)
    assert running_host_refusal(os_name="nt", runner=runner) != ""
    assert running_host_refusal(os_name="nt", runner=runner, force=True) == ""


def test_a_probe_that_fails_is_treated_as_running_not_as_clear():
    """FAIL CLOSED: 'we could not check, so we wrote anyway' corrupts a profile."""

    def explode(argv: Sequence[str]) -> str:
        raise FileNotFoundError("tasklist is not on PATH")

    refusal = running_host_refusal(os_name="nt", runner=explode)
    assert "FAILING CLOSED" in refusal
    assert "FileNotFoundError" in refusal


def test_a_subprocess_error_is_also_fail_closed():
    def explode(argv: Sequence[str]) -> str:
        raise subprocess.TimeoutExpired(cmd="ps", timeout=1)

    assert "FAILING CLOSED" in running_host_refusal(os_name="posix", runner=explode)


def test_the_user_scope_promotion_gate_is_a_human_step_not_an_override():
    refusal = user_scope_promotion_refusal(touches_user_scope=True, host_running=True)
    assert "HUMAN step" in refusal
    assert "--force does not apply here" in refusal


def test_the_promotion_gate_is_silent_when_it_does_not_apply():
    assert (
        user_scope_promotion_refusal(touches_user_scope=False, host_running=True) == ""
    )
    assert (
        user_scope_promotion_refusal(touches_user_scope=True, host_running=False) == ""
    )


def test_the_composed_guard_puts_the_promotion_gate_ahead_of_force():
    guard = make_guard(
        os_name="nt", runner=_runner(_TASKLIST), force=True, touches_user_scope=True
    )
    assert "HUMAN step" in guard()


def test_the_composed_guard_falls_through_to_the_session_check():
    assert make_guard(os_name="nt", runner=_runner(_TASKLIST))() != ""
    assert make_guard(os_name="nt", runner=_runner(_QUIET_WINDOWS))() == ""


def test_the_composed_guard_fails_closed_on_a_broken_probe():
    def explode(argv: Sequence[str]) -> str:
        raise OSError("no such tool")

    guard = make_guard(os_name="nt", runner=explode, touches_user_scope=True)
    assert "HUMAN step" in guard()


def test_the_composed_guard_defaults_its_platform_from_sys_platform():
    """No os_name given: it must still pick a listing command that exists here."""
    guard = make_guard(runner=_runner(_QUIET_POSIX + _QUIET_WINDOWS))
    assert guard() == ""


def test_the_real_default_runner_executes_a_real_child_process():
    """Binds the PRODUCTION default, not a fake -- against a short-lived Python child,
    never the host binary. The gated suite must never spawn a real session."""
    out = default_runner([sys.executable, "-c", "print('claude.exe')"])
    assert out.strip() == "claude.exe"


def test_the_real_default_runner_raises_on_a_failing_child():
    """It must RAISE, so `running_host_refusal` reaches its fail-closed branch."""
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        default_runner([sys.executable, "-c", "raise SystemExit(3)"])
    assert excinfo.value.returncode == 3
