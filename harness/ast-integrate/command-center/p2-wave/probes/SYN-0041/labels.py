"""Five-way taxonomy for SYN-0041. Exactly one label per item."""
from __future__ import annotations

LABELS = ("VERIFIED", "INFERRED", "UNVERIFIED", "REJECTED", "DEFERRED")
LABEL_SET = frozenset(LABELS)
EXTRA_LABEL_KEYS = frozenset({"labels", "secondary_label", "disposition", "tag"})
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
