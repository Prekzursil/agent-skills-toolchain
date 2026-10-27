"""Planted dependency graphs for IMP-0082 cycle detection."""
from __future__ import annotations

from typing import Any

EXPECTED_SELF = [["loop", "loop"]]
EXPECTED_TWO = [["a", "b", "a"]]
EXPECTED_LONG = [["p", "q", "r", "s", "p"]]


def _pkg(deps: dict[str, dict[str, str]]) -> dict[str, Any]:
    return {"version": "1.0.0", "dependencies": deps}


def self_cycle() -> dict[str, Any]:
    return {
        "packages": {
            "loop": _pkg({"required": {"loop": "*"}}),
        }
    }


def two_node_cycle() -> dict[str, Any]:
    return {
        "packages": {
            "a": _pkg({"required": {"b": "^1.0.0"}}),
            "b": _pkg({"required": {"a": "^1.0.0"}}),
        }
    }


def long_cycle() -> dict[str, Any]:
    return {
        "packages": {
            "p": _pkg({"required": {"q": "*"}}),
            "q": _pkg({"required": {"r": "*"}}),
            "r": _pkg({"required": {"s": "*"}}),
            "s": _pkg({"required": {"p": "*"}}),
        }
    }


def diamond() -> dict[str, Any]:
    return {
        "packages": {
            "top": _pkg({"required": {"left": "*", "right": "*"}}),
            "left": _pkg({"required": {"bottom": "*"}}),
            "right": _pkg({"required": {"bottom": "*"}}),
            "bottom": _pkg({"required": {}}),
        }
    }


def kinds_distinct() -> dict[str, Any]:
    return {
        "packages": {
            "consumer": _pkg(
                {
                    "required": {"lib-req": "^2.0.0"},
                    "optional": {"lib-opt": "~1.4.0"},
                    "peer": {"lib-peer": ">=3.0.0 <4.0.0"},
                    "dev": {"lib-dev": "*"},
                }
            ),
            "lib-req": _pkg({}),
            "lib-opt": _pkg({}),
            "lib-peer": _pkg({}),
            "lib-dev": _pkg({}),
        }
    }


def peer_only_mutual() -> dict[str, Any]:
    return {
        "packages": {
            "alpha": _pkg({"peer": {"beta": "*"}}),
            "beta": _pkg({"peer": {"alpha": "*"}}),
        }
    }
