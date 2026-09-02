"""Public API of the before-state fixture package.

Private helpers exist so a text-search enumerator would over-count them.
"""

from __future__ import annotations

__all__ = ["PublicAlpha", "PublicBeta", "legacy_name", "compute"]


class PublicAlpha:
    """Stable public type."""


class PublicBeta:
    """Public type consumed outside this repo. Removing it is a breaking change."""


def legacy_name() -> str:
    return "old"


def compute(value: int) -> int:
    return _secret_scale(value)


def _secret_scale(value: int) -> int:
    """Private helper. Grep-for-def counts this; introspection via __all__ must not."""
    return value * 2
