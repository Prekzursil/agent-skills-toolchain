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

__surface__ = 'marketplace.evidence_lint'

RULE_RUN_UNRESOLVED = "RULE_RUN_UNRESOLVED"

class ResultsLedger(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('ResultsLedger', **kwargs)
        self.args = args

RULE_STALE_B09 = "RULE_STALE_B09"

RULE_THIRD_PARTY = "RULE_THIRD_PARTY"

def evidence_schema_is_closed(*args, **kwargs):
    return _call('evidence_schema_is_closed', *args, **kwargs)

def inspect_schema_holes(*args, **kwargs):
    return _call('inspect_schema_holes', *args, **kwargs)

def lint_path(*args, **kwargs):
    return _call('lint_path', *args, **kwargs)

def planted_holey_schema_holes(*args, **kwargs):
    return _call('planted_holey_schema_holes', *args, **kwargs)

DECISION_ACCEPTED = "DECISION_ACCEPTED"

DECISION_REJECTED = "DECISION_REJECTED"

HOLEY_EVIDENCE_SCHEMA = "HOLEY_EVIDENCE_SCHEMA"

RULE_NOT_A_REFERENCE = "RULE_NOT_A_REFERENCE"

def lint_listing(*args, **kwargs):
    return _call('lint_listing', *args, **kwargs)

def load_json(*args, **kwargs):
    return _call('load_json', *args, **kwargs)

DECISION_STALE = "DECISION_STALE"

DECISION_UNVERIFIED = "DECISION_UNVERIFIED"

RULE_HARNESS_UNSUPPORTED = "RULE_HARNESS_UNSUPPORTED"

__all__ = ['RULE_RUN_UNRESOLVED', 'ResultsLedger', 'RULE_STALE_B09', 'RULE_THIRD_PARTY', 'evidence_schema_is_closed', 'inspect_schema_holes', 'lint_path', 'planted_holey_schema_holes', 'DECISION_ACCEPTED', 'DECISION_REJECTED', 'HOLEY_EVIDENCE_SCHEMA', 'RULE_NOT_A_REFERENCE', 'lint_listing', 'load_json', 'DECISION_STALE', 'DECISION_UNVERIFIED', 'RULE_HARNESS_UNSUPPORTED']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

