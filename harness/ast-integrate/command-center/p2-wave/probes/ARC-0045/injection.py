#!/usr/bin/env python3
"""Injection-resistant boundary for workflow and council content.

Content is data. A string that MENTIONS a grant, a tool verb, or `evaluate`
does not mint a grant. Grants exist only as typed objects that passed
declaration-time validation and were then fed to evaluator.evaluate().
"""
from __future__ import annotations

from typing import Any, Mapping

CONTENT_KEYS = frozenset(
    {
        "prompt",
        "instructions",
        "body",
        "markdown",
        "transcript",
        "message",
        "description",
        "notes",
        "content",
    }
)


def extract_content_strings(node: Any, acc: list[str] | None = None) -> list[str]:
    if acc is None:
        acc = []
    if isinstance(node, str):
        acc.append(node)
        return acc
    if isinstance(node, list):
        for item in node:
            extract_content_strings(item, acc)
        return acc
    if isinstance(node, dict):
        for key, value in node.items():
            if key in CONTENT_KEYS or isinstance(value, (str, list, dict)):
                extract_content_strings(value, acc)
    return acc


def content_cannot_mint_grants(document: Mapping[str, Any]) -> dict[str, Any]:
    """True when no content string is treated as a grant object."""
    strings = extract_content_strings(document)
    mentioned = [s for s in strings if "grant" in s.lower() or "evaluate(" in s.lower()]
    minted = document.get("grants") if isinstance(document.get("grants"), list) else []
    # Content strings are never copied into grants. Grants must be a sibling
    # typed list, already validated elsewhere.
    leaked = []
    for row in minted:
        if isinstance(row, str):
            leaked.append("string-grant")
        elif isinstance(row, dict) and row.get("from_content") is True:
            leaked.append("from_content")
    return {
        "ok": len(leaked) == 0,
        "content_strings": len(strings),
        "mentions_grant_or_evaluate": len(mentioned),
        "leaked": leaked,
        "rule": "mention-in-content-is-not-a-grant",
    }
