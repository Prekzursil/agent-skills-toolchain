"""build_argv REFUSES to put a prompt on argv.

The measured failure: a real run died at ``payload_len=34472`` with Windows ``os error 206``
because an inline prompt was placed on the command line. The Windows CreateProcess cap is
32,767 chars, measured via libuv at 32,745 OK -> 32,774 ENAMETOOLONG.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from agentspec.argv import (
    MIN_SUBSTRING_SCAN_LEN,
    PROMPT_TRANSPORTS,
    WINDOWS_CMDLINE_CAP,
    ArgvTooLong,
    PolicyViolation,
    PromptOnArgv,
    RailSpec,
    build_argv,
    build_for_rail,
    missing_hardening,
    prompt_on_argv,
    render_cmdline,
)

GUARD = Path(__file__).resolve().parents[2] / "glob-argv-guard" / "glob_argv_guard.py"


def test_the_windows_cap_matches_the_in_repo_measurement() -> None:
    """Drift gate: reuse the repo's OWN measured constant instead of inventing one.

    Deliberately NOT skipped when the file is absent — a probe that is silent in both
    states measures nothing, so an absent guard file FAILS this test loudly.
    """
    assert GUARD.is_file(), f"in-repo measurement source is missing: {GUARD}"
    source = GUARD.read_text(encoding="utf-8")
    match = re.search(r"^WINDOWS_CMDLINE_CAP = (\d+)$", source, re.MULTILINE)
    assert match is not None, (
        "glob_argv_guard.py no longer declares WINDOWS_CMDLINE_CAP"
    )
    assert int(match.group(1)) == WINDOWS_CMDLINE_CAP == 32767


def test_transports_are_the_closed_pair() -> None:
    assert PROMPT_TRANSPORTS == ("file", "stdin")


# --- render_cmdline ------------------------------------------------------------------------


def test_render_cmdline_joins_with_spaces() -> None:
    assert render_cmdline(("codex", "exec", "-o", "out.txt")) == "codex exec -o out.txt"


def test_render_cmdline_quotes_an_element_containing_a_space() -> None:
    assert (
        render_cmdline(("codex", "C:/Program Files/x")) == 'codex "C:/Program Files/x"'
    )


def test_render_cmdline_quotes_an_empty_element() -> None:
    assert render_cmdline(("codex", "")) == 'codex ""'


def test_render_cmdline_quotes_an_element_containing_a_tab() -> None:
    assert render_cmdline(("codex", "a\tb")) == 'codex "a\tb"'


def test_render_cmdline_of_nothing_is_empty() -> None:
    assert render_cmdline(()) == ""


# --- build_argv: the prompt never reaches argv ---------------------------------------------


def test_file_transport_routes_the_prompt_to_a_path_not_to_argv() -> None:
    plan = build_argv(
        exe="codex.exe",
        flags=("exec", "--ignore-user-config"),
        prompt="a" * 40_000,
        transport="file",
        prompt_flag="--prompt-file",
        prompt_path="C:/tmp/p.txt",
    )
    assert plan.argv == (
        "codex.exe",
        "exec",
        "--ignore-user-config",
        "--prompt-file",
        "C:/tmp/p.txt",
    )
    assert plan.prompt_transport == "file"
    assert plan.prompt_path == "C:/tmp/p.txt"
    assert plan.stdin_payload is None
    assert plan.cmdline_len < WINDOWS_CMDLINE_CAP
    assert all("a" * 40_000 not in element for element in plan.argv)


def test_stdin_transport_routes_a_40kb_prompt_to_stdin() -> None:
    prompt = "x" * 40_960
    plan = build_argv(exe="grok.exe", flags=("-",), prompt=prompt, transport="stdin")
    assert plan.argv == ("grok.exe", "-")
    assert plan.stdin_payload == prompt
    assert plan.prompt_path is None
    assert plan.cmdline_len == len("grok.exe -") < WINDOWS_CMDLINE_CAP


def test_an_argv_element_carrying_the_prompt_is_refused() -> None:
    with pytest.raises(PromptOnArgv, match="prompt"):
        build_argv(
            exe="codex.exe",
            flags=("--message", "the whole prompt body"),
            prompt="the whole prompt body",
            transport="stdin",
        )


def test_an_equal_element_is_refused_at_ANY_prompt_length() -> None:
    """Rule 1: a bare argument equal to the prompt, however short."""
    with pytest.raises(PromptOnArgv):
        build_argv(exe="c.exe", flags=("p",), prompt="p", transport="stdin")


@pytest.mark.parametrize("delimiter", ["=", ":"])
def test_the_flag_equals_value_shape_is_refused_at_ANY_prompt_length(
    delimiter: str,
) -> None:
    """Rule 2: `--message=<body>` / `--message:<body>`, however short the body."""
    with pytest.raises(PromptOnArgv):
        build_argv(
            exe="codex.exe",
            flags=(f"--msg{delimiter}the whole prompt body",),
            prompt="the whole prompt body",
            transport="stdin",
        )


def test_a_long_prompt_embedded_anywhere_in_an_element_is_refused() -> None:
    """Rule 3: bare containment, once the prompt is long enough to be unambiguous."""
    prompt = "z" * MIN_SUBSTRING_SCAN_LEN
    with pytest.raises(PromptOnArgv):
        build_argv(
            exe="c.exe",
            flags=(f"--wrap{prompt}tail",),
            prompt=prompt,
            transport="stdin",
        )


def test_a_short_prompt_colliding_with_a_flag_token_is_NOT_a_false_positive() -> None:
    """Detector control in the GOOD state: the guard must not block valid work.

    A first draft used bare containment at every length and refused this exact call, because
    the one-char prompt "p" occurs inside `--output-last-message`.
    """
    plan = build_argv(
        exe="codex.exe", flags=("--output-last-message",), prompt="p", transport="stdin"
    )
    assert plan.stdin_payload == "p"


def test_the_containment_rule_is_off_one_char_below_the_threshold() -> None:
    """Boundary: len == threshold refuses, len == threshold - 1 does not."""
    short = "z" * (MIN_SUBSTRING_SCAN_LEN - 1)
    assert prompt_on_argv(f"--wrap{short}tail", short) is False
    long = "z" * MIN_SUBSTRING_SCAN_LEN
    assert prompt_on_argv(f"--wrap{long}tail", long) is True


def test_the_exe_itself_is_checked_for_the_prompt() -> None:
    with pytest.raises(PromptOnArgv):
        build_argv(exe="secret prompt", prompt="secret prompt", transport="stdin")


def test_an_empty_prompt_is_refused() -> None:
    with pytest.raises(ValueError, match="prompt"):
        build_argv(exe="codex.exe", prompt="", transport="stdin")


def test_an_unknown_transport_is_refused() -> None:
    with pytest.raises(ValueError, match="transport"):
        build_argv(exe="codex.exe", prompt="p", transport="argv")


def test_an_empty_exe_is_refused() -> None:
    with pytest.raises(ValueError, match="exe"):
        build_argv(exe="", prompt="p", transport="stdin")


def test_file_transport_requires_a_prompt_flag() -> None:
    with pytest.raises(ValueError, match="prompt_flag"):
        build_argv(exe="codex.exe", prompt="p", transport="file", prompt_path="p.txt")


def test_file_transport_requires_a_prompt_path() -> None:
    with pytest.raises(ValueError, match="prompt_path"):
        build_argv(exe="codex.exe", prompt="p", transport="file", prompt_flag="-f")


def test_stdin_transport_refuses_a_prompt_path() -> None:
    with pytest.raises(ValueError, match="prompt_path"):
        build_argv(exe="c.exe", prompt="p", transport="stdin", prompt_path="p.txt")


def test_stdin_transport_refuses_a_prompt_flag() -> None:
    with pytest.raises(ValueError, match="prompt_flag"):
        build_argv(exe="c.exe", prompt="p", transport="stdin", prompt_flag="-f")


# --- the cap boundary ---------------------------------------------------------------------


def _plan_with_cmdline_len(total: int) -> object:
    """Build a plan whose rendered command line is exactly ``total`` chars."""
    exe = "c.exe"
    filler = "b" * (total - len(exe) - 1)
    return build_argv(exe=exe, flags=(filler,), prompt="p", transport="stdin")


def test_a_command_line_exactly_at_the_cap_is_allowed() -> None:
    plan = _plan_with_cmdline_len(WINDOWS_CMDLINE_CAP)
    assert plan.cmdline_len == WINDOWS_CMDLINE_CAP  # type: ignore[attr-defined]


def test_one_char_over_the_cap_is_refused_with_the_win_arg_limit_reason() -> None:
    with pytest.raises(ArgvTooLong) as caught:
        _plan_with_cmdline_len(WINDOWS_CMDLINE_CAP + 1)
    assert caught.value.reason == "win-arg-limit"
    assert caught.value.cmdline_len == WINDOWS_CMDLINE_CAP + 1
    assert caught.value.cap == WINDOWS_CMDLINE_CAP


def test_the_cap_is_overridable_for_a_non_windows_rail() -> None:
    plan = build_argv(
        exe="c.exe", flags=("x" * 100,), prompt="p", transport="stdin", cap=200
    )
    assert plan.cmdline_len == 106


# --- hardening (R5) -----------------------------------------------------------------------


def test_missing_hardening_lists_the_absent_flags() -> None:
    assert missing_hardening(("codex.exe", "exec"), ("--ignore-user-config",)) == (
        "--ignore-user-config",
    )


def test_missing_hardening_is_empty_when_every_flag_is_present() -> None:
    argv = ("codex.exe", "exec", "--ignore-user-config", "--skip-git-repo-check")
    assert (
        missing_hardening(argv, ("--ignore-user-config", "--skip-git-repo-check")) == ()
    )


def test_missing_hardening_matches_a_whole_element_not_a_substring() -> None:
    """`--ignore-user-configuration` must NOT satisfy `--ignore-user-config`."""
    assert missing_hardening(
        ("c.exe", "--ignore-user-configuration"), ("--ignore-user-config",)
    ) == ("--ignore-user-config",)


def test_build_for_rail_injects_the_rails_hardening_flags() -> None:
    rail = RailSpec(
        name="codex",
        exe="codex.exe",
        hardening=("--ignore-user-config",),
        prompt_transport="file",
        prompt_flag="--output-last-message",
    )
    plan = build_for_rail(rail, prompt="p", prompt_path="C:/tmp/r.txt", flags=("exec",))
    assert plan.argv == (
        "codex.exe",
        "exec",
        "--ignore-user-config",
        "--output-last-message",
        "C:/tmp/r.txt",
    )


def test_build_for_rail_refuses_a_caller_that_strips_a_hardening_flag() -> None:
    """The RED condition for R5: a non-interactive rail invocation missing its hardening."""
    rail = RailSpec(name="codex", exe="codex.exe", hardening=("--ignore-user-config",))
    with pytest.raises(PolicyViolation) as caught:
        build_for_rail(rail, prompt="p", flags=(), inject_hardening=False)
    assert caught.value.reason == "policy-violation"
    assert caught.value.missing == ("--ignore-user-config",)


def test_build_for_rail_uses_stdin_when_the_rail_declares_it() -> None:
    rail = RailSpec(name="grok", exe="grok.exe", prompt_transport="stdin")
    plan = build_for_rail(rail, prompt="hello")
    assert plan.stdin_payload == "hello"
    assert plan.argv == ("grok.exe",)


def test_a_rail_spec_declaring_an_unknown_transport_is_refused() -> None:
    rail = RailSpec(name="bad", exe="b.exe", prompt_transport="argv")
    with pytest.raises(ValueError, match="transport"):
        build_for_rail(rail, prompt="p")
