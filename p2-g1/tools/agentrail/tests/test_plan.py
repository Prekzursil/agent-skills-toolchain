"""Planning: the spill keeps the prompt off argv, and agentspec owns every other decision."""

from __future__ import annotations

import pytest
from agentspec.argv import ArgvTooLong, PromptOnArgv, prompt_on_argv

from agentrail.plan import (
    DispatchRefused,
    build_plan,
    plan_with_retry,
    spill_transport,
)
from agentrail.rails import ConfigError, RailRow

LONG_PROMPT = "PAYLOAD-" + "x" * 34_464
"""34,472 chars -- the MEASURED payload that produced Windows ``os error 206``."""


def row(**kwargs: object) -> RailRow:
    base: dict[str, object] = {
        "name": "demo",
        "receipt_format": "text",
        "receipt_forbidden_markers": ("in progress",),
    }
    base.update(kwargs)
    return RailRow(**base)  # pyright: ignore[reportArgumentType]


def plan(row_: RailRow, **kwargs: object) -> object:
    defaults: dict[str, object] = {
        "unit_id": "u1",
        "prompt": "do the thing",
        "spill_dir": "/tmp/spill",
    }
    defaults.update(kwargs)
    return build_plan(row_, "exe", **defaults)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    ("native", "prompt_flag", "expected", "spilled"),
    [
        ("stdin", None, "stdin", False),
        ("file", "--pf", "file", False),
        ("argv", "--pf", "file", True),
        ("argv", None, "stdin", True),
    ],
)
def test_spill_maps_every_native_transport_onto_a_legal_one(
    native: str, prompt_flag: str | None, expected: str, spilled: bool
) -> None:
    got = spill_transport(row(native_transport=native, prompt_flag=prompt_flag))
    assert got == (expected, spilled)


def test_an_argv_native_rail_never_puts_the_prompt_on_argv() -> None:
    """THE headline property, exercised with the measured 34,472-char payload."""
    built = build_plan(
        row(native_transport="argv", prompt_flag="--prompt-file"),
        "grok.exe",
        unit_id="u1",
        prompt=LONG_PROMPT,
        spill_dir="/tmp/spill",
    )
    assert built.spilled is True
    assert built.transport == "file"
    assert built.spill is not None
    assert built.spill.text == LONG_PROMPT
    assert built.spill.path == "/tmp/spill/u1.prompt.txt"
    assert not any(prompt_on_argv(element, LONG_PROMPT) for element in built.argv)
    assert built.argv_plan.cmdline_len < len(LONG_PROMPT)


def test_an_argv_native_rail_without_a_prompt_flag_spills_to_stdin() -> None:
    built = build_plan(
        row(native_transport="argv"),
        "agy.exe",
        unit_id="u1",
        prompt=LONG_PROMPT,
        spill_dir="/tmp/spill",
    )
    assert built.transport == "stdin"
    assert built.spill is None
    assert built.stdin_payload == LONG_PROMPT
    assert built.argv == ("agy.exe",)


def test_hardening_is_injected_and_verified_by_agentspec() -> None:
    built = build_plan(
        row(hardening=("--ignore-user-config",), base_flags=("exec",)),
        "codex.exe",
        unit_id="u1",
        prompt="p",
        spill_dir="/tmp",
    )
    assert built.argv == ("codex.exe", "exec", "--ignore-user-config")


def test_the_receipt_flag_pair_is_appended_only_when_both_halves_exist() -> None:
    with_receipt = build_plan(
        row(receipt_flag="-o"),
        "exe",
        unit_id="u1",
        prompt="p",
        spill_dir="/t",
        receipt_path="/t/r.txt",
    )
    assert with_receipt.argv == ("exe", "-o", "/t/r.txt")
    assert with_receipt.receipt_path == "/t/r.txt"

    no_path = build_plan(
        row(receipt_flag="-o"), "exe", unit_id="u1", prompt="p", spill_dir="/t"
    )
    assert no_path.argv == ("exe",)

    no_flag = build_plan(
        row(),
        "exe",
        unit_id="u1",
        prompt="p",
        spill_dir="/t",
        receipt_path="/t/r.txt",
    )
    assert no_flag.argv == ("exe",)


