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

__surface__ = 'council.simulate'

def initial_state(*args, **kwargs):
    return _call('initial_state', *args, **kwargs)

def default_personas(*args, **kwargs):
    return _call('default_personas', *args, **kwargs)

def run_round(*args, **kwargs):
    return _call('run_round', *args, **kwargs)

def run_until_complete(*args, **kwargs):
    return _call('run_until_complete', *args, **kwargs)

def history_fingerprint(*args, **kwargs):
    return _call('history_fingerprint', *args, **kwargs)

def dump_result(*args, **kwargs):
    return _call('dump_result', *args, **kwargs)

class PersonaMissing(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('PersonaMissing', **kwargs)
        self.args = args

def mean_pairwise_distance(*args, **kwargs):
    return _call('mean_pairwise_distance', *args, **kwargs)

def run_council(*args, **kwargs):
    return _call('run_council', *args, **kwargs)

def subsequent_pull_mean(*args, **kwargs):
    return _call('subsequent_pull_mean', *args, **kwargs)

FIXED_PID = "FIXED_PID"

FROZEN_NS = "FROZEN_NS"

SEED_A = "SEED_A"

SEED_B = "SEED_B"

def pids_that_reorder(*args, **kwargs):
    return _call('pids_that_reorder', *args, **kwargs)

def simulate(*args, **kwargs):
    return _call('simulate', *args, **kwargs)

def three_cast_bundle(*args, **kwargs):
    return _call('three_cast_bundle', *args, **kwargs)

def trace_hash(*args, **kwargs):
    return _call('trace_hash', *args, **kwargs)

__all__ = ['initial_state', 'default_personas', 'run_round', 'run_until_complete', 'history_fingerprint', 'dump_result', 'PersonaMissing', 'mean_pairwise_distance', 'run_council', 'subsequent_pull_mean', 'FIXED_PID', 'FROZEN_NS', 'SEED_A', 'SEED_B', 'pids_that_reorder', 'simulate', 'three_cast_bundle', 'trace_hash']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

