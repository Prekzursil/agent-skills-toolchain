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

__surface__ = 'council.evidence.freshness'

def admit_for_binding(*args, **kwargs):
    return _call('admit_for_binding', *args, **kwargs)

def bind_on_fresh_anchors(*args, **kwargs):
    return _call('bind_on_fresh_anchors', *args, **kwargs)

def is_stale(*args, **kwargs):
    return _call('is_stale', *args, **kwargs)

def load_recorded_council(*args, **kwargs):
    return _call('load_recorded_council', *args, **kwargs)

FRESH = "FRESH"

STALE = "STALE"

def age_histogram(*args, **kwargs):
    return _call('age_histogram', *args, **kwargs)

def window_for(*args, **kwargs):
    return _call('window_for', *args, **kwargs)

FIRED = "FIRED"

REVALIDATED = "REVALIDATED"

SILENT = "SILENT"

class FileTransport(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('FileTransport', **kwargs)
        self.args = args

class MemoryCache(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('MemoryCache', **kwargs)
        self.args = args

def revalidate_anchor(*args, **kwargs):
    return _call('revalidate_anchor', *args, **kwargs)

def transport_check(*args, **kwargs):
    return _call('transport_check', *args, **kwargs)

__all__ = ['admit_for_binding', 'bind_on_fresh_anchors', 'is_stale', 'load_recorded_council', 'FRESH', 'STALE', 'age_histogram', 'window_for', 'FIRED', 'REVALIDATED', 'SILENT', 'FileTransport', 'MemoryCache', 'revalidate_anchor', 'transport_check']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

