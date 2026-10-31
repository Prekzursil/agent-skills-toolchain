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

__surface__ = 'marketplace.vuln_ingestion'

KNOWN_CONTROL_CVE = "KNOWN_CONTROL_CVE"

class OsvHttpSource(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('OsvHttpSource', **kwargs)
        self.args = args

class SbomStore(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('SbomStore', **kwargs)
        self.args = args

def ids_contain(*args, **kwargs):
    return _call('ids_contain', *args, **kwargs)

def ingest_components(*args, **kwargs):
    return _call('ingest_components', *args, **kwargs)

CLEAN_CONTROL_NAME = "CLEAN_CONTROL_NAME"

class GithubAdvisorySource(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('GithubAdvisorySource', **kwargs)
        self.args = args

def interpret_osv_scanner_exit(*args, **kwargs):
    return _call('interpret_osv_scanner_exit', *args, **kwargs)

def known_control_component(*args, **kwargs):
    return _call('known_control_component', *args, **kwargs)

def two_source_known_cve(*args, **kwargs):
    return _call('two_source_known_cve', *args, **kwargs)

KNOWN_CONTROL_NAME = "KNOWN_CONTROL_NAME"

KNOWN_CONTROL_VERSION = "KNOWN_CONTROL_VERSION"

class FakeSource(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('FakeSource', **kwargs)
        self.args = args

__all__ = ['KNOWN_CONTROL_CVE', 'OsvHttpSource', 'SbomStore', 'ids_contain', 'ingest_components', 'CLEAN_CONTROL_NAME', 'GithubAdvisorySource', 'interpret_osv_scanner_exit', 'known_control_component', 'two_source_known_cve', 'KNOWN_CONTROL_NAME', 'KNOWN_CONTROL_VERSION', 'FakeSource']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

