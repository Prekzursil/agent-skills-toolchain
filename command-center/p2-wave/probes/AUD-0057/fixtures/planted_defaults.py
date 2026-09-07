"""AUD-0057 planted defaults: one hole + one covered control.

Planted hole: every test passes ``threshold`` explicitly, so mutating
PLANTED_UNEXERCISED_DEFAULT must leave the weak suite GREEN.

Planted covered: tests omit ``threshold``, so mutating
PLANTED_EXERCISED_DEFAULT must turn the strong suite RED.
"""

PLANTED_UNEXERCISED_DEFAULT = 1024
PLANTED_EXERCISED_DEFAULT = 64


def planted_unexercised(size: int, threshold: int = PLANTED_UNEXERCISED_DEFAULT) -> bool:
    """Return True when size meets the (unexercised) default threshold."""
    return size >= threshold


def planted_exercised(size: int, threshold: int = PLANTED_EXERCISED_DEFAULT) -> bool:
    """Return True when size meets the (exercised) default threshold."""
    return size >= threshold
