"""The in-process FAKE rail: scripted responses, injected clock, zero network."""

from __future__ import annotations

import pytest

from agentspec.argv import build_argv
from agentspec.clock import FixedClock
from agentspec.evals.fake_rail import (
    DispatchRefused,
    FakeRail,
    ScriptExhausted,
    ScriptedResponse,
)

PLAN = build_argv(exe="fake.exe", prompt="do it", transport="stdin")


def _rail(*responses: ScriptedResponse, start_ms: int = 0) -> tuple[FakeRail, FixedClock]:
    clock = FixedClock(start_ms=start_ms)
    return FakeRail(script={"u1": responses}, clock=clock), clock


def test_the_rail_returns_the_scripted_response() -> None:
    rail, _ = _rail(ScriptedResponse(exit_code=0, receipt=b'{"status":"ok"}'))
    result = rail.dispatch(unit_id="u1", plan=PLAN, timeout_s=60, awaited=True)
    assert result.exit_code == 0
    assert result.receipt_bytes == b'{"status":"ok"}'


def test_wall_ms_comes_from_the_INJECTED_clock_so_two_runs_agree() -> None:
    first, _ = _rail(ScriptedResponse(exit_code=0, receipt=b"ok", wall_ms_delta=1234))
    second, _ = _rail(ScriptedResponse(exit_code=0, receipt=b"ok", wall_ms_delta=1234))
    a = first.dispatch(unit_id="u1", plan=PLAN, timeout_s=60, awaited=True)
    b = second.dispatch(unit_id="u1", plan=PLAN, timeout_s=60, awaited=True)
    assert a.wall_ms == b.wall_ms == 1234


def test_the_clock_advances_by_the_scripted_delta() -> None:
    rail, clock = _rail(ScriptedResponse(exit_code=0, receipt=b"ok", wall_ms_delta=40))
    rail.dispatch(unit_id="u1", plan=PLAN, timeout_s=60, awaited=True)
    assert clock.now_ms() == 40


def test_successive_calls_consume_successive_scripted_responses() -> None:
    rail, _ = _rail(
        ScriptedResponse(exit_code=1, receipt=None),
        ScriptedResponse(exit_code=0, receipt=b"ok"),
    )
    assert rail.dispatch(unit_id="u1", plan=PLAN, timeout_s=60, awaited=True).exit_code == 1
    assert rail.dispatch(unit_id="u1", plan=PLAN, timeout_s=60, awaited=True).exit_code == 0


def test_every_dispatch_is_recorded_with_its_argv_and_timeout() -> None:
    rail, _ = _rail(ScriptedResponse(exit_code=0, receipt=b"ok"))
    rail.dispatch(unit_id="u1", plan=PLAN, timeout_s=90, awaited=True)
    assert len(rail.calls) == 1
    call = rail.calls[0]
    assert call.unit_id == "u1"
    assert call.argv == ("fake.exe",)
    assert call.stdin_payload == "do it"
    assert call.timeout_s == 90
    assert call.attempt == 1
    assert call.awaited is True


def test_a_backgrounded_awaited_dispatch_is_REFUSED_by_the_rail() -> None:
    rail, _ = _rail(ScriptedResponse(exit_code=0, receipt=b"ok"))
    with pytest.raises(DispatchRefused) as caught:
        rail.dispatch(unit_id="u1", plan=PLAN, timeout_s=60, awaited=True, background=True)
    assert caught.value.reason == "policy-violation"
    assert caught.value.violations == ("background-on-awaited-dispatch",)
    assert rail.calls == ()


def test_a_dispatch_with_no_timeout_is_REFUSED_by_the_rail() -> None:
    rail, _ = _rail(ScriptedResponse(exit_code=0, receipt=b"ok"))
    with pytest.raises(DispatchRefused) as caught:
        rail.dispatch(unit_id="u1", plan=PLAN, timeout_s=None, awaited=True)
    assert caught.value.violations == ("missing-timeout",)


def test_an_unscripted_unit_raises_rather_than_inventing_a_result() -> None:
    rail, _ = _rail(ScriptedResponse(exit_code=0, receipt=b"ok"))
    with pytest.raises(ScriptExhausted, match="ghost"):
        rail.dispatch(unit_id="ghost", plan=PLAN, timeout_s=60, awaited=True)


def test_running_past_the_end_of_a_script_raises() -> None:
    rail, _ = _rail(ScriptedResponse(exit_code=0, receipt=b"ok"))
    rail.dispatch(unit_id="u1", plan=PLAN, timeout_s=60, awaited=True)
    with pytest.raises(ScriptExhausted, match="u1"):
        rail.dispatch(unit_id="u1", plan=PLAN, timeout_s=60, awaited=True)


def test_the_progress_stream_is_carried_but_never_becomes_the_receipt() -> None:
    rail, _ = _rail(
        ScriptedResponse(exit_code=0, receipt=None, progress="[fake] working\n[fake] done")
    )
    result = rail.dispatch(unit_id="u1", plan=PLAN, timeout_s=60, awaited=True)
    assert result.progress.startswith("[fake]")
    assert result.receipt_bytes is None


def test_the_rail_performs_no_io_and_needs_no_network() -> None:
    """Structural claim, checked structurally: the module imports only agentspec + stdlib
    typing/dataclasses, and NOTHING that could open a socket or spawn a process."""
    import agentspec.evals.fake_rail as mod

    source = __import__("pathlib").Path(mod.__file__).read_text(encoding="utf-8")
    for banned in ("import socket", "import subprocess", "import urllib", "import requests"):
        assert banned not in source


def test_a_scripted_response_is_frozen() -> None:
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        ScriptedResponse(exit_code=0, receipt=None).exit_code = 1  # type: ignore[misc]


def test_a_dispatch_record_is_frozen() -> None:
    import dataclasses

    rail, _ = _rail(ScriptedResponse(exit_code=0, receipt=b"ok"))
    rail.dispatch(unit_id="u1", plan=PLAN, timeout_s=60, awaited=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rail.calls[0].timeout_s = 1  # type: ignore[misc]
