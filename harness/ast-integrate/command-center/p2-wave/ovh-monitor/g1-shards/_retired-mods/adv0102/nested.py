"""Nested disagreement questions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BoundedQuestion:
    name: str
    parent: str | None = None
    options: tuple = ()
    payload: dict | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if args:
            self.name = str(args[0])
        else:
            self.name = str(kwargs.get("name") or kwargs.get("id") or "q")
        self.parent = kwargs.get("parent")
        self.options = tuple(kwargs.get("options") or ())
        self.payload = dict(kwargs)
