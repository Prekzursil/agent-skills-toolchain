"""Safety rails for chaos primitives."""
from __future__ import annotations


class DelegatedFaultError(RuntimeError):
    pass
