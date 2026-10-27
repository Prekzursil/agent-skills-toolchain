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

__surface__ = 'marketplace.manifest_reader'

def canonical_live_document(*args, **kwargs):
    return _call('canonical_live_document', *args, **kwargs)

def check_manifest(*args, **kwargs):
    return _call('check_manifest', *args, **kwargs)

def dump_bytes(*args, **kwargs):
    return _call('dump_bytes', *args, **kwargs)

def ensure_live_subject(*args, **kwargs):
    return _call('ensure_live_subject', *args, **kwargs)

def live_path(*args, **kwargs):
    return _call('live_path', *args, **kwargs)

def load_manifest(*args, **kwargs):
    return _call('load_manifest', *args, **kwargs)

def canonical_plugin_document(*args, **kwargs):
    return _call('canonical_plugin_document', *args, **kwargs)

CONTRACT_RULES = "CONTRACT_RULES"

LIVE_REL = "live-rel"

SCHEMA_REL = "schema-rel"

def report_to_dict(*args, **kwargs):
    return _call('report_to_dict', *args, **kwargs)

RULE_ROUND_TRIP = "RULE_ROUND_TRIP"

RULE_SOURCE_RESOLVABLE = "RULE_SOURCE_RESOLVABLE"

__all__ = ['canonical_live_document', 'check_manifest', 'dump_bytes', 'ensure_live_subject', 'live_path', 'load_manifest', 'canonical_plugin_document', 'CONTRACT_RULES', 'LIVE_REL', 'SCHEMA_REL', 'report_to_dict', 'RULE_ROUND_TRIP', 'RULE_SOURCE_RESOLVABLE']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

