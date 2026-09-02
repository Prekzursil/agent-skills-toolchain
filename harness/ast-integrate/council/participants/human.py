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

__surface__ = 'council.participants.human'

APPROVE = "APPROVE"

POLICY_EXCLUDE_ABSTENTION = "POLICY_EXCLUDE_ABSTENTION"

REJECT = "REJECT"

ORIGIN_AGENT = "ORIGIN_AGENT"

def tally_records(*args, **kwargs):
    return _call('tally_records', *args, **kwargs)

ABSTAIN = "ABSTAIN"

KIND_AGENT = "KIND_AGENT"

KIND_HUMAN = "KIND_HUMAN"

PROXY_ORIGIN_MARKER = "PROXY_ORIGIN_MARKER"

class DeterministicClock(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('DeterministicClock', **kwargs)
        self.args = args

class HybridCouncil(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('HybridCouncil', **kwargs)
        self.args = args

class HumanOnlyViolation(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('HumanOnlyViolation', **kwargs)
        self.args = args

class Seat(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('Seat', **kwargs)
        self.args = args

class WindowError(Exception):
    pass

def classify_kind(*args, **kwargs):
    return _call('classify_kind', *args, **kwargs)

def scan_proxy_markers(*args, **kwargs):
    return _call('scan_proxy_markers', *args, **kwargs)

def strip_proxy_markers(*args, **kwargs):
    return _call('strip_proxy_markers', *args, **kwargs)

__all__ = ['APPROVE', 'POLICY_EXCLUDE_ABSTENTION', 'REJECT', 'ORIGIN_AGENT', 'tally_records', 'ABSTAIN', 'KIND_AGENT', 'KIND_HUMAN', 'PROXY_ORIGIN_MARKER', 'DeterministicClock', 'HybridCouncil', 'HumanOnlyViolation', 'Seat', 'WindowError', 'classify_kind', 'scan_proxy_markers', 'strip_proxy_markers']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

