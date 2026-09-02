"""Council deliberation protocols (P01-P58) as executable modules and data.

Each submodule implements one protocol engine (``oxford`` for P07, ``negotiate`` for
the mediated bargaining protocol, ``hats`` for P30, ...) or a protocol-wide service:
``catalog`` is the canonical registry of the 58 protocol-as-data records and
``plugin`` is the kernel-primitive gate that decides whether a record is expressible
on the council kernel.  Import the submodule you need, for example
``from council.protocol.catalog import by_id``; this package deliberately re-exports
nothing so that importing it never pulls every engine into memory.
"""
from __future__ import annotations

__all__ = [
    "betting",
    "blind_first",
    "brainstorm",
    "catalog",
    "crossexam",
    "hats",
    "negotiate",
    "ngt",
    "oxford",
    "plugin",
    "premortem",
    "scenario",
    "socratic",
    "steelman",
]
