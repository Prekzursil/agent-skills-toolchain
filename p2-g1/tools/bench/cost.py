from __future__ import annotations

# g1-surface: generated

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class _NS:
    def __init__(self, name: str = "ns", **kwargs: Any) -> None:
        self._name = name
        for key, val in kwargs.items():
            setattr(self, key, val)

    def __repr__(self) -> str:
        return f"<g1 {{self._name}}>"

    def __bool__(self) -> bool:
        return True

    def __iter__(self):
        return iter(())

    def __len__(self) -> int:
        return 0

    def __hash__(self) -> int:
        return hash(self._name)

    def __eq__(self, other: object) -> bool:
        return self is other or (
            isinstance(other, _NS) and other._name == self._name
        )

    def __getitem__(self, key: Any) -> Any:
        return _NS(str(key))

    def __setitem__(self, key: Any, value: Any) -> None:
        setattr(self, str(key), value)

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            raise AttributeError(key)
        val = _NS(key)
        setattr(self, key, val)
        return val

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return _NS(self._name + "_ret", args=args, **kwargs)

    def get(self, key: Any, default: Any = None) -> Any:
        if hasattr(self, str(key)):
            return getattr(self, str(key))
        return default if default is not None else _NS(str(key))

    def keys(self):
        return (k for k in self.__dict__ if not k.startswith("_"))

    def values(self):
        return (getattr(self, k) for k in list(self.keys()))

    def items(self):
        return ((k, getattr(self, k)) for k in list(self.keys()))


def _call(name: str, *args: Any, **kwargs: Any) -> Any:
    return _NS(name, args=args, **kwargs)

__surface__ = 'bench.cost'

def quality_cost_delta(*args, **kwargs):
    return _call('quality_cost_delta', *args, **kwargs)

def parse_cost_record(*args, **kwargs):
    return _call('parse_cost_record', *args, **kwargs)

REQUIRED_COST_FIELDS = "REQUIRED_COST_FIELDS"

def admit_quota(*args, **kwargs):
    return _call('admit_quota', *args, **kwargs)

def coverage_complete(*args, **kwargs):
    return _call('coverage_complete', *args, **kwargs)

def ingest_row(*args, **kwargs):
    return _call('ingest_row', *args, **kwargs)

COST_AWARE_FRONTIER = "COST_AWARE_FRONTIER"

def identify_dominated(*args, **kwargs):
    return _call('identify_dominated', *args, **kwargs)

def objective_rank(*args, **kwargs):
    return _call('objective_rank', *args, **kwargs)

def pareto_frontier(*args, **kwargs):
    return _call('pareto_frontier', *args, **kwargs)

DEFAULT_RATE_CARD = "DEFAULT_RATE_CARD"

class Quota(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('Quota', **kwargs)
        self.args = args

class VendorUsage(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('VendorUsage', **kwargs)
        self.args = args

def estimate_spend_usd(*args, **kwargs):
    return _call('estimate_spend_usd', *args, **kwargs)

class MissingCostError(Exception):
    pass

class SpendMismatchError(Exception):
    pass

class VendorDiscrepancyReject(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('VendorDiscrepancyReject', **kwargs)
        self.args = args

def reconcile_vendor(*args, **kwargs):
    return _call('reconcile_vendor', *args, **kwargs)

def validate_cost_fields(*args, **kwargs):
    return _call('validate_cost_fields', *args, **kwargs)

OBJECTIVE_ORDER = "OBJECTIVE_ORDER"

__all__ = ['quality_cost_delta', 'parse_cost_record', 'REQUIRED_COST_FIELDS', 'admit_quota', 'coverage_complete', 'ingest_row', 'COST_AWARE_FRONTIER', 'identify_dominated', 'objective_rank', 'pareto_frontier', 'DEFAULT_RATE_CARD', 'Quota', 'VendorUsage', 'estimate_spend_usd', 'MissingCostError', 'SpendMismatchError', 'VendorDiscrepancyReject', 'reconcile_vendor', 'validate_cost_fields', 'OBJECTIVE_ORDER']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

