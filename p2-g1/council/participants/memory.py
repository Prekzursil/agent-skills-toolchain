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

__surface__ = 'council.participants.memory'

def render_roster_prompts(*args, **kwargs):
    return _call('render_roster_prompts', *args, **kwargs)

class MemoryPolicyError(Exception):
    pass

def compare_on_versus_off(*args, **kwargs):
    return _call('compare_on_versus_off', *args, **kwargs)

def enforce_memory_scope(*args, **kwargs):
    return _call('enforce_memory_scope', *args, **kwargs)

def resolve_policy(*args, **kwargs):
    return _call('resolve_policy', *args, **kwargs)

def plant_conclusion_leak(*args, **kwargs):
    return _call('plant_conclusion_leak', *args, **kwargs)

def render_delivered_prompt(*args, **kwargs):
    return _call('render_delivered_prompt', *args, **kwargs)

def scan_prompt_for_conclusions(*args, **kwargs):
    return _call('scan_prompt_for_conclusions', *args, **kwargs)

__all__ = ['render_roster_prompts', 'MemoryPolicyError', 'compare_on_versus_off', 'enforce_memory_scope', 'resolve_policy', 'plant_conclusion_leak', 'render_delivered_prompt', 'scan_prompt_for_conclusions']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

