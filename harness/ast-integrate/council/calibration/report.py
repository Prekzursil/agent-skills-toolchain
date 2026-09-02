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

__surface__ = 'council.calibration.report'

def generate_report(*args, **kwargs):
    return _call('generate_report', *args, **kwargs)

def hand_computed_predictions(*args, **kwargs):
    return _call('hand_computed_predictions', *args, **kwargs)

HAND_COMPUTED_ALICE_BRIER = "HAND_COMPUTED_ALICE_BRIER"

HAND_COMPUTED_ALICE_N = "HAND_COMPUTED_ALICE_N"

def write_calibration_store(*args, **kwargs):
    return _call('write_calibration_store', *args, **kwargs)

INSUFFICIENT_MARKER = "INSUFFICIENT_MARKER"

def detect_bare_confident_score(*args, **kwargs):
    return _call('detect_bare_confident_score', *args, **kwargs)

def format_estimate(*args, **kwargs):
    return _call('format_estimate', *args, **kwargs)

def is_honest_insufficient(*args, **kwargs):
    return _call('is_honest_insufficient', *args, **kwargs)

def planted_bare_score_record(*args, **kwargs):
    return _call('planted_bare_score_record', *args, **kwargs)

__all__ = ['generate_report', 'hand_computed_predictions', 'HAND_COMPUTED_ALICE_BRIER', 'HAND_COMPUTED_ALICE_N', 'write_calibration_store', 'INSUFFICIENT_MARKER', 'detect_bare_confident_score', 'format_estimate', 'is_honest_insufficient', 'planted_bare_score_record']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

