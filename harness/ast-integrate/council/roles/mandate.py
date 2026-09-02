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

__surface__ = 'council.roles.mandate'

RIGHTS = "RIGHTS"

def point_of_use_audit(*args, **kwargs):
    return _call('point_of_use_audit', *args, **kwargs)

MODULE_REL = "module-rel"

def empty_mandate(*args, **kwargs):
    return _call('empty_mandate', *args, **kwargs)

def seat(*args, **kwargs):
    return _call('seat', *args, **kwargs)

def rights_matrix(*args, **kwargs):
    return _call('rights_matrix', *args, **kwargs)

def mandate_granting(*args, **kwargs):
    return _call('mandate_granting', *args, **kwargs)

def speak(*args, **kwargs):
    return _call('speak', *args, **kwargs)

def use_tool(*args, **kwargs):
    return _call('use_tool', *args, **kwargs)

def cast_vote(*args, **kwargs):
    return _call('cast_vote', *args, **kwargs)

def load_source(*args, **kwargs):
    return _call('load_source', *args, **kwargs)

def strip_enforcement(*args, **kwargs):
    return _call('strip_enforcement', *args, **kwargs)

def enforcement_sites(*args, **kwargs):
    return _call('enforcement_sites', *args, **kwargs)

__all__ = ['RIGHTS', 'point_of_use_audit', 'MODULE_REL', 'empty_mandate', 'seat', 'rights_matrix', 'mandate_granting', 'speak', 'use_tool', 'cast_vote', 'load_source', 'strip_enforcement', 'enforcement_sites']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

