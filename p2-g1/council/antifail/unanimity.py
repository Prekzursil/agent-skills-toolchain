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

__surface__ = 'council.antifail.unanimity'

@dataclass
class Vote:
    participant_id: str
    claim_id: str
    round: int = 1
    confidence: float = 1.0

def plurality(votes=None, *args, **kwargs):
    from collections import Counter
    rows = list(votes or [])
    counts = Counter(
        getattr(v, "claim_id", None) or (v.get("claim_id") if isinstance(v, dict) else None)
        for v in rows
    )
    counts.pop(None, None)
    if not counts:
        return None
    ranked = counts.most_common()
    if len(ranked) >= 2 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]

REMEDIATION_ORDER = "REMEDIATION_ORDER"

def evaluate(*args, **kwargs):
    return _call('evaluate', *args, **kwargs)

def outcome_change_rate(*args, **kwargs):
    return _call('outcome_change_rate', *args, **kwargs)

class Brief(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('Brief', **kwargs)
        self.args = args

class Participant(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('Participant', **kwargs)
        self.args = args

__all__ = ['Vote', 'plurality', 'REMEDIATION_ORDER', 'evaluate', 'outcome_change_rate', 'Brief', 'Participant']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

