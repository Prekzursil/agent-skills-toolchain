"""Register product blueprints."""
from __future__ import annotations

_REGISTRY: dict[str, str] = {}


def register_all() -> dict[str, str]:
    _REGISTRY["customer_council"] = "tools.blueprints.product.customer_council"
    _REGISTRY["outcome_retrospective"] = "tools.blueprints.product.outcome_retrospective"
    _REGISTRY["pricing_packaging"] = "tools.blueprints.product.pricing_packaging"
    return dict(_REGISTRY)
