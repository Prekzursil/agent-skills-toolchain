"""Named failure classes for CNF-0155 vendor-error attribution."""
from __future__ import annotations

TAXONOMY = ("overclaim", "false-pass", "contamination")

CONTAMINATION_MARKERS = (
    "command-center/receipts/",
    "implementer_verdict",
    "SUCCESS:IMP-",
)
