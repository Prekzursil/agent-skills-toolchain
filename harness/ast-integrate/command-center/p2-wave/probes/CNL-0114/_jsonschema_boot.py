"""Import jsonschema without the repo-root `platform/` package shadowing stdlib."""
from __future__ import annotations

import sys
from pathlib import Path


def boot() -> None:
    cwd = Path.cwd().resolve()
    cleaned = []
    for p in sys.path:
        if not p:
            continue
        try:
            if Path(p).resolve() == cwd:
                continue
        except OSError:
            pass
        cleaned.append(p)
    sys.path[:] = cleaned
    sys.modules.pop("platform", None)
    # Drop a previously-imported broken jsonschema if any.
    for name in list(sys.modules):
        if name == "jsonschema" or name.startswith("jsonschema."):
            sys.modules.pop(name, None)
