"""Planted outside every CI pytest selector.

AUD-0050 control: this path must appear in the orphan list. A mapper that
reports an empty orphan list on this fixture is not discriminating.
"""


def test_deliberately_ungated_control() -> None:
    assert True
