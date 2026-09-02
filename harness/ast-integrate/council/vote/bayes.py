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

__surface__ = 'council.vote.bayes'

SIM_K_OBS = "SIM_K_OBS"

SIM_N_EXPERTS = "SIM_N_EXPERTS"

SIM_N_TRIALS = "SIM_N_TRIALS"

SIM_P_TRUE = "SIM_P_TRUE"

SIM_SEED = 1

def clone_both_states(*args, **kwargs):
    return _call('clone_both_states', *args, **kwargs)

def independent_panel(*args, **kwargs):
    return _call('independent_panel', *args, **kwargs)

def load_near_certain_spec(*args, **kwargs):
    return _call('load_near_certain_spec', *args, **kwargs)

def pool_with_and_without_discount(*args, **kwargs):
    return _call('pool_with_and_without_discount', *args, **kwargs)

def run_calibration_simulation(*args, **kwargs):
    return _call('run_calibration_simulation', *args, **kwargs)

class PerRunThresholdTuneError(Exception):
    pass

class UndeclaredIndependenceError(Exception):
    pass

def clone_panel(*args, **kwargs):
    return _call('clone_panel', *args, **kwargs)

def is_near_certain(*args, **kwargs):
    return _call('is_near_certain', *args, **kwargs)

def logit(*args, **kwargs):
    return _call('logit', *args, **kwargs)

def n_effective(*args, **kwargs):
    return _call('n_effective', *args, **kwargs)

def pool(*args, **kwargs):
    return _call('pool', *args, **kwargs)

def sigmoid(*args, **kwargs):
    return _call('sigmoid', *args, **kwargs)

__all__ = ['SIM_K_OBS', 'SIM_N_EXPERTS', 'SIM_N_TRIALS', 'SIM_P_TRUE', 'SIM_SEED', 'clone_both_states', 'independent_panel', 'load_near_certain_spec', 'pool_with_and_without_discount', 'run_calibration_simulation', 'PerRunThresholdTuneError', 'UndeclaredIndependenceError', 'clone_panel', 'is_near_certain', 'logit', 'n_effective', 'pool', 'sigmoid']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

