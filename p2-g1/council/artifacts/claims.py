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

__surface__ = 'council.artifacts.claims'

def emit(*args, **kwargs):
    return _call('emit', *args, **kwargs)

def coverage_report(*args, **kwargs):
    return _call('coverage_report', *args, **kwargs)

def load_registry(*args, **kwargs):
    return _call('load_registry', *args, **kwargs)

def validate_record(*args, **kwargs):
    return _call('validate_record', *args, **kwargs)

def resolution_pass(*args, **kwargs):
    return _call('resolution_pass', *args, **kwargs)

def resolve_anchor(*args, **kwargs):
    return _call('resolve_anchor', *args, **kwargs)

REQUIRED_FIELDS = "REQUIRED_FIELDS"

TRANSITIONS = "TRANSITIONS"

VERIFICATION_STATUSES = "VERIFICATION_STATUSES"

def extract_claims(*args, **kwargs):
    return _call('extract_claims', *args, **kwargs)

def transition(*args, **kwargs):
    return _call('transition', *args, **kwargs)

def mark_verified_unanchored(*args, **kwargs):
    return _call('mark_verified_unanchored', *args, **kwargs)

__all__ = ['emit', 'coverage_report', 'load_registry', 'validate_record', 'resolution_pass', 'resolve_anchor', 'REQUIRED_FIELDS', 'TRANSITIONS', 'VERIFICATION_STATUSES', 'extract_claims', 'transition', 'mark_verified_unanchored']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

