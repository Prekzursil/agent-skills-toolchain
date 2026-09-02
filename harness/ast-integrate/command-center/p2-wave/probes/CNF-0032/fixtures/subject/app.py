"""Fixture subject for CNF-0032 hunk-revert causality.

Baseline is the FIXED form. The protocol copies this tree into a scratch
directory and reverse-applies one hunk at a time, leaving tests untouched.
"""


def clamp_non_negative(n: int) -> int:
    """Negatives become zero. Load-bearing hunk F1 is the ternary."""
    return 0 if n < 0 else n  # CNF-0032-F1


def tag(n: int) -> str:
    """String tag. Hunk F2 is comment-only and is not load-bearing."""
    # tagged for operators  # CNF-0032-F2
    return f"n={n}"


def divide_or_none(num: int, den: int):
    """Division that returns None on zero denominator.

    Hunk F3a is the comment breadcrumb (confounded / not load-bearing).
    Hunk F3b is the zero-denominator guard (load-bearing).
    """
    # handles zero denominator  # CNF-0032-F3a
    if den == 0:
        return None  # CNF-0032-F3b
    return num / den
