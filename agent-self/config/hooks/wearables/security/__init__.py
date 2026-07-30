"""Fail-CLOSED security controls for the wearables pipeline.

These are the ONE exception to the AGENTS.md fail-open default: the egress
chokepoint and secret-scrubber DENY on any error or unclassifiable input.

"Unclassifiable input" includes a FIELD whose runtime value does not match its
declared type. ``EgressRequest`` is a plain frozen dataclass, and a dataclass
annotation performs no runtime validation -- ``allow_derived_egress="false"``
constructs successfully. ``egress_guard`` therefore type-checks that flag itself
and denies a non-bool rather than reading it for truthiness, because every
non-empty string (including the literal ``"false"``) is truthy in Python and
would otherwise read as an affirmative downgrade.
"""

__all__ = ["egress"]
