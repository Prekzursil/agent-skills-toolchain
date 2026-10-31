"""Prompt-injection carrier through council stage context."""
from __future__ import annotations

from typing import Any

CARRIERS = ("artifact", "transcript", "tool-output")


def assemble(*parts: str, carrier: str = "artifact") -> dict[str, Any]:
    return {"carrier": carrier, "body": "\n".join(parts), "tokens": []}


def consume(ctx: dict[str, Any], token: str) -> dict[str, Any]:
    body = str(ctx.get("body") or "")
    reached = token in body
    tokens = list(ctx.get("tokens") or [])
    if reached:
        tokens.append(token)
    out = dict(ctx)
    out["tokens"] = tokens
    out["reached"] = reached
    return out


def token_reached(ctx: dict[str, Any], token: str) -> bool:
    return token in (ctx.get("tokens") or []) or token in str(ctx.get("body") or "")
