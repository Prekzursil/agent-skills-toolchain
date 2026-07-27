"""THE MUTATION GATE -- every load-bearing decision, reverted one at a time, must go RED.

A green suite proves the code passes its tests. It does NOT prove the tests would notice if the
decision were removed: a check that stays green in the BROKEN state is not a check. So each row
below carries three things --

* ``check``  the property, asserted over a value;
* ``sound``  the value the REAL code produces (the control);
* ``broken`` the value produced once that one decision is reverted.

``test_every_check_is_green_unmutated`` runs every control and requires PASS.
``test_every_mutation_turns_its_check_red`` runs every mutant and requires FAILURE.
A row that cannot do both is a row that proves nothing, and the registry test below refuses to
let one be added without both halves.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from agentspec.argv import (
    WINDOWS_CMDLINE_CAP,
    prompt_on_argv,
    render_cmdline,
)
from agentspec.envelope import ENVELOPE_FIELDS
from agentspec.spec import ReceiptSpec
from agentspec.taxonomy import family

import agentrail
from agentrail.deploy import decide, render_shim
from agentrail.plan import build_plan
from agentrail.rails import RailRow, expand_rows, load_rows, row_by_name
from agentrail.report import AGENTRAIL_REASONS, judge_result, transport_failure
from agentrail.resolve import resolve
from fakes import FakeFileSystem
from rival_scan import rival_declarations

PACKAGE_ROOT = Path(agentrail.__file__).parent
SHIPPED_CONFIG = (PACKAGE_ROOT / "rails.toml").read_text(encoding="utf-8")
HOME = "/home/u"
LONG_PROMPT = "PAYLOAD-" + "x" * 34_464
"""The MEASURED 34,472-char payload that produced Windows ``os error 206``."""

TEXT_SPEC = ReceiptSpec(fmt="text", forbidden_markers=("still in progress",))
SHIM_TARGET = "/home/u/.local/bin/agentrail.cmd"


def shipped_row(name: str) -> RailRow:
    rows = expand_rows(load_rows(SHIPPED_CONFIG), {"HOME": HOME})
    return row_by_name(rows, name)


# --------------------------------------------------------------------------------------------
# M1 -- the codex vendor-bin GLOB, reverted to a hardcoded path.
# --------------------------------------------------------------------------------------------

CODEX_TOMORROW = (
    f"{HOME}/AppData/Roaming/npm/node_modules/@openai/codex/node_modules/"
    "@openai/codex-win32-arm64/vendor/aarch64-pc-windows-msvc/bin/codex.exe"
)
CODEX_TODAY = (
    f"{HOME}/AppData/Roaming/npm/node_modules/@openai/codex/node_modules/"
    "@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe"
)


def _resolve_codex(row: RailRow) -> str:
    """Resolve against a machine where the npm package and target triple have MOVED."""
    return resolve(row, FakeFileSystem({CODEX_TOMORROW: b""})).exe


def check_codex_resolves_after_a_version_bump(exe: str) -> None:
    assert exe == CODEX_TOMORROW, (
        "the codex executable must be found by GLOB; a path pinned to today's package "
        "version and target triple silently breaks on the next `npm -g update`"
    )


def sound_codex_glob() -> str:
    return _resolve_codex(shipped_row("codex"))


def broken_codex_glob() -> str:
    """MUTATION: replace the glob with the path that resolves on THIS machine today."""
    from dataclasses import replace

    return _resolve_codex(replace(shipped_row("codex"), exe_globs=(CODEX_TODAY,)))


# --------------------------------------------------------------------------------------------
# M2 -- the SPILL, reverted so the prompt rides argv the way the vendor CLI asks.
# --------------------------------------------------------------------------------------------


def check_prompt_never_reaches_argv(argv: tuple[str, ...]) -> None:
    offenders = [element for element in argv if prompt_on_argv(element, LONG_PROMPT)]
    assert offenders == [], f"the prompt reached argv in {len(offenders)} element(s)"
    length = len(render_cmdline(argv))
    assert length <= WINDOWS_CMDLINE_CAP, (
        f"the command line is {length} chars against the measured Windows cap of "
        f"{WINDOWS_CMDLINE_CAP} -- this is os error 206"
    )


def sound_spill() -> tuple[str, ...]:
    """agentrail SPILLS an argv-native rail's prompt to a file."""
    return build_plan(
        shipped_row("gemini"),
        "gemini.exe",
        unit_id="u1",
        prompt=LONG_PROMPT,
        spill_dir="/spill",
    ).argv


