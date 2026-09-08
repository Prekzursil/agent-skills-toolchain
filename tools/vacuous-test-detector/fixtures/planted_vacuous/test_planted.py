# Planted vacuous corpus for TST-0348.
# Each function is intentionally vacuous in exactly one primary class
# (swallowed_failure may co-occur). AST-only: strings mentioning "assert"
# must not count as assertions.


def test_no_assertion_mention_only():
    """Docstring mentions assert but never asserts."""
    msg = "this string mentions assert but does not assert"
    x = 1 + 1
    _ = (msg, x)


def test_constant_assertion_literal():
    assert True
    assert 1 == 1
    assert "a" == "a"


def test_mock_configured_assertion_only():
    from unittest.mock import MagicMock

    m = MagicMock()
    m.return_value = 42
    m(1, 2)
    assert m.called
    assert m.call_count == 1
    m.assert_called()


def test_swallowed_failure_bare():
    try:
        assert False, "this failure is swallowed"
    except AssertionError:
        pass
