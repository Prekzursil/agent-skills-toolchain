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

__surface__ = 'workflow_foundry.anti_rebuild_guard'

ADOPT = "ADOPT"

BUILD = "BUILD"

KIND_ABSENT_COVERAGE = "KIND_ABSENT_COVERAGE"

def consult(*args, **kwargs):
    return _call('consult', *args, **kwargs)

KIND_INCOMPARABLE_BASELINE = "KIND_INCOMPARABLE_BASELINE"

KIND_INCUMBENT_AT_OR_ABOVE_BAR = "KIND_INCUMBENT_AT_OR_ABOVE_BAR"

KIND_INFERIOR_BASELINE = "KIND_INFERIOR_BASELINE"

class GuardError(Exception):
    pass

def assert_build_citation_structural(*args, **kwargs):
    return _call('assert_build_citation_structural', *args, **kwargs)

class Registry(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('Registry', **kwargs)
        self.args = args

def load_registry(*args, **kwargs):
    return _call('load_registry', *args, **kwargs)

__all__ = ['ADOPT', 'BUILD', 'KIND_ABSENT_COVERAGE', 'consult', 'KIND_INCOMPARABLE_BASELINE', 'KIND_INCUMBENT_AT_OR_ABOVE_BAR', 'KIND_INFERIOR_BASELINE', 'GuardError', 'assert_build_citation_structural', 'Registry', 'load_registry']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

