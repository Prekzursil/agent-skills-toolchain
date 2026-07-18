"""Fail-CLOSED security controls for the wearables pipeline.

These are the ONE exception to the AGENTS.md fail-open default: the egress
chokepoint and secret-scrubber DENY on any error or unclassifiable input.
"""

__all__ = ["egress"]
