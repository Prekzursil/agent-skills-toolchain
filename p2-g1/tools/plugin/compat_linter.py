"""Compatibility linter: additive unknown keys must be x- prefixed."""
from __future__ import annotations

from typing import Any

from strict_parser import parse_manifest


def lint_manifest(obj: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_manifest(obj)
    additive = [
        k for k, kind in parsed["classified"].items() if kind == "unknown-bare"
    ]
    return {
        "ok": parsed["ok"],
        "errors": list(parsed["errors"]),
        "additive_rejected": additive,
        "classified": parsed["classified"],
    }
