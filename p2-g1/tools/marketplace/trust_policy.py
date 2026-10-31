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

__surface__ = 'marketplace.trust_policy'

def default_policy_document(*args, **kwargs):
    return _call('default_policy_document', *args, **kwargs)

SCHEMA_REL = "schema-rel"

def cartesian(*args, **kwargs):
    return _call('cartesian', *args, **kwargs)

def completeness(*args, **kwargs):
    return _call('completeness', *args, **kwargs)

def default_verdict(*args, **kwargs):
    return _call('default_verdict', *args, **kwargs)

def decide(*args, **kwargs):
    return _call('decide', *args, **kwargs)

def drop_cell(*args, **kwargs):
    return _call('drop_cell', *args, **kwargs)

def exercise_matrix(*args, **kwargs):
    return _call('exercise_matrix', *args, **kwargs)

def fixture_attestation(*args, **kwargs):
    return _call('fixture_attestation', *args, **kwargs)

def repo_default_path(*args, **kwargs):
    return _call('repo_default_path', *args, **kwargs)

def validate_schema(*args, **kwargs):
    return _call('validate_schema', *args, **kwargs)

def write_default_policy(*args, **kwargs):
    return _call('write_default_policy', *args, **kwargs)

def load_policy(*args, **kwargs):
    return _call('load_policy', *args, **kwargs)

class ActivationError(Exception):
    pass

def require_owner_signoff(*args, **kwargs):
    return _call('require_owner_signoff', *args, **kwargs)

__all__ = ['default_policy_document', 'SCHEMA_REL', 'cartesian', 'completeness', 'default_verdict', 'decide', 'drop_cell', 'exercise_matrix', 'fixture_attestation', 'repo_default_path', 'validate_schema', 'write_default_policy', 'load_policy', 'ActivationError', 'require_owner_signoff']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

