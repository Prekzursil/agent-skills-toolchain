"""Local grant coverage. tools/plugin/permission_diff.py is absent on this tree."""
from __future__ import annotations

from typing import Iterable


def covered_by_set(perm: str, grant: Iterable[str]) -> bool:
    name = str(perm).strip()
    granted = {str(p).strip() for p in grant}
    return name in granted
