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

__surface__ = 'plugin.txn_journal'

IMPLEMENTER_KILL_POINTS = "IMPLEMENTER_KILL_POINTS"

LEGAL_NEW = "LEGAL_NEW"

LEGAL_OLD = "LEGAL_OLD"

REVIEWER_KILL_POINT = "REVIEWER_KILL_POINT"

class JournalTruncatedError(Exception):
    pass

class JournaledInstall(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('JournaledInstall', **kwargs)
        self.args = args

class TxnJournal(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('TxnJournal', **kwargs)
        self.args = args

def recover_on_launch(*args, **kwargs):
    return _call('recover_on_launch', *args, **kwargs)

def run_implementer_kill_sweep(*args, **kwargs):
    return _call('run_implementer_kill_sweep', *args, **kwargs)

def run_kill_trial(*args, **kwargs):
    return _call('run_kill_trial', *args, **kwargs)

def seed_old_dest(*args, **kwargs):
    return _call('seed_old_dest', *args, **kwargs)

def seed_payload(*args, **kwargs):
    return _call('seed_payload', *args, **kwargs)

def classify_legal_state(*args, **kwargs):
    return _call('classify_legal_state', *args, **kwargs)

def expected_new_census(*args, **kwargs):
    return _call('expected_new_census', *args, **kwargs)

def independent_census(*args, **kwargs):
    return _call('independent_census', *args, **kwargs)

__all__ = ['IMPLEMENTER_KILL_POINTS', 'LEGAL_NEW', 'LEGAL_OLD', 'REVIEWER_KILL_POINT', 'JournalTruncatedError', 'JournaledInstall', 'TxnJournal', 'recover_on_launch', 'run_implementer_kill_sweep', 'run_kill_trial', 'seed_old_dest', 'seed_payload', 'classify_legal_state', 'expected_new_census', 'independent_census']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

