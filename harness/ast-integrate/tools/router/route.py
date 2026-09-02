"""Query router used by `ast route`. IMP-0403."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from router.nofit import route as nofit_route, load_index, VERDICT_NOFIT, VERDICT_SELECTED


def _flatten_triggers(cap: dict[str, Any]) -> list[str]:
    trig = cap.get("triggers")
    words: list[str] = []
    if isinstance(trig, dict):
        for value in trig.values():
            if isinstance(value, list):
                words.extend(str(item) for item in value)
            elif isinstance(value, str):
                words.append(value)
    elif isinstance(trig, list):
        words.extend(str(item) for item in trig)
    return words


def route_query(query: str, index: str | Path | None = None, cwd: str | None = None, **kwargs: Any) -> dict[str, Any]:
    if index is None:
        index = kwargs.get("index")
    if cwd is None:
        cwd = kwargs.get("cwd")
    caps: list[dict[str, Any]] = []
    if index:
        path = Path(index)
        if path.is_file():
            caps = load_index(path)
    stripped: list[dict[str, Any]] = []
    for cap in caps:
        row = {k: v for k, v in cap.items() if k != "body"}
        row["triggers"] = _flatten_triggers(cap)
        stripped.append(row)
    result = nofit_route(query, stripped)
    result["cwd"] = cwd
    result["index"] = str(index) if index else None
    result["injection_performed"] = False
    result["injected"] = []
    return result
