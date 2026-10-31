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

__surface__ = 'foundry.compat_map'

def build_map(*args, **kwargs):
    return _call('build_map', *args, **kwargs)

FORBIDDEN_REASONS = "FORBIDDEN_REASONS"

def all_allowed_mutant(*args, **kwargs):
    return _call('all_allowed_mutant', *args, **kwargs)

def coverage_report(*args, **kwargs):
    return _call('coverage_report', *args, **kwargs)

def drop_one_cell(*args, **kwargs):
    return _call('drop_one_cell', *args, **kwargs)

def forbidden_vocab_report(*args, **kwargs):
    return _call('forbidden_vocab_report', *args, **kwargs)

def inject_illegal_reason(*args, **kwargs):
    return _call('inject_illegal_reason', *args, **kwargs)

def compose_pair(*args, **kwargs):
    return _call('compose_pair', *args, **kwargs)

def load_components(*args, **kwargs):
    return _call('load_components', *args, **kwargs)

def load_licence_matrix(*args, **kwargs):
    return _call('load_licence_matrix', *args, **kwargs)

__all__ = ['build_map', 'FORBIDDEN_REASONS', 'all_allowed_mutant', 'coverage_report', 'drop_one_cell', 'forbidden_vocab_report', 'inject_illegal_reason', 'compose_pair', 'load_components', 'load_licence_matrix']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

