"""Fixture payload for hello-skill 1.1.0 (beta channel).

The only difference from 1.0.0 is the version string, which is enough to give the two versions
different payload digests -- that difference is what makes update and rollback observable.
"""


def greet(name: str = "world") -> str:
    return f"hello, {name} -- from hello-skill 1.1.0"


def channel() -> str:
    return "beta"
