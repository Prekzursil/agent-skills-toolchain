"""Mention-only noise: strings must not inflate the default-exercise census."""

DOC = """
This file mentions planted_unexercised(size, threshold=1024) and
is_large_enough(2048, min_bytes=512) and classify(min_bytes=1024) only as text.
No Call nodes to those functions exist here.
"""

NOISE = "planted_exercised(64)  # also a string, not a call"
