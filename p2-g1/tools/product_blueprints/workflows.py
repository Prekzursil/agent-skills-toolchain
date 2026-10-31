"""Workflow records for product blueprints."""
from __future__ import annotations

from product_blueprints.registry import list_blueprints


def all_workflows() -> list[dict]:
    return [dict(r.workflow) for r in list_blueprints()]
