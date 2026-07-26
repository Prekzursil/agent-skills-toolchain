"""Time is INJECTED. There is no real clock anywhere in this package."""

from __future__ import annotations

import pytest

from agentspec.clock import Clock, FixedClock


def test_a_fixed_clock_starts_where_it_was_told_to() -> None:
    assert FixedClock().now_ms() == 0
    assert FixedClock(start_ms=1_700_000_000_000).now_ms() == 1_700_000_000_000


def test_time_does_not_move_unless_advanced() -> None:
    clock = FixedClock()
    assert clock.now_ms() == clock.now_ms() == 0


def test_advance_moves_time_and_returns_the_new_reading() -> None:
    clock = FixedClock()
    assert clock.advance(250) == 250
    assert clock.now_ms() == 250
    assert clock.advance(0) == 250


def test_advance_refuses_to_go_backwards() -> None:
    clock = FixedClock()
    with pytest.raises(ValueError, match="monotonic"):
        clock.advance(-1)


def test_advance_refuses_a_non_integer() -> None:
    with pytest.raises(TypeError, match="int"):
        FixedClock().advance(1.5)  # type: ignore[arg-type]


def test_advance_refuses_a_boolean() -> None:
    with pytest.raises(TypeError, match="int"):
        FixedClock().advance(True)  # type: ignore[arg-type]


def test_a_negative_start_is_refused() -> None:
    with pytest.raises(ValueError, match="start_ms"):
        FixedClock(start_ms=-1)


def test_fixed_clock_satisfies_the_clock_protocol() -> None:
    """The port is runtime-checkable so an adapter can assert its double conforms."""
    assert isinstance(FixedClock(), Clock)


def test_an_object_without_now_ms_does_not_satisfy_the_protocol() -> None:
    class NotAClock:
        pass

    assert not isinstance(NotAClock(), Clock)


def test_fixed_clock_also_satisfies_the_steppable_port() -> None:
    from agentspec.clock import SteppableClock

    assert isinstance(FixedClock(), SteppableClock)


def test_a_read_only_clock_is_a_clock_but_NOT_steppable() -> None:
    """The two ports are distinct on purpose: the fake rail needs to drive time."""
    from agentspec.clock import SteppableClock

    class ReadOnlyClock:
        def now_ms(self) -> int:
            return 7

    assert isinstance(ReadOnlyClock(), Clock)
    assert not isinstance(ReadOnlyClock(), SteppableClock)


def test_elapsed_ms_is_a_pure_subtraction_over_two_readings() -> None:
    from agentspec.clock import elapsed_ms

    clock = FixedClock(start_ms=100)
    start = clock.now_ms()
    clock.advance(40)
    assert elapsed_ms(start, clock.now_ms()) == 40


def test_elapsed_ms_refuses_a_backwards_interval() -> None:
    from agentspec.clock import elapsed_ms

    with pytest.raises(ValueError, match="monotonic"):
        elapsed_ms(10, 9)
