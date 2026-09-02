"""Load registered library ids."""
from __future__ import annotations


def load_library() -> list[str]:
    from tools.library import registry

    registry.ensure_registered()
    return list(registry.IDS)
