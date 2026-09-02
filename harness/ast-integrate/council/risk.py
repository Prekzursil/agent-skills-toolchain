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

__surface__ = 'council.risk'

RISK_CLASSES = "RISK_CLASSES"

def at_floor(*args, **kwargs):
    return _call('at_floor', *args, **kwargs)

def evaluate_config(*args, **kwargs):
    return _call('evaluate_config', *args, **kwargs)

def floor_enforcement_matrix(*args, **kwargs):
    return _call('floor_enforcement_matrix', *args, **kwargs)

def map_risk_class(*args, **kwargs):
    return _call('map_risk_class', *args, **kwargs)

def matrix_is_sound(*args, **kwargs):
    return _call('matrix_is_sound', *args, **kwargs)

EVENT_MUTATION_REFUSED = "EVENT_MUTATION_REFUSED"

def high_under_low_attack(*args, **kwargs):
    return _call('high_under_low_attack', *args, **kwargs)

def late_declaration_attack(*args, **kwargs):
    return _call('late_declaration_attack', *args, **kwargs)

FLOORS = "FLOORS"

EVENT_START_WITHOUT_CLASS = "EVENT_START_WITHOUT_CLASS"

class DeliberationSession(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('DeliberationSession', **kwargs)
        self.args = args

def immutability_holds(*args, **kwargs):
    return _call('immutability_holds', *args, **kwargs)

__all__ = ['RISK_CLASSES', 'at_floor', 'evaluate_config', 'floor_enforcement_matrix', 'map_risk_class', 'matrix_is_sound', 'EVENT_MUTATION_REFUSED', 'high_under_low_attack', 'late_declaration_attack', 'FLOORS', 'EVENT_START_WITHOUT_CLASS', 'DeliberationSession', 'immutability_holds']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

