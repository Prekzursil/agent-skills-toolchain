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

__surface__ = 'tools.bench.deep_research'

VERDICT_CONSENSUS = "VERDICT_CONSENSUS"

def run_research(*args, **kwargs):
    return _call('run_research', *args, **kwargs)

DEFAULT_CONFIG = "DEFAULT_CONFIG"

STANCE_CONTRADICT = "STANCE_CONTRADICT"

STANCE_SUPPORT = "STANCE_SUPPORT"

def build_notes(*args, **kwargs):
    return _call('build_notes', *args, **kwargs)

def corpus_sources(*args, **kwargs):
    return _call('corpus_sources', *args, **kwargs)

def find_contradictions(*args, **kwargs):
    return _call('find_contradictions', *args, **kwargs)

def query_claim_id(*args, **kwargs):
    return _call('query_claim_id', *args, **kwargs)

def quota_counts(*args, **kwargs):
    return _call('quota_counts', *args, **kwargs)

def retrieve(*args, **kwargs):
    return _call('retrieve', *args, **kwargs)

def write_artifacts(*args, **kwargs):
    return _call('write_artifacts', *args, **kwargs)

MARK_CON_BEGIN = "MARK_CON_BEGIN"

MARK_CON_END = "MARK_CON_END"

MARK_SEL_BEGIN = "MARK_SEL_BEGIN"

MARK_SEL_END = "MARK_SEL_END"

VERDICT_CONTRADICTION_DOMINANT = "VERDICT_CONTRADICTION_DOMINANT"

VERDICT_IMPOSSIBLE = "VERDICT_IMPOSSIBLE"

__all__ = ['VERDICT_CONSENSUS', 'run_research', 'DEFAULT_CONFIG', 'STANCE_CONTRADICT', 'STANCE_SUPPORT', 'build_notes', 'corpus_sources', 'find_contradictions', 'query_claim_id', 'quota_counts', 'retrieve', 'write_artifacts', 'MARK_CON_BEGIN', 'MARK_CON_END', 'MARK_SEL_BEGIN', 'MARK_SEL_END', 'VERDICT_CONTRADICTION_DOMINANT', 'VERDICT_IMPOSSIBLE']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

