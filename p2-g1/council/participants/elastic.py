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

__surface__ = 'council.participants.elastic'

def recruit(*args, **kwargs):
    return _call('recruit', *args, **kwargs)

class ElasticError(Exception):
    pass

def scale_decision(*args, **kwargs):
    return _call('scale_decision', *args, **kwargs)

REASON_FORBIDDEN_KEY = "REASON_FORBIDDEN_KEY"

REASON_OUTPUT_ECHO = "REASON_OUTPUT_ECHO"

def context_diff(*args, **kwargs):
    return _call('context_diff', *args, **kwargs)

def draft_first_position(*args, **kwargs):
    return _call('draft_first_position', *args, **kwargs)

def feed_consensus_transcript(*args, **kwargs):
    return _call('feed_consensus_transcript', *args, **kwargs)

def first_original_context(*args, **kwargs):
    return _call('first_original_context', *args, **kwargs)

def independence_check(*args, **kwargs):
    return _call('independence_check', *args, **kwargs)

__all__ = ['recruit', 'ElasticError', 'scale_decision', 'REASON_FORBIDDEN_KEY', 'REASON_OUTPUT_ECHO', 'context_diff', 'draft_first_position', 'feed_consensus_transcript', 'first_original_context', 'independence_check']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

