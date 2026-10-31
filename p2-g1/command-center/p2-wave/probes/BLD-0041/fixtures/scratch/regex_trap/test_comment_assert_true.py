"""Regex trap: the words `assert True` appear only in comments and a string.

A regex census would flag this file. AST inspection must not.
"""


def test_regex_trap_comment():
    # assert True
    note = "assert True"
    value = 2 * 21
    assert value == 42
    assert note.startswith("assert")
