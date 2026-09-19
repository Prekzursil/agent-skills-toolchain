"""Planted negative-control test module for AUD-0050.

Deliberately placed outside every CI pytest selector. The gate-coverage mapper
MUST list this path as an orphan; an empty orphan list with this fixture present
means the mapper is not discriminating.
"""


def test_planted_orphan_control_never_collected_by_ci() -> None:
    assert True
