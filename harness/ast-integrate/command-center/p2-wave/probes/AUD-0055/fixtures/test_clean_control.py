"""Negative control: a passing test with no skip/xfail marker.

The census must stay silent on this file (scanner both-states).
"""


def test_aud0055_clean_no_marker():
    assert 2 + 2 == 4
