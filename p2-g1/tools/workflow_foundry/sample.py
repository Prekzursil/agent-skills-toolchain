"""Sample ad-hoc trace inputs for IMP-0194."""
from __future__ import annotations

OMITTED_GAP = "stop-rule: owner-ask"

SAMPLE_INPUTS = {
    "a": "hello",
    "b": "world",
    "op": "join",
}

SAMPLE_STEPS = (
    {"id": "s1", "tool": "upper", "args": ["a"], "output": "a_up"},
    {"id": "s2", "tool": "join", "args": ["a_up", "b"], "output": "joined"},
    {"id": "s3", "tool": "digest", "args": ["joined"], "output": "digest"},
)
