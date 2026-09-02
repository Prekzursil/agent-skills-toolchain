"""A real test with no mutation record — must register UNPROVEN."""

from subject import accept


def test_empty_list_rejected_at_explicit_one():
    assert accept([], minimum=1) is False
