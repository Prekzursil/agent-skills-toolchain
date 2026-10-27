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

__surface__ = 'workflow_foundry.component_graph'

class OrphanComponentError(Exception):
    pass

def assemble(*args, **kwargs):
    return _call('assemble', *args, **kwargs)

def assert_no_orphans(*args, **kwargs):
    return _call('assert_no_orphans', *args, **kwargs)

def build(*args, **kwargs):
    return _call('build', *args, **kwargs)

def graph_public(*args, **kwargs):
    return _call('graph_public', *args, **kwargs)

def is_orphan(*args, **kwargs):
    return _call('is_orphan', *args, **kwargs)

def orphan_count(*args, **kwargs):
    return _call('orphan_count', *args, **kwargs)

def plant_orphan(*args, **kwargs):
    return _call('plant_orphan', *args, **kwargs)

def span_is_resolvable(*args, **kwargs):
    return _call('span_is_resolvable', *args, **kwargs)

def valid_provenance(*args, **kwargs):
    return _call('valid_provenance', *args, **kwargs)

def with_lookalike_named_orphan(*args, **kwargs):
    return _call('with_lookalike_named_orphan', *args, **kwargs)

def with_unanchored_stage(*args, **kwargs):
    return _call('with_unanchored_stage', *args, **kwargs)

__all__ = ['OrphanComponentError', 'assemble', 'assert_no_orphans', 'build', 'graph_public', 'is_orphan', 'orphan_count', 'plant_orphan', 'span_is_resolvable', 'valid_provenance', 'with_lookalike_named_orphan', 'with_unanchored_stage']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

