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

__surface__ = 'council.protocol.premortem'

FAILED_PREMISE = "FAILED_PREMISE"

class Acceptance(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('Acceptance', **kwargs)
        self.args = args

class ActionPlan(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('ActionPlan', **kwargs)
        self.args = args

class CauseStatement(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('CauseStatement', **kwargs)
        self.args = args

class Mitigation(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('Mitigation', **kwargs)
        self.args = args

class RecordingKernel(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('RecordingKernel', **kwargs)
        self.args = args

def carry_into_action_plan(*args, **kwargs):
    return _call('carry_into_action_plan', *args, **kwargs)

def drop_mode_silently(*args, **kwargs):
    return _call('drop_mode_silently', *args, **kwargs)

def harvest(*args, **kwargs):
    return _call('harvest', *args, **kwargs)

def omitted_unmitigated(*args, **kwargs):
    return _call('omitted_unmitigated', *args, **kwargs)

class KernelBypass(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('KernelBypass', **kwargs)
        self.args = args

class PremiseMissing(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('PremiseMissing', **kwargs)
        self.args = args

class SchemaInvalid(_NS):
    def __init__(self, *args, **kwargs):
        super().__init__('SchemaInvalid', **kwargs)
        self.args = args

__all__ = ['FAILED_PREMISE', 'Acceptance', 'ActionPlan', 'CauseStatement', 'Mitigation', 'RecordingKernel', 'carry_into_action_plan', 'drop_mode_silently', 'harvest', 'omitted_unmitigated', 'KernelBypass', 'PremiseMissing', 'SchemaInvalid']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

