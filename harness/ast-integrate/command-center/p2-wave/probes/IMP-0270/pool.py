#!/usr/bin/env python3
"""Shared IMP-0270 sampling frame: unbalanced vendors, equal requested quotas.

The pool is deliberately 12/10/8 so uniform sampling cannot match a 2/2/2
quota request. That gap is the chi-square discriminator.
"""
from __future__ import annotations

from typing import Any

VENDOR_COUNTS = (("anthropic", 12), ("openai", 10), ("google", 8))
REQUESTED_STRATA = {"anthropic": 2, "openai": 2, "google": 2}
UNIFORM_K = 6
SEED_A = 20260824
SEED_B = 424242
N_DRAWS = 1000


def build_pool() -> list[dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    for vendor, count in VENDOR_COUNTS:
        for i in range(count):
            pool.append(
                {
                    "id": f"{vendor}-{i:02d}",
                    "vendor": vendor,
                    "model": f"{vendor}-model-{i % 3}",
                    "declared_expertise": ["sampling"] if i % 2 == 0 else ["review"],
                }
            )
    return pool
