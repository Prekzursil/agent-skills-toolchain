"""Both-states rival: redeclares dispatch retry constants and redefines plan_retry.

Not on the production walk path. Probe 1 feeds this file to the AST walker and
requires at least one hit, proving the detector is live.
"""

RETRYABLE_ONCE = ("everything",)
RATE_LIMIT_MAX_ATTEMPTS = 99
DISPATCH_RETRY_REASONS = frozenset({"everything"})


def plan_retry(reason, dispatch_failures, ledger=None):
    return None