def test_caller_flags_land_before_hardening() -> None:
    built = build_plan(
        row(base_flags=("run",), hardening=("--safe",)),
        "exe",
        unit_id="u1",
        prompt="p",
        spill_dir="/t",
        flags=("--extra",),
    )
    assert built.argv == ("exe", "run", "--extra", "--safe")


@pytest.mark.parametrize(
    "unit_id",
    [
        "",
        "   ",
        "wu 7",
        "wu\t7",
        "wu\x1b[31m7",
        "wu\x00 7",
        "\x1b]8;;http://evil\x07wu1",
    ],
    ids=[
        "empty",
        "all-whitespace",
        "embedded-space",
        "embedded-tab",
        "csi-colour",
        "nul-byte",
        "osc-8-hyperlink",
    ],
)
def test_an_id_agentspec_could_not_render_is_refused_before_anything_runs(
    unit_id: str,
) -> None:
    """REGRESSION. Two validators for one field, disagreeing across a dispatch.

    ``build_plan`` used to gate on ``unit_id.strip()``, which accepts every row here except the
    first two, while :func:`agentspec.terminal.success_line` rejects all seven. The dispatch
    therefore RAN and the completed result was then destroyed by an unenveloped ``ValueError``
    raised while rendering the marker. The old test covered only ``"   "`` -- the adjacent
    case, not the defect case -- which is why 100% line coverage did not see it.
    """
    with pytest.raises(ConfigError, match="unit_id"):
        build_plan(row(), "exe", unit_id=unit_id, prompt="p", spill_dir="/t")


def test_the_unit_id_rule_is_agentspecs_own_and_is_not_paraphrased() -> None:
    """The anti-drift property: agree with agentspec by CALLING it, not by matching it.

    Control included -- a legal id must still pass, or a validator that refused everything
    would satisfy the disagreement check while breaking the package.
    """
    from agentspec.terminal import success_line

    from agentrail.plan import checked_unit_id

    for candidate in ("wu-1", "u1", "wu.7", "wü-1"):
        assert checked_unit_id(candidate) == candidate
        assert success_line(candidate) == f"SUCCESS:{candidate}"

    for candidate in ("", "wu 7", "wu\x1b7"):
        with pytest.raises(ConfigError):
            checked_unit_id(candidate)
        with pytest.raises(ValueError, match="unit_id must be"):
            success_line(candidate)


@pytest.mark.parametrize(
    "unit_id",
    ["../../../../evil/pwned", "a/b", "a\\b", "C:evil", "..\\..\\evil"],
    ids=[
        "traversal",
        "forward-slash",
        "backslash",
        "drive-relative",
        "windows-traversal",
    ],
)
def test_an_id_that_would_escape_the_spill_dir_is_refused(unit_id: str) -> None:
    """MEASURED escapes, both of them silent, from ``<spill_dir>/<unit_id>.prompt.txt``.

    * ``"../../../../evil/pwned"`` wrote to ``S:/spill/../../../../evil/pwned.prompt.txt``,
      creating directories outside the declared spill dir and truncating any ``*.prompt.txt``
      already there, with caller-supplied content.
    * ``"C:evil"`` is worse: Windows reads ``C:evil.prompt.txt`` as DRIVE-RELATIVE, so the
      write landed at the current directory of drive ``C:`` and the spill dir stayed empty --
      no exception, no trace.

    agentspec accepts all of these (they are printable and whitespace-free) and is right to:
    they are legal MARKERS. Containment is agentrail's own rule because only agentrail turns
    the id into a filename.
    """
    with pytest.raises(ConfigError, match="spill"):
        build_plan(row(), "exe", unit_id=unit_id, prompt="p", spill_dir="/t")


def test_a_legal_unit_id_still_builds_the_expected_spill_path() -> None:
    """The control for the containment rule: it must not have banned ordinary ids."""
    built = build_plan(
        row(native_transport="file", prompt_flag="--prompt-file"),
        "exe",
        unit_id="wu-7.retry2",
        prompt="p",
        spill_dir="/t",
    )
    assert built.spill is not None
    assert built.spill.path == "/t/wu-7.retry2.prompt.txt"


