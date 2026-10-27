"""Fixture payload for vulnerable-lib 1.0.0.

There is no actual vulnerability here and no exploit: the "vulnerability" is entirely a registry
fact (an entry in the signed advisory list). Shipping real vulnerable code to test a vulnerability
gate would be building the hazard in order to test the alarm.
"""

ADVISORY = "adv:2026-0001"


def status() -> str:
    return f"vulnerable-lib 1.0.0 is covered by {ADVISORY}; fixed in 1.0.1 (never published in the fixture)"
