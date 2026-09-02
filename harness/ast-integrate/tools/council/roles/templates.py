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

__surface__ = 'tools.council.roles.templates'

def author_custom_role(*args, **kwargs):
    return _call('author_custom_role', *args, **kwargs)

def builtin_registry(*args, **kwargs):
    return _call('builtin_registry', *args, **kwargs)

SPEC_ANCHOR = "SPEC_ANCHOR"

def detect_template_drift(*args, **kwargs):
    return _call('detect_template_drift', *args, **kwargs)

def resolve_template(*args, **kwargs):
    return _call('resolve_template', *args, **kwargs)

def schema_conformance_pass(*args, **kwargs):
    return _call('schema_conformance_pass', *args, **kwargs)

NEVER_GRANTED_TOOL = "NEVER_GRANTED_TOOL"

NEVER_GRANTED_PERMISSION = "NEVER_GRANTED_PERMISSION"

NEVER_GRANTED_SOURCE = "NEVER_GRANTED_SOURCE"

class RoleMandate(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('RoleMandate', **kwargs)
        self.args = args

def rights_escalation_check(*args, **kwargs):
    return _call('rights_escalation_check', *args, **kwargs)

__all__ = ['author_custom_role', 'builtin_registry', 'SPEC_ANCHOR', 'detect_template_drift', 'resolve_template', 'schema_conformance_pass', 'NEVER_GRANTED_TOOL', 'NEVER_GRANTED_PERMISSION', 'NEVER_GRANTED_SOURCE', 'RoleMandate', 'rights_escalation_check']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

