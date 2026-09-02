#!/usr/bin/env python3
"""Known-broken fixture: AND behaves as OR under partial evidence.

Two-valued rows stay AND-correct (T∧F=F). When one conjunct is Unknown and
the other is True, the mutant returns True (OR-like) instead of Unknown.
A 2-valued sample of the table cannot see this defect.
"""
from __future__ import annotations

from typing import Optional

Tri = Optional[bool]


def mutant_and(a: Tri, b: Tri) -> Tri:
    if a is None and b is True:
        return True
    if b is None and a is True:
        return True
    if a is False or b is False:
        return False
    if a is True and b is True:
        return True
    return None
