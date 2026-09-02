"""Behaviour under test for CC-0014 mutation records.

REQUIRED_MIN is the constant whose un-exercised default historically left the
suite green after a revert: every case passed the value explicitly.
"""

REQUIRED_MIN = 3


def accept(items, minimum=None):
    """Return True iff len(items) meets the floor.

    When *minimum* is omitted the module default REQUIRED_MIN is used. A test
    that always passes minimum= does not protect REQUIRED_MIN.
    """
    floor = REQUIRED_MIN if minimum is None else minimum
    return len(items) >= floor
