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

__surface__ = 'bench.tournament'

def mixed_tournament(*args, **kwargs):
    return _call('mixed_tournament', *args, **kwargs)

def null_identical_tournament(*args, **kwargs):
    return _call('null_identical_tournament', *args, **kwargs)

def null_iid_tournament(*args, **kwargs):
    return _call('null_iid_tournament', *args, **kwargs)

def evaluate_field(*args, **kwargs):
    return _call('evaluate_field', *args, **kwargs)

def transitive_scores(*args, **kwargs):
    return _call('transitive_scores', *args, **kwargs)

def write_case_corpus(*args, **kwargs):
    return _call('write_case_corpus', *args, **kwargs)

def ledger_row(*args, **kwargs):
    return _call('ledger_row', *args, **kwargs)

def planted_cycle_scores(*args, **kwargs):
    return _call('planted_cycle_scores', *args, **kwargs)

def schedule_unstable_scores(*args, **kwargs):
    return _call('schedule_unstable_scores', *args, **kwargs)

def select_format(*args, **kwargs):
    return _call('select_format', *args, **kwargs)

MIXED_SEED = 1

NULL_SEED = 1

PARTIAL_ORDER = "PARTIAL_ORDER"

TOTAL_ORDER = "TOTAL_ORDER"

def hides_nontransitivity(*args, **kwargs):
    return _call('hides_nontransitivity', *args, **kwargs)

def mutant_hide_cycle(*args, **kwargs):
    return _call('mutant_hide_cycle', *args, **kwargs)

def scores_from_fixture_doc(*args, **kwargs):
    return _call('scores_from_fixture_doc', *args, **kwargs)

ELIMINATION = "ELIMINATION"

INSUFFICIENT_BUDGET = "INSUFFICIENT_BUDGET"

ROUND_ROBIN = "ROUND_ROBIN"

SWISS = "SWISS"

class CaseScore(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('CaseScore', **kwargs)
        self.args = args

def mutant_pick_round_robin(*args, **kwargs):
    return _call('mutant_pick_round_robin', *args, **kwargs)

def silently_resolves_schedule(*args, **kwargs):
    return _call('silently_resolves_schedule', *args, **kwargs)

__all__ = ['mixed_tournament', 'null_identical_tournament', 'null_iid_tournament', 'evaluate_field', 'transitive_scores', 'write_case_corpus', 'ledger_row', 'planted_cycle_scores', 'schedule_unstable_scores', 'select_format', 'MIXED_SEED', 'NULL_SEED', 'PARTIAL_ORDER', 'TOTAL_ORDER', 'hides_nontransitivity', 'mutant_hide_cycle', 'scores_from_fixture_doc', 'ELIMINATION', 'INSUFFICIENT_BUDGET', 'ROUND_ROBIN', 'SWISS', 'CaseScore', 'mutant_pick_round_robin', 'silently_resolves_schedule']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

