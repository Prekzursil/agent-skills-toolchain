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

__surface__ = 'council.topology.redblue'

def scan_cross_team_tokens(*args, **kwargs):
    return _call('scan_cross_team_tokens', *args, **kwargs)

class RecordingKernel(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('RecordingKernel', **kwargs)
        self.args = args

def default_fixture_assignment(*args, **kwargs):
    return _call('default_fixture_assignment', *args, **kwargs)

def default_fixture_moves(*args, **kwargs):
    return _call('default_fixture_moves', *args, **kwargs)

def mint_token(*args, **kwargs):
    return _call('mint_token', *args, **kwargs)

def run_clean_fixture(*args, **kwargs):
    return _call('run_clean_fixture', *args, **kwargs)

def score_exchange(*args, **kwargs):
    return _call('score_exchange', *args, **kwargs)

def deliberate_leak_fixture(*args, **kwargs):
    return _call('deliberate_leak_fixture', *args, **kwargs)

def known_shared_fixture(*args, **kwargs):
    return _call('known_shared_fixture', *args, **kwargs)

def token_owner(*args, **kwargs):
    return _call('token_owner', *args, **kwargs)

__all__ = ['scan_cross_team_tokens', 'RecordingKernel', 'default_fixture_assignment', 'default_fixture_moves', 'mint_token', 'run_clean_fixture', 'score_exchange', 'deliberate_leak_fixture', 'known_shared_fixture', 'token_owner']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

