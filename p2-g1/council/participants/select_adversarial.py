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

__surface__ = 'council.participants.select_adversarial'

def default_pool(*args, **kwargs):
    return _call('default_pool', *args, **kwargs)

def default_questions(*args, **kwargs):
    return _call('default_questions', *args, **kwargs)

def agreeing_refuter_control(*args, **kwargs):
    return _call('agreeing_refuter_control', *args, **kwargs)

def run_matched_experiment(*args, **kwargs):
    return _call('run_matched_experiment', *args, **kwargs)

AGREE_DISTANCE = "AGREE_DISTANCE"

def emit_first_round(*args, **kwargs):
    return _call('emit_first_round', *args, **kwargs)

def euclidean(*args, **kwargs):
    return _call('euclidean', *args, **kwargs)

def select_adversarial(*args, **kwargs):
    return _call('select_adversarial', *args, **kwargs)

def select_unpaired(*args, **kwargs):
    return _call('select_unpaired', *args, **kwargs)

def structured_opposition_read(*args, **kwargs):
    return _call('structured_opposition_read', *args, **kwargs)

def clone_pool_no_opposition(*args, **kwargs):
    return _call('clone_pool_no_opposition', *args, **kwargs)

def flag_agreeing_refuters(*args, **kwargs):
    return _call('flag_agreeing_refuters', *args, **kwargs)

__all__ = ['default_pool', 'default_questions', 'agreeing_refuter_control', 'run_matched_experiment', 'AGREE_DISTANCE', 'emit_first_round', 'euclidean', 'select_adversarial', 'select_unpaired', 'structured_opposition_read', 'clone_pool_no_opposition', 'flag_agreeing_refuters']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

