"""Index linter that names casefold claimants (IMP-0126)."""
from __future__ import annotations

from typing import Any

from marketplace.path_conflict import conflicts_from_index


def lint_index(index: dict[str, Any] | None = None, **kwargs: Any):
    if index is None:
        index = kwargs.get("document") or kwargs.get("root") or {}
    if not isinstance(index, dict):
        index = {}
    return conflicts_from_index(index)
