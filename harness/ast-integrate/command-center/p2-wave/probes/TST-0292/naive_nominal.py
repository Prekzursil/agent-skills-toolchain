"""Planted-wrong correlator: two vendor names therefore two seats.

TST-0292-probe2 must reject this. Counting nameplates is the overclaim the
unit exists to catch.
"""
from __future__ import annotations


def always_two_seats(_rows_a, _rows_b) -> dict:
    return {
        "nominal": 2,
        "phi": None,
        "effective_seats": 2.0,
        "ignored_joint_table": True,
        "claim": "two vendor names therefore two independent seats",
    }
