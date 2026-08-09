"""Metric registry for CouncilSpec stopping expressions.

The registry is READ OUT OF THE SCHEMA rather than duplicated here. The schema file
`platform/schema/councilspec.schema.json` is the single source of truth for which metric
names exist and what value domain each one has; duplicating the lists in Python would
drift the moment either side is edited.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, FrozenSet, Tuple

SCHEMA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "schema", "councilspec.schema.json")
)

NUMERIC_OPS: Tuple[str, ...] = (">=", ">", "<=", "<", "==", "!=")
EQUALITY_OPS: Tuple[str, ...] = ("==", "!=")

CUSTOM_PREFIX = "custom:"


class RegistryError(RuntimeError):
    """Raised when the schema cannot supply a usable metric registry."""


@lru_cache(maxsize=4)
def load_schema(path: str = SCHEMA_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _leaf_enum(schema: Dict[str, Any], def_name: str) -> FrozenSet[str]:
    try:
        values = schema["$defs"][def_name]["properties"]["metric"]["enum"]
    except KeyError as exc:  # pragma: no cover - guarded by test_registry_detector_control
        raise RegistryError(f"{def_name}.properties.metric.enum missing from schema") from exc
    if not values:
        raise RegistryError(f"{def_name} metric enum is empty")
    return frozenset(values)


@lru_cache(maxsize=4)
def metric_domains(path: str = SCHEMA_PATH) -> Dict[str, FrozenSet[str]]:
    """Return {'numeric': {...}, 'boolean': {...}, 'enum': {...}} metric name sets."""
    schema = load_schema(path)
    domains = {
        "numeric": _leaf_enum(schema, "stop_leaf_numeric"),
        "boolean": _leaf_enum(schema, "stop_leaf_boolean"),
        "enum": _leaf_enum(schema, "stop_leaf_enum"),
    }
    overlap = (
        (domains["numeric"] & domains["boolean"])
        | (domains["numeric"] & domains["enum"])
        | (domains["boolean"] & domains["enum"])
    )
    if overlap:
        # The schema relies on `oneOf` over disjoint metric-name sets; an overlap would make
        # a leaf match two branches and fail validation for the wrong reason.
        raise RegistryError(f"metric name sets must be disjoint; overlapping: {sorted(overlap)}")
    return domains


@lru_cache(maxsize=4)
def enum_tokens(path: str = SCHEMA_PATH) -> FrozenSet[str]:
    schema = load_schema(path)
    try:
        values = schema["$defs"]["stop_leaf_enum"]["properties"]["value"]["enum"]
    except KeyError as exc:  # pragma: no cover
        raise RegistryError("stop_leaf_enum.properties.value.enum missing from schema") from exc
    return frozenset(values)


def domain_of(metric: str, path: str = SCHEMA_PATH) -> str:
    """Return 'numeric' | 'boolean' | 'enum' | 'custom' for a metric name."""
    if metric.startswith(CUSTOM_PREFIX):
        return "custom"
    for domain, names in metric_domains(path).items():
        if metric in names:
            return domain
    raise KeyError(metric)


def legal_ops(domain: str) -> Tuple[str, ...]:
    return NUMERIC_OPS if domain in ("numeric", "custom") else EQUALITY_OPS


def all_metric_names(path: str = SCHEMA_PATH) -> FrozenSet[str]:
    d = metric_domains(path)
    return d["numeric"] | d["boolean"] | d["enum"]
