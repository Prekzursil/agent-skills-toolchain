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

__surface__ = 'marketplace.install'

def install(*args, **kwargs):
    return _call('install', *args, **kwargs)

HANDLING_REFUSED_IMPLICIT = "HANDLING_REFUSED_IMPLICIT"

HANDLING_NAIVE_HOST = "HANDLING_NAIVE_HOST"

HANDLING_SANDBOX_GATED = "HANDLING_SANDBOX_GATED"

def marketplace_install(*args, **kwargs):
    return _call('marketplace_install', *args, **kwargs)

def measure_postinstall_policy(*args, **kwargs):
    return _call('measure_postinstall_policy', *args, **kwargs)

class InstallRefused(Exception):
    pass

class Ledger(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('Ledger', **kwargs)
        self.args = args

def census(*args, **kwargs):
    return _call('census', *args, **kwargs)

HANDLING_GATE_NO_SANDBOX = "HANDLING_GATE_NO_SANDBOX"

SCRIPT_FIELD = "SCRIPT_FIELD"

OWNER_GATE_TOKEN = "OWNER_GATE_TOKEN"

class OwnerGate(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('OwnerGate', **kwargs)
        self.args = args

def install_package(*args, **kwargs):
    return _call('install_package', *args, **kwargs)

CANARY_TOKEN = "CANARY_TOKEN"

SCHEMA_REL = "schema-rel"

def dump_policy(*args, **kwargs):
    return _call('dump_policy', *args, **kwargs)

__all__ = ['install', 'HANDLING_REFUSED_IMPLICIT', 'HANDLING_NAIVE_HOST', 'HANDLING_SANDBOX_GATED', 'marketplace_install', 'measure_postinstall_policy', 'InstallRefused', 'Ledger', 'census', 'HANDLING_GATE_NO_SANDBOX', 'SCRIPT_FIELD', 'OWNER_GATE_TOKEN', 'OwnerGate', 'install_package', 'CANARY_TOKEN', 'SCHEMA_REL', 'dump_policy']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

