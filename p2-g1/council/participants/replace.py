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

__surface__ = 'council.participants.replace'

def evict(*args, **kwargs):
    return _call('evict', *args, **kwargs)

def make_run(*args, **kwargs):
    return _call('make_run', *args, **kwargs)

def ballot_count(*args, **kwargs):
    return _call('ballot_count', *args, **kwargs)

def replace_occupant(*args, **kwargs):
    return _call('replace_occupant', *args, **kwargs)

def compute_quorum(*args, **kwargs):
    return _call('compute_quorum', *args, **kwargs)

def evaluate_triggers(*args, **kwargs):
    return _call('evaluate_triggers', *args, **kwargs)

def find_eviction_candidates(*args, **kwargs):
    return _call('find_eviction_candidates', *args, **kwargs)

def record_failure(*args, **kwargs):
    return _call('record_failure', *args, **kwargs)

RULE_ID = "RULE_ID"

def census_retention_check(*args, **kwargs):
    return _call('census_retention_check', *args, **kwargs)

def compute_tally(*args, **kwargs):
    return _call('compute_tally', *args, **kwargs)

def contribution_census(*args, **kwargs):
    return _call('contribution_census', *args, **kwargs)

def vote_ledger(*args, **kwargs):
    return _call('vote_ledger', *args, **kwargs)

__all__ = ['evict', 'make_run', 'ballot_count', 'replace_occupant', 'compute_quorum', 'evaluate_triggers', 'find_eviction_candidates', 'record_failure', 'RULE_ID', 'census_retention_check', 'compute_tally', 'contribution_census', 'vote_ledger']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

