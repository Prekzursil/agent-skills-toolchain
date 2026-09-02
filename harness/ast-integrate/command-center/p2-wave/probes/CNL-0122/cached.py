"""Negative control: a runtime that returns a cached transcript and ignores seeds.

Identical-seed replay cannot detect this. Single-seed perturbation must.
"""
from __future__ import annotations

from typing import Any


class CachedTranscriptRuntime:
    def __init__(self, cached: bytes) -> None:
        self._cached = cached
        self.hits = 0

    def transcript(self, seeds: dict[str, int]) -> bytes:
        del seeds  # ignored on purpose — this is the defect under test
        self.hits += 1
        return self._cached


def perturbation_verdict(good: bytes, maybe_perturbed: bytes) -> dict[str, Any]:
    diverged = good != maybe_perturbed
    if diverged:
        return {
            "diverged": True,
            "verdict": "ACCEPT",
            "why": "perturbed-seed-changed-transcript",
        }
    return {
        "diverged": False,
        "verdict": "REJECT",
        "why": "frozen-or-cached-transcript",
    }
