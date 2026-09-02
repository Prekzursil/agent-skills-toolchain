"""Public API of the after-state fixture package.

PublicBeta is gone and is NOT named in the changelog (undocumented removal).
legacy_name is renamed to current_name (documented).
"""

from __future__ import annotations

__all__ = ["PublicAlpha", "current_name", "compute"]


class PublicAlpha:
    """Stable public type."""


def current_name() -> str:
    return "new"


def compute(value: int) -> int:
    return _secret_scale(value)


def _secret_scale(value: int) -> int:
    """Private helper. Grep-for-def counts this; introspection via __all__ must not."""
    return value * 2
