"""Planted control: try/except swallows the assertion failure it was meant to detect."""


def test_planted_swallowed_failure_tst0348():
    try:
        assert 1 == 2
    except Exception:
        pass
