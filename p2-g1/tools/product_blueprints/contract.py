"""Blueprint contract helpers."""
from __future__ import annotations

from product_blueprints.registry import BLUEPRINT_IDS


def required_ids() -> tuple[str, ...]:
    return BLUEPRINT_IDS
