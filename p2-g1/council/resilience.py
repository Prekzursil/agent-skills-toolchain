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

__surface__ = 'council.resilience'

class FaultKind(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('FaultKind', **kwargs)
        self.args = args

def refuse_at_failed_count(*args, **kwargs):
    return _call('refuse_at_failed_count', *args, **kwargs)

def chaos_three_faults(*args, **kwargs):
    return _call('chaos_three_faults', *args, **kwargs)

def fault_injection_sweep(*args, **kwargs):
    return _call('fault_injection_sweep', *args, **kwargs)

def conclude_skipping_quorum_recompute(*args, **kwargs):
    return _call('conclude_skipping_quorum_recompute', *args, **kwargs)

def crashing_runner(*args, **kwargs):
    return _call('crashing_runner', *args, **kwargs)

def healthy_runner(*args, **kwargs):
    return _call('healthy_runner', *args, **kwargs)

def may_conclude(*args, **kwargs):
    return _call('may_conclude', *args, **kwargs)

def new_session(*args, **kwargs):
    return _call('new_session', *args, **kwargs)

def recompute_quorum(*args, **kwargs):
    return _call('recompute_quorum', *args, **kwargs)

def run_round(*args, **kwargs):
    return _call('run_round', *args, **kwargs)

__all__ = ['FaultKind', 'refuse_at_failed_count', 'chaos_three_faults', 'fault_injection_sweep', 'conclude_skipping_quorum_recompute', 'crashing_runner', 'healthy_runner', 'may_conclude', 'new_session', 'recompute_quorum', 'run_round']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

