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

__surface__ = 'council.evidence.standard'

CLASSIFIER_INPUT_FIELD = "CLASSIFIER_INPUT_FIELD"

def bind_decision(*args, **kwargs):
    return _call('bind_decision', *args, **kwargs)

def load_labelled_claims(*args, **kwargs):
    return _call('load_labelled_claims', *args, **kwargs)

def preset_for(*args, **kwargs):
    return _call('preset_for', *args, **kwargs)

DECLARED_FLOORS = "DECLARED_FLOORS"

class UnderTierError(Exception):
    pass

def attach_claim(*args, **kwargs):
    return _call('attach_claim', *args, **kwargs)

def classification_pass(*args, **kwargs):
    return _call('classification_pass', *args, **kwargs)

def expected_admitted_ids(*args, **kwargs):
    return _call('expected_admitted_ids', *args, **kwargs)

def admit_claim(*args, **kwargs):
    return _call('admit_claim', *args, **kwargs)

def classify_by_claimant_assertion(*args, **kwargs):
    return _call('classify_by_claimant_assertion', *args, **kwargs)

def classify_source_type(*args, **kwargs):
    return _call('classify_source_type', *args, **kwargs)

def misclassification_report(*args, **kwargs):
    return _call('misclassification_report', *args, **kwargs)

__all__ = ['CLASSIFIER_INPUT_FIELD', 'bind_decision', 'load_labelled_claims', 'preset_for', 'DECLARED_FLOORS', 'UnderTierError', 'attach_claim', 'classification_pass', 'expected_admitted_ids', 'admit_claim', 'classify_by_claimant_assertion', 'classify_source_type', 'misclassification_report']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

