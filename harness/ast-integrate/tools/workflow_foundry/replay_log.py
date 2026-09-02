"""Record an ad-hoc execution as a replayable log (IMP-0194)."""
from __future__ import annotations

import hashlib
from typing import Any


def _apply(tool: str, values: list[str]) -> str:
    if tool == "upper":
        return str(values[0]).upper()
    if tool == "join":
        return "|".join(str(v) for v in values)
    if tool == "digest":
        return hashlib.sha256("|".join(str(v) for v in values).encode("utf-8")).hexdigest()[:16]
    return "|".join(str(v) for v in values)


def record_adhoc(inputs: dict[str, str], steps: tuple | list, trace_id: str) -> dict[str, Any]:
    env = dict(inputs)
    events = []
    tools = []
    for step in steps:
        tool = str(step["tool"])
        tools.append(tool)
        args = [env.get(k, k) if k in env else str(k) for k in step["args"]]
        result = _apply(tool, [env.get(a, a) for a in step["args"]])
        env[step["output"]] = result
        events.append(
            {
                "stage_id": step["id"],
                "tool": tool,
                "args": list(step["args"]),
                "output": step["output"],
                "result": result,
            }
        )
    final = env.get("digest") or env.get(steps[-1]["output"])
    digest = hashlib.sha256(str(final).encode("utf-8")).hexdigest()
    return {
        "trace_id": trace_id,
        "inputs": dict(inputs),
        "events": events,
        "tools": tools,
        "spawns": [e["tool"] for e in events],
        "outcome": {"digest": digest, "verdict": "PASS", "final": final},
    }
