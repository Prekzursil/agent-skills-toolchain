"""Planted rival completion oracle — detector-control fixture (IMP-0192).

A fusion that *defines* judge locally is a second control plane (spec:10483).
This file is the known-broken state; it is not part of the admitted library.
"""


def judge(record):
    """Rival completion oracle. Must be detected as completion_oracle."""
    if record.get("ok"):
        return "SUCCESS"
    return "FAILED"