def broken_spill() -> tuple[str, ...]:
    """MUTATION: honour ``native_transport = "argv"`` literally, as a naive adapter would."""
    row = shipped_row("gemini")
    assert row.native_transport == "argv", "this mutation needs an argv-native row"
    return ("gemini.exe", *row.base_flags, "-p", LONG_PROMPT)


# --------------------------------------------------------------------------------------------
# M3 -- the four mandatory envelope fields, reverted by deleting one.
# --------------------------------------------------------------------------------------------


def check_envelope_is_complete(payload: dict[str, Any]) -> None:
    missing = [field for field in ENVELOPE_FIELDS if field not in payload]
    assert missing == [], f"envelope is missing {missing}"
    assert payload["next_actions"], (
        "error-only output without next steps is a named anti-pattern"
    )


def sound_success_envelope() -> dict[str, Any]:
    return judge_result(
        "u1", exit_code=0, receipt_bytes=b"3 files changed", spec=TEXT_SPEC
    ).as_dict()


def broken_success_envelope() -> dict[str, Any]:
    """MUTATION: drop ``artifacts`` from the SUCCESS envelope."""
    payload = sound_success_envelope()
    del payload["artifacts"]
    return payload


def sound_error_envelope() -> dict[str, Any]:
    return transport_failure(
        "u1",
        "spawn-failed",
        detail="d",
        next_action="fix it",
        retry_instruction="r",
        stop_condition="s",
    ).as_dict()


def broken_error_envelope() -> dict[str, Any]:
    """MUTATION: drop ``next_actions`` from the ERROR envelope."""
    payload = sound_error_envelope()
    payload["next_actions"] = []
    return payload


# --------------------------------------------------------------------------------------------
# M4 -- a rail reason string, reverted to one outside agentspec's closed taxonomy.
# --------------------------------------------------------------------------------------------


def check_reasons_are_closed(reasons: tuple[str, ...]) -> None:
    outside = [reason for reason in reasons if not family(reason)]
    assert outside == [], (
        f"{outside} are outside the closed agentspec taxonomy; a consumer grepping the "
        f"taxonomy would never see these failures"
    )


def sound_reason_set() -> tuple[str, ...]:
    return (
        *AGENTRAIL_REASONS,
        transport_failure(
            "u1",
            "timeout-30s",
            detail="d",
            next_action="n",
            retry_instruction="r",
            stop_condition="s",
        ).observation.error.code,  # pyright: ignore[reportOptionalMemberAccess]
    )


def broken_reason_set() -> tuple[str, ...]:
    """MUTATION: mint a rail-flavoured reason that agentspec never declared."""
    return (*AGENTRAIL_REASONS, "rail-was-grumpy")


# --------------------------------------------------------------------------------------------
# M5 -- the deploy guard, reverted to an unconditional write.
# --------------------------------------------------------------------------------------------

EXISTING_SHIM = b"@echo off\nrem the operator's own hand-tuned shim\n"


def check_an_existing_shim_survives(state: bytes | None) -> None:
    assert state == EXISTING_SHIM, (
        "an existing shim was truncated -- `New-Item -Force` on a FILE destroys it, and an "
        "unconditional write is the same class of data loss"
    )


def sound_deploy_guard() -> bytes | None:
    fs = FakeFileSystem({SHIM_TARGET: EXISTING_SHIM})
    decision = decide(SHIM_TARGET, exists=fs.is_file(SHIM_TARGET))
    if decision.writes:
        fs.write_text(SHIM_TARGET, render_shim(["/tools"]))
    return fs.read_bytes(SHIM_TARGET)