def test_the_rows_default_timeout_applies_when_none_is_given() -> None:
    built = build_plan(
        row(default_timeout_s=77), "exe", unit_id="u1", prompt="p", spill_dir="/t"
    )
    assert built.timeout_s == 77
    explicit = build_plan(
        row(default_timeout_s=77),
        "exe",
        unit_id="u1",
        prompt="p",
        spill_dir="/t",
        timeout_s=5,
    )
    assert explicit.timeout_s == 5


@pytest.mark.parametrize(
    ("kwargs", "violation"),
    [
        ({"background": True, "awaited": True}, "background-on-awaited-dispatch"),
        ({"timeout_s": 0}, "nonpositive-timeout"),
    ],
)
def test_an_illegal_dispatch_shape_is_refused_before_the_rail_is_touched(
    kwargs: dict[str, object], violation: str
) -> None:
    with pytest.raises(DispatchRefused) as caught:
        build_plan(row(), "exe", unit_id="u1", prompt="p", spill_dir="/t", **kwargs)  # pyright: ignore[reportArgumentType]
    assert violation in caught.value.violations
    assert caught.value.reason == "policy-violation"


def test_a_prompt_that_collides_with_a_caller_flag_is_refused_by_agentspec() -> None:
    with pytest.raises(PromptOnArgv):
        build_plan(
            row(),
            "exe",
            unit_id="u1",
            prompt="--extra",
            spill_dir="/t",
            flags=("--extra",),
        )


def test_the_spill_dir_separator_is_normalised() -> None:
    for directory in ("/tmp/spill", "/tmp/spill/", "\\tmp\\spill\\"):
        built = build_plan(
            row(native_transport="file", prompt_flag="--pf"),
            "exe",
            unit_id="u1",
            prompt="p",
            spill_dir=directory,
        )
        assert built.spill is not None
        assert built.spill.path.endswith("/u1.prompt.txt")
        assert "//u1" not in built.spill.path


def test_force_transport_overrides_the_spill_decision() -> None:
    built = build_plan(
        row(native_transport="file", prompt_flag="--pf"),
        "exe",
        unit_id="u1",
        prompt="p",
        spill_dir="/t",
        force_transport="stdin",
    )
    assert built.transport == "stdin"
    assert built.spill is None


def test_plan_with_retry_is_a_passthrough_when_argv_fits() -> None:
    built = plan_with_retry(row(), "exe", unit_id="u1", prompt="p", spill_dir="/t")
    assert built.retries == ()
    assert built.attempt == 1


def test_over_cap_argv_retries_once_onto_the_shorter_stdin_transport() -> None:
    """agentspec.retry owns the decision; agentrail owns the only lever it has."""
    fat = row(
        native_transport="file",
        prompt_flag="--prompt-file",
        base_flags=("--pad", "y" * 200),
        cap=240,
    )
    with pytest.raises(ArgvTooLong):
        build_plan(
            fat, "exe", unit_id="u1", prompt="p", spill_dir="/very/long/spill/dir"
        )

    built = plan_with_retry(
        fat, "exe", unit_id="u1", prompt="p", spill_dir="/very/long/spill/dir"
    )
    assert built.transport == "stdin"
    assert built.attempt == 2
    assert len(built.retries) == 1
    assert built.retries[0].retry is True
    assert "file/stdin" in built.retries[0].rationale


def test_an_already_minimal_transport_has_no_shorter_form_and_propagates() -> None:
    fat = row(base_flags=("--pad", "y" * 400), cap=100)
    with pytest.raises(ArgvTooLong) as caught:
        plan_with_retry(fat, "exe", unit_id="u1", prompt="p", spill_dir="/t")
    assert caught.value.cap == 100
    assert caught.value.reason == "win-arg-limit"


def test_a_second_attempt_gets_agentspecs_stop_answer_not_another_retry() -> None:
    fat = row(
        native_transport="file",
        prompt_flag="--prompt-file",
        base_flags=("--pad", "y" * 200),
        cap=240,
    )
    with pytest.raises(ArgvTooLong):
        plan_with_retry(
            fat,
            "exe",
            unit_id="u1",
            prompt="p",
            spill_dir="/very/long/spill/dir",
            attempt=2,
        )
