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

__surface__ = 'council.protocol.crossexam'

def schedule_cross_examination(*args, **kwargs):
    return _call('schedule_cross_examination', *args, **kwargs)

class Position(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('Position', **kwargs)
        self.args = args

DEPTH_BOUND = "DEPTH_BOUND"

class Pairing(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('Pairing', **kwargs)
        self.args = args

SELF_EXAM = "SELF_EXAM"

def audit_record(*args, **kwargs):
    return _call('audit_record', *args, **kwargs)

def examination_quota(*args, **kwargs):
    return _call('examination_quota', *args, **kwargs)

def pairing_is_valid_exam(*args, **kwargs):
    return _call('pairing_is_valid_exam', *args, **kwargs)

def propose_followup(*args, **kwargs):
    return _call('propose_followup', *args, **kwargs)

def coverage_gaps(*args, **kwargs):
    return _call('coverage_gaps', *args, **kwargs)

def coverage_matrix(*args, **kwargs):
    return _call('coverage_matrix', *args, **kwargs)

def drop_position_pairings(*args, **kwargs):
    return _call('drop_position_pairings', *args, **kwargs)

def popularity_examination_correlation(*args, **kwargs):
    return _call('popularity_examination_correlation', *args, **kwargs)

def weak_only_schedule(*args, **kwargs):
    return _call('weak_only_schedule', *args, **kwargs)

__all__ = ['schedule_cross_examination', 'Position', 'DEPTH_BOUND', 'Pairing', 'SELF_EXAM', 'audit_record', 'examination_quota', 'pairing_is_valid_exam', 'propose_followup', 'coverage_gaps', 'coverage_matrix', 'drop_position_pairings', 'popularity_examination_correlation', 'weak_only_schedule']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

