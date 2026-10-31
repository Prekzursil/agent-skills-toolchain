"""Fixture payload for dep-consumer 1.0.0.

Names its dependency in code as well as in the manifest so a reader can see the two agree. The
installer never executes this file -- installation copies bytes and verifies digests; it does not
run payloads. That is deliberate: a marketplace that executed payload code at install time would
make every gate that runs afterwards pointless.
"""

REQUIRES = ("hello-skill", "^1.0.0")


def describe() -> str:
    return f"dep-consumer 1.0.0 requires {REQUIRES[0]} {REQUIRES[1]}"
