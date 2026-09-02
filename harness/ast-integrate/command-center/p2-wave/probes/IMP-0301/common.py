#!/usr/bin/env python3
"""Shared probe paths and independent recount helpers for IMP-0301."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from council.quota.targets import evaluate  # noqa: E402

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def spec() -> dict[str, Any]:
    return load("council_spec.json")


def independent_counts(ideas: list[dict[str, Any]], declared: list[str]) -> dict[str, int]:
    tally: Counter[str] = Counter()
    for idea in ideas:
        cat = str(idea.get("category") or "").strip()
        if cat:
            tally[cat] += 1
    return {name: int(tally.get(name, 0)) for name in declared}


def independent_tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def independent_jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def independent_simpson(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    return 1.0 - sum((n / total) ** 2 for n in counts.values())


def result_by_id(report: dict[str, Any], tid: str) -> dict[str, Any]:
    for row in report.get("results") or []:
        if row.get("id") == tid:
            return row
    raise KeyError(tid)


def declared() -> list[str]:
    return ["alpha", "beta", "gamma"]