def broken_deploy_guard() -> bytes | None:
    """MUTATION: skip the Test-Path guard and write unconditionally."""
    fs = FakeFileSystem({SHIM_TARGET: EXISTING_SHIM})
    fs.write_text(SHIM_TARGET, render_shim(["/tools"]))
    return fs.read_bytes(SHIM_TARGET)


# --------------------------------------------------------------------------------------------
# M6 -- the shim's exit-code propagation, reverted to the fail-open bare `endlocal`.
# --------------------------------------------------------------------------------------------


def check_the_shim_carries_the_exit_code_out(body: str) -> None:
    tail = [line.strip() for line in body.splitlines() if line.strip()][-1]
    assert tail == "endlocal & exit /b %errorlevel%", (
        f"the shim's last statement is {tail!r}; a bare `endlocal` RESETS ERRORLEVEL to 0, so "
        f"every failure exits 0 and every caller that branches on the exit code reads success"
    )


def sound_shim_exit_code() -> str:
    return render_shim(["/tools"])


def broken_shim_exit_code() -> str:
    """MUTATION: end on a bare ``endlocal``, which is what shipped and measured exit 0."""
    return render_shim(["/tools"]).replace(
        "endlocal & exit /b %errorlevel%", "endlocal"
    )


# --------------------------------------------------------------------------------------------
# M7 -- the JSON printer, reverted to a plain-text renderer that emits the control byte live.
#
# NOT `ensure_ascii=False`: that mutation was TRIED and it is an EQUIVALENT MUTANT. MEASURED --
# `json.dumps({"k": "a\x1b]8;;x\x07"}, ensure_ascii=False)` still emits ``, because RFC
# 8259 forbids a raw C0 control inside a JSON string and `json` escapes it whatever the flag
# says; `ensure_ascii` governs NON-ASCII only. Shipping that row would have been theatre: a
# mutation that changes nothing, guarded by a check that could never go red. The real invariant
# is "the envelope is printed AS JSON", and a plain-text renderer is what actually breaks it.
# --------------------------------------------------------------------------------------------

OSC8 = "\x1b]8;;http://attacker/steal\x07click\x1b]8;;\x07"


def check_no_live_escape_reaches_the_terminal(rendered: str) -> None:
    offenders = [
        f"U+{ord(char):04X}" for char in rendered if ord(char) < 0x20 and char != "\n"
    ]
    assert offenders == [], (
        f"the printed envelope carries live control byte(s) {offenders}; an OSC-8/OSC-52 "
        f"sequence from a rails.toml value or a --flag would execute in the operator's console"
    )


def _envelope_carrying_a_control_byte() -> Any:
    from agentrail.cli import CommandResult

    return CommandResult(
        observation=transport_failure(
            "u1",
            "spawn-failed",
            detail=f"the rail said {OSC8}",
            next_action="inspect it",
            retry_instruction="r",
            stop_condition="s",
            artifacts=(f"flag={OSC8}",),
        ).observation,
        terminal="FAILED:u1 spawn-failed",
    )


def sound_json_printer() -> str:
    from agentrail.cli import render

    return render(_envelope_carrying_a_control_byte())


def broken_json_printer() -> str:
    """MUTATION: a friendlier ``--text`` renderer -- the plausible change that breaks it."""
    result = _envelope_carrying_a_control_byte()
    observation = result.observation
    return "\n".join(
        (observation.summary, *observation.artifacts, *observation.next_actions)
    )


# --------------------------------------------------------------------------------------------
# M8 -- the anti-duplication scanner, reverted by forking an agentspec constant.
# --------------------------------------------------------------------------------------------


def check_no_rival_core(sources: tuple[tuple[str, str], ...]) -> None:
    rivals = [
        rival for name, source in sources for rival in rival_declarations(source, name)
    ]
    assert rivals == [], "\n".join(str(rival) for rival in rivals)


