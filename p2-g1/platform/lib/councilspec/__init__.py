"""CouncilSpec reference implementation: typed schema, expression engine, semantic rules.

Contract:  platform/schema/councilspec.schema.json  (Draft 2020-12, the SSOT for metric names)
Examples:  platform/schema/examples/{valid,invalid}/ + EXPECTATIONS.json
Runner:    python -m councilspec.validate --conformance
"""

from .expression import (
    ExpressionError,
    MetricTypeError,
    MissingMetricError,
    evaluate,
    iter_leaves,
    parse,
    referenced_metrics,
    unparse,
)
from .registry import SCHEMA_PATH, all_metric_names, domain_of, metric_domains
from .semantics import Finding, check, errors
from .validate import run_conformance, validate_file, validate_spec

__all__ = [
    "ExpressionError",
    "MetricTypeError",
    "MissingMetricError",
    "parse",
    "unparse",
    "evaluate",
    "iter_leaves",
    "referenced_metrics",
    "SCHEMA_PATH",
    "metric_domains",
    "domain_of",
    "all_metric_names",
    "Finding",
    "check",
    "errors",
    "validate_spec",
    "validate_file",
    "run_conformance",
]
