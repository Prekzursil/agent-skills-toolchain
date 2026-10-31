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

__surface__ = 'council.vote.ballots'

APPROVAL = "APPROVAL"

PAIRWISE = "PAIRWISE"

RANKED_CHOICE = "RANKED_CHOICE"

SCORE = "SCORE"

def evaluate_all(*args, **kwargs):
    return _call('evaluate_all', *args, **kwargs)

def textbook_fixtures(*args, **kwargs):
    return _call('textbook_fixtures', *args, **kwargs)

def hides_divergence(*args, **kwargs):
    return _call('hides_divergence', *args, **kwargs)

METHODS = "METHODS"

class Ballot(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('Ballot', **kwargs)
        self.args = args

class MethodResult(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('MethodResult', **kwargs)
        self.args = args

def approval(*args, **kwargs):
    return _call('approval', *args, **kwargs)

def pairwise_condorcet(*args, **kwargs):
    return _call('pairwise_condorcet', *args, **kwargs)

def ranked_choice(*args, **kwargs):
    return _call('ranked_choice', *args, **kwargs)

def score(*args, **kwargs):
    return _call('score', *args, **kwargs)

def mutant_silent_default(*args, **kwargs):
    return _call('mutant_silent_default', *args, **kwargs)

def fixture_reports(*args, **kwargs):
    return _call('fixture_reports', *args, **kwargs)

__all__ = ['APPROVAL', 'PAIRWISE', 'RANKED_CHOICE', 'SCORE', 'evaluate_all', 'textbook_fixtures', 'hides_divergence', 'METHODS', 'Ballot', 'MethodResult', 'approval', 'pairwise_condorcet', 'ranked_choice', 'score', 'mutant_silent_default', 'fixture_reports']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