def sound_source_tree() -> tuple[tuple[str, str], ...]:
    return tuple(
        (path.name, path.read_text(encoding="utf-8"))
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
    )


def broken_source_tree() -> tuple[tuple[str, str], ...]:
    """MUTATION: fork the measured argv cap instead of importing it."""
    return (
        *sound_source_tree(),
        ("forked.py", "WINDOWS_CMDLINE_CAP = 32767\n"),
    )


# --------------------------------------------------------------------------------------------
# The registry, and the two gates over it.
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Mutation:
    """One reverted decision, with the control that proves the check works unmutated."""

    name: str
    check: Callable[[Any], None]
    sound: Callable[[], Any]
    broken: Callable[[], Any]
    refuses_to_build: bool = False
    """True when ``broken()`` is EXPECTED to raise, because the refusal IS the detection.

    Declared per row rather than inferred: an exception is only evidence if it was predicted.
    See :func:`_assert_mutation_is_detected` for the blind spot this closes.
    """


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        "codex-glob-to-hardcoded-path",
        check_codex_resolves_after_a_version_bump,
        sound_codex_glob,
        broken_codex_glob,
        # DECLARED: with the glob pinned to today's path and only tomorrow's build present,
        # nothing resolves at all, so `resolve` raises ExecutableNotFound before the check can
        # look at an exe. The refusal IS the detection -- but it now has to be predicted. The
        # old gate accepted it for the wrong reason: ANY exception counted, including a typo.
        refuses_to_build=True,
    ),
    Mutation(
        "spill-removed-prompt-rides-argv",
        check_prompt_never_reaches_argv,
        sound_spill,
        broken_spill,
    ),
    Mutation(
        "envelope-field-deleted-success-path",
        check_envelope_is_complete,
        sound_success_envelope,
        broken_success_envelope,
    ),
    Mutation(
        "envelope-field-deleted-error-path",
        check_envelope_is_complete,
        sound_error_envelope,
        broken_error_envelope,
    ),
    Mutation(
        "reason-outside-the-closed-taxonomy",
        check_reasons_are_closed,
        sound_reason_set,
        broken_reason_set,
    ),
    Mutation(
        "deploy-guard-to-unconditional-write",
        check_an_existing_shim_survives,
        sound_deploy_guard,
        broken_deploy_guard,
    ),
    Mutation(
        "shim-exit-code-swallowed-by-endlocal",
        check_the_shim_carries_the_exit_code_out,
        sound_shim_exit_code,
        broken_shim_exit_code,
    ),
    Mutation(
        "printer-downgraded-to-plain-text",
        check_no_live_escape_reaches_the_terminal,
        sound_json_printer,
        broken_json_printer,
    ),
    Mutation(
        "rival-core-argv-cap-forked",
        check_no_rival_core,
        sound_source_tree,
        broken_source_tree,
    ),
)

REQUIRED_ROWS: frozenset[str] = frozenset(
    {
        "codex-glob-to-hardcoded-path",
        "spill-removed-prompt-rides-argv",
        "envelope-field-deleted-success-path",
        "envelope-field-deleted-error-path",
        "reason-outside-the-closed-taxonomy",
        "deploy-guard-to-unconditional-write",
        "shim-exit-code-swallowed-by-endlocal",
        "printer-downgraded-to-plain-text",
    }
)
"""The rows the acceptance bar names explicitly, plus the two the repair pass added after a
reproduced defect. Deleting one must fail the suite."""


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda mutation: mutation.name)
def test_every_check_is_green_unmutated(mutation: Mutation) -> None:
    """THE CONTROL. Without it, a check that fails in BOTH states would look like a gate."""
    mutation.check(mutation.sound())


