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

__surface__ = 'council.gain'

def bootstrap_mean_diff_ci(*args, **kwargs):
    return _call('bootstrap_mean_diff_ci', *args, **kwargs)

def cohens_d(*args, **kwargs):
    return _call('cohens_d', *args, **kwargs)

def mean(*args, **kwargs):
    return _call('mean', *args, **kwargs)

def score_transcript(*args, **kwargs):
    return _call('score_transcript', *args, **kwargs)

def strip_scores(*args, **kwargs):
    return _call('strip_scores', *args, **kwargs)

GAIN_FLOOR = "GAIN_FLOOR"

METRIC_KIND = "METRIC_KIND"

SAFETY_CAP = "SAFETY_CAP"

STOP_PATIENCE = "STOP_PATIENCE"

def evaluate_stop(*args, **kwargs):
    return _call('evaluate_stop', *args, **kwargs)

def evaluate_stop_lexical(*args, **kwargs):
    return _call('evaluate_stop_lexical', *args, **kwargs)

def round_gain_crosses_floor(*args, **kwargs):
    return _call('round_gain_crosses_floor', *args, **kwargs)

__all__ = ['bootstrap_mean_diff_ci', 'cohens_d', 'mean', 'score_transcript', 'strip_scores', 'GAIN_FLOOR', 'METRIC_KIND', 'SAFETY_CAP', 'STOP_PATIENCE', 'evaluate_stop', 'evaluate_stop_lexical', 'round_gain_crosses_floor']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

