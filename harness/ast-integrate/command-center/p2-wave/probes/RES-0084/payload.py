#!/usr/bin/env python3
"""Read measurement payload from a receipt-shaped or legacy-flat artifact."""
from __future__ import annotations


def payload(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}

    def pick(key, default=None):
        if key in report and report[key] is not None:
            return report[key]
        return doc.get(key, default)

    return {
        "recorded_runs": pick("recorded_runs") or {},
        "fixtures": pick("fixtures") or {},
        "both_states": pick("both_states") or {},
        "blind_spot": pick("blind_spot") or {},
        "measured_threshold": pick("measured_threshold"),
        "adversarial_generator": pick("adversarial_generator") or {},
        "lexical_bands": pick("lexical_bands") or {},
        "state": doc.get("state"),
    }
