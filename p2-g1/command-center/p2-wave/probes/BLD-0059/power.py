# Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was
# lost with the prior builder session; content follows the recorded role in
# the unit receipt (anchors re-resolve live). Prior reviewer closure kept.
"""Instrument for BLD-0059: the sampling power calculator (role: power-
calculator). detect(n, p) = 1 - (1 - p)**n -- probability that a uniform
random sample of n units from a class with defect prevalence p includes at
least one defective unit. Acceptance rule: detect >= claimed confidence."""
from __future__ import annotations


def detect(n: int, p: float) -> float:
    return 1.0 - (1.0 - p) ** n


def accept(n: int, p: float, confidence: float) -> tuple[bool, float]:
    d = detect(n, p)
    return d >= confidence, d
