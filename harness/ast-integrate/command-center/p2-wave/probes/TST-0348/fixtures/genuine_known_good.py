"""Known-good tests: real assertions. Must produce zero false positives.

Includes a mention of the word assert in a string so the scanner cannot
cheat by grepping payload text (C16 use-versus-mention).
"""

from unittest.mock import Mock


def add(left, right):
    return left + right


def parse_int(text):
    return int(text)


def test_genuine_add_with_mention_tst0348():
    note = "this test mentions assert True in a string"
    assert add(2, 3) == 5
    assert note.count("assert") == 1


def test_genuine_pytest_raises_tst0348():
    try:
        parse_int("x")
        raise AssertionError("parse_int should have failed")
    except ValueError:
        assert parse_int("7") == 7


def test_genuine_neighbour_mock_tst0348():
    """Mock is a neighbour; the assertion is about the subject under test."""
    client = Mock()
    client.compute.return_value = 42
    assert add(client.compute(), 1) == 43
