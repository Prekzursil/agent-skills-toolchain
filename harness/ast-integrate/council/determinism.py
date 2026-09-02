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

__surface__ = 'council.determinism'

def record_council(*args, **kwargs):
    return _call('record_council', *args, **kwargs)

NOT_PINNABLE = "NOT_PINNABLE"

PINNED = "PINNED"

ESTATE_LIVE_HTTP_RESIDUAL = "ESTATE_LIVE_HTTP_RESIDUAL"

def default_council(*args, **kwargs):
    return _call('default_council', *args, **kwargs)

def estate_vendors(*args, **kwargs):
    return _call('estate_vendors', *args, **kwargs)

def identical_output_rate(*args, **kwargs):
    return _call('identical_output_rate', *args, **kwargs)

class SamplingParams(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('SamplingParams', **kwargs)
        self.args = args

class SeatSpec(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('SeatSpec', **kwargs)
        self.args = args

class SeedHonouringVendor(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('SeedHonouringVendor', **kwargs)
        self.args = args

class SeedIgnoringVendor(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('SeedIgnoringVendor', **kwargs)
        self.args = args

def classify(*args, **kwargs):
    return _call('classify', *args, **kwargs)

def liar_classify_if_seed_exposed(*args, **kwargs):
    return _call('liar_classify_if_seed_exposed', *args, **kwargs)

def record_seat(*args, **kwargs):
    return _call('record_seat', *args, **kwargs)

__all__ = ['record_council', 'NOT_PINNABLE', 'PINNED', 'ESTATE_LIVE_HTTP_RESIDUAL', 'default_council', 'estate_vendors', 'identical_output_rate', 'SamplingParams', 'SeatSpec', 'SeedHonouringVendor', 'SeedIgnoringVendor', 'classify', 'liar_classify_if_seed_exposed', 'record_seat']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

