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

__surface__ = 'council.protocol.socratic'

STATE_OPEN = "STATE_OPEN"

class SocraticProtocol(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('SocraticProtocol', **kwargs)
        self.args = args

STATE_DISCHARGED = "STATE_DISCHARGED"

STATE_ESCALATED = "STATE_ESCALATED"

STATE_EXPIRED = "STATE_EXPIRED"

def ledger_digest(*args, **kwargs):
    return _call('ledger_digest', *args, **kwargs)

LABEL_ANSWER = "LABEL_ANSWER"

def classify_reply(*args, **kwargs):
    return _call('classify_reply', *args, **kwargs)

def load_corpus(*args, **kwargs):
    return _call('load_corpus', *args, **kwargs)

def naive_any_bytes_discharge(*args, **kwargs):
    return _call('naive_any_bytes_discharge', *args, **kwargs)

def score_corpus(*args, **kwargs):
    return _call('score_corpus', *args, **kwargs)

__all__ = ['STATE_OPEN', 'SocraticProtocol', 'STATE_DISCHARGED', 'STATE_ESCALATED', 'STATE_EXPIRED', 'ledger_digest', 'LABEL_ANSWER', 'classify_reply', 'load_corpus', 'naive_any_bytes_discharge', 'score_corpus']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

