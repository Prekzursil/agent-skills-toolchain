#!/usr/bin/env python3
"""TST-0181 measured layer: hooks-config loader (with a $schema-crash mutant).

Loaded-set semantics: every hook entry whose command target exists is LOADED;
a hook whose file is missing is a LOUD per-hook error (never a silent zero).
The $schema key is metadata: it must be ignored entirely.
"""
from __future__ import annotations

import json
from pathlib import Path


class HookLoadError(Exception):
    def __init__(self, message: str, missing: list[str] | None = None):
        super().__init__(message)
        self.missing = missing or []


def load_hooks(config_path: Path, base_dir: Path, *, crash_on_schema: bool = False) -> dict:
    """Returns {loaded: {name: command}, errors: [missing files]}.

    The mutant (crash_on_schema=True) reproduces the regression seed: any
    $schema key in the config makes the client load ZERO hooks.
    """
    doc = json.loads(config_path.read_text(encoding="utf-8"))
    if crash_on_schema and "$schema" in doc:
        return {"loaded": {}, "errors": [], "crashed_on_schema": True}
    loaded: dict[str, str] = {}
    errors: list[str] = []
    for name, spec in (doc.get("hooks") or {}).items():
        cmd = spec.get("command") if isinstance(spec, dict) else None
        target = base_dir / (spec.get("file") if isinstance(spec, dict) else None)
        if cmd is None:
            errors.append(name + ": missing command")
            continue
        if not target.is_file():
            errors.append(name + ": hook file missing: " + str(spec.get("file")))
            continue
        loaded[name] = cmd
    return {"loaded": loaded, "errors": errors, "crashed_on_schema": False}
