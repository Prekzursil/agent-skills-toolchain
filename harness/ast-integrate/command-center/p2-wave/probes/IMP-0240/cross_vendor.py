"""Cross-vendor compatibility: canonicalize two vendor shapes and compare.

A translation that drops a content part is a compatibility failure, not a
cosmetic difference.
"""
from __future__ import annotations

from typing import Any


def anthropic_to_canonical(msg: dict[str, Any]) -> dict[str, Any]:
    content = msg.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "".join(str(part.get("text") or "") for part in content if isinstance(part, dict))
    else:
        text = ""
    return {"role": msg.get("role"), "text": text}


def openai_to_canonical(msg: dict[str, Any]) -> dict[str, Any]:
    content = msg.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "".join(
            str(part.get("text") or "")
            for part in content
            if isinstance(part, dict) and part.get("type") in {None, "text"}
        )
    else:
        text = ""
    return {"role": msg.get("role"), "text": text}


def openai_mutant_drops_tail(msg: dict[str, Any]) -> dict[str, Any]:
    content = msg.get("content")
    if isinstance(content, list) and content:
        content = content[:1]
    return openai_to_canonical({**msg, "content": content})


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    left = anthropic_to_canonical(a)
    right = openai_to_canonical(b)
    equal = left == right
    return {
        "equivalent": equal,
        "anthropic": left,
        "openai": right,
        "method": "canonical-roundtrip",
    }
