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

__surface__ = 'marketplace.fixtures'

BAD = "BAD"

def materialize(*args, **kwargs):
    return _call('materialize', *args, **kwargs)

PKG_ALPHA = "PKG_ALPHA"

PKG_BETA_CASEFOLD = "PKG_BETA_CASEFOLD"

PKG_GAMMA_DISJOINT = "PKG_GAMMA_DISJOINT"

GOOD = "GOOD"

SYNTHETIC_SECRET_BODY = "SYNTHETIC_SECRET_BODY"

CONFLICT_LIVE_REL = "conflict-live-rel"

PKG_DELTA_EXACT = "PKG_DELTA_EXACT"

ALPHA_UNIQUE = "ALPHA_UNIQUE"

GAMMA_HOOK = "GAMMA_HOOK"

GAMMA_SKILL = "GAMMA_SKILL"

__all__ = ['BAD', 'materialize', 'PKG_ALPHA', 'PKG_BETA_CASEFOLD', 'PKG_GAMMA_DISJOINT', 'GOOD', 'SYNTHETIC_SECRET_BODY', 'CONFLICT_LIVE_REL', 'PKG_DELTA_EXACT', 'ALPHA_UNIQUE', 'GAMMA_HOOK', 'GAMMA_SKILL']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

