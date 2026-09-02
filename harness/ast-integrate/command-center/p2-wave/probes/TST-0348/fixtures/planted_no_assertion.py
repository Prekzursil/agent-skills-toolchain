"""Planted control: a test with zero assertion-use nodes.

The word assert appears only as mention (string / comment). C16: that is not
asserting.
"""

MENTION = "remember to assert True and call assertEqual on the result"


def test_planted_no_assertion_tst0348():
    # comments may say assert nothing; comments are not AST Assert nodes
    payload = "assert 1 == 1"
    counted = payload.count("assert")
    _ = counted + len(MENTION)