def _assert_mutation_is_detected(mutation: Mutation) -> None:
    """Reverting the decision must be DETECTED -- by an assertion or by a declared refusal.

    ``broken()`` is called OUTSIDE the ``pytest.raises`` block, and that placement is the whole
    point. With the call INSIDE it, a row whose body merely CRASHES -- a typo, a ``NameError``,
    a stale import -- satisfied the raises-block and was scored as "the mutation was detected".

    MEASURED: replacing one ``broken_*`` body with ``raise NameError("typo_in_my_mutation_row")``
    left this gate GREEN (``241 passed, 9 deselected``). The gate that exists to prove the
    other checks are real could not prove it about itself.

    A refusal to BUILD is still a legitimate detection -- a mutation the type system or a
    validator rejects outright is detected -- but it now has to be DECLARED by the row, so an
    accidental crash and an intended refusal stop looking identical.
    """
    try:
        value = mutation.broken()
    except Exception as exc:  # noqa: BLE001 -- classified below, never swallowed
        assert mutation.refuses_to_build, (
            f"{mutation.name}: broken() raised {type(exc).__name__}: {exc}. A mutation row that "
            f"merely crashes proves nothing about the check. Fix the row, or set "
            f"refuses_to_build=True if the refusal IS the detection."
        )
        return
    assert not mutation.refuses_to_build, (
        f"{mutation.name}: declared refuses_to_build but broken() returned a value"
    )
    with pytest.raises(Exception) as caught:
        mutation.check(value)
    assert not isinstance(caught.value, pytest.skip.Exception)


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda mutation: mutation.name)
def test_every_mutation_turns_its_check_red(mutation: Mutation) -> None:
    _assert_mutation_is_detected(mutation)


def _crashing_broken() -> dict[str, Any]:
    raise NameError("typo_in_my_mutation_row")


def test_the_gate_rejects_a_row_that_merely_crashes() -> None:
    """META-CONTROL. The measured blind spot, asserted so it cannot silently return.

    Without this, ``refuses_to_build`` would itself be an unexercised branch in the gate --
    exactly the "a check that never runs in the broken state is not a check" failure this file
    exists to prevent, one level up.
    """
    crashing = Mutation(
        "synthetic-crashing-row",
        check_envelope_is_complete,
        sound_success_envelope,
        _crashing_broken,
    )
    with pytest.raises(AssertionError, match="merely crashes proves nothing"):
        _assert_mutation_is_detected(crashing)


def test_the_gate_accepts_a_row_whose_refusal_to_build_is_the_detection() -> None:
    """The other half of the control: a DECLARED refusal must still count as detected."""
    declared = Mutation(
        "synthetic-declared-refusal",
        check_envelope_is_complete,
        sound_success_envelope,
        _crashing_broken,
        refuses_to_build=True,
    )
    _assert_mutation_is_detected(declared)


def test_the_gate_rejects_a_declared_refusal_that_quietly_stopped_refusing() -> None:
    """A row that stops raising must not keep its exemption -- that is how a gate rots."""
    stale = Mutation(
        "synthetic-stale-refusal",
        check_envelope_is_complete,
        sound_success_envelope,
        sound_success_envelope,
        refuses_to_build=True,
    )
    with pytest.raises(AssertionError, match="declared refuses_to_build"):
        _assert_mutation_is_detected(stale)


def test_the_registry_still_covers_every_named_decision() -> None:
    """A mutation row silently deleted is a gate silently removed."""
    names = {mutation.name for mutation in MUTATIONS}
    assert REQUIRED_ROWS <= names, f"missing rows: {sorted(REQUIRED_ROWS - names)}"
    assert len(names) == len(MUTATIONS), "duplicate mutation names"


def test_the_sound_and_broken_values_actually_differ() -> None:
    """A mutation producing the SAME value as the control would be theatre.

    Same blind spot as :func:`_assert_mutation_is_detected`, same fix: an exception is only
    accepted here when the row DECLARED it, so a crashing row cannot buy its exemption twice.
    """
    for mutation in MUTATIONS:
        try:
            broken = mutation.broken()
        except Exception as exc:  # noqa: BLE001 -- classified, never swallowed
            assert mutation.refuses_to_build, (
                f"{mutation.name}: broken() raised {type(exc).__name__}: {exc}"
            )
            continue
        assert broken != mutation.sound(), f"{mutation.name} mutated nothing"
