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

__surface__ = 'foundry.runtime'


class TypedWorkflowError(Exception):
    pass


def execute(workflow: Any = None, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Run a typed-workflow dict through handler_table. No network, no shell."""
    wf = workflow if isinstance(workflow, dict) else {}
    if not wf and args and isinstance(args[0], dict):
        wf = args[0]
    inputs = kwargs.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
    handlers = kwargs.get("handler_table") or kwargs.get("handlers") or {}
    if not isinstance(handlers, dict):
        handlers = {}
    ctx: dict[str, Any] = {"inputs": dict(inputs), "workflow": wf, "ok": True, "result": {}}
    stages = wf.get("stages") if isinstance(wf.get("stages"), list) else []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        hid = stage.get("handler") or stage.get("id")
        fn = handlers.get(hid)
        if not callable(fn):
            continue
        fn(ctx)
    result = ctx.get("result")
    outputs = result if isinstance(result, dict) else {"value": result}
    return {
        "ok": ctx.get("ok", True) is True,
        "outputs": outputs,
        "inputs": dict(inputs),
        "workflow_id": wf.get("id"),
        "spawned": False,
    }


def load_workflow(path=None, *args, **kwargs):
    from pathlib import Path
    import json

    target = path if path is not None else (args[0] if args else None)
    if target is None:
        raise TypedWorkflowError("JSON typed-workflow path required")
    p = Path(target)
    if p.suffix.lower() == ".py" or p.name.endswith(".py"):
        raise TypedWorkflowError("bespoke script refused; typed workflow must be JSON")
    if p.suffix.lower() not in {".json"}:
        raise TypedWorkflowError("typed workflow must be JSON")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("kind") not in {"typed-workflow", "workflow"}:
        raise TypedWorkflowError("document is not a typed-workflow JSON")
    if not isinstance(doc.get("stages"), list):
        raise TypedWorkflowError("typed workflow JSON missing stages")
    return doc

__all__ = ['execute', 'TypedWorkflowError', 'load_workflow']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

