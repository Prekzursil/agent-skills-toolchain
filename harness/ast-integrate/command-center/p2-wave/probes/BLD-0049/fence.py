"""Structural DATA fence for BLD-0049 canary measurement.

This is the measurement instrument, not a claim that the production runner
uses it. A path is FENCED only when these markers wrap the payload. A comment
that says "untrusted DATA" is not a fence.
"""
from __future__ import annotations

import hashlib
import re

BEGIN = "<<<UNTRUSTED_DATA"
END = "<<<END_UNTRUSTED_DATA>>>"

_BLOCK = re.compile(
    re.escape(BEGIN)
    + r" origin=(?P<origin>\S+) sha256=(?P<sha>[0-9a-f]{64}) bytes=(?P<n>\d+)>>>\n"
    r"(?P<body>.*?)\n"
    + re.escape(END)
    + r" sha256=(?P<sha2>[0-9a-f]{64})>>>",
    re.DOTALL,
)


def digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def wrap(payload: str, origin: str) -> str:
    sha = digest(payload)
    n = len(payload.encode("utf-8"))
    return (
        f"{BEGIN} origin={origin} sha256={sha} bytes={n}>>>\n"
        f"{payload}\n"
        f"{END} sha256={sha}>>>"
    )


def split_prompt(prompt: str) -> dict[str, object]:
    """Return DATA blocks plus the instruction-channel remainder."""
    data: list[dict[str, str]] = []
    instruction = prompt
    for m in _BLOCK.finditer(prompt):
        if m.group("sha") != m.group("sha2"):
            continue
        body = m.group("body")
        if digest(body) != m.group("sha"):
            continue
        data.append({"origin": m.group("origin"), "body": body, "sha256": m.group("sha")})
        instruction = instruction.replace(m.group(0), "\n")
    return {"data": data, "instruction": instruction}
