"""Tiny subject used by BLD-0040 planted oracle-strength controls.

compute_score is the function probe2 breaks (wrong-but-non-crashing return).
produce_report is the snapshot SUT: regen_golden.py writes its output as golden.json.
"""
from __future__ import annotations


def compute_score(values: list[int]) -> int:
    return sum(values)


def produce_report() -> dict:
    return {"sum": compute_score([1, 2, 3]), "ok": True}
