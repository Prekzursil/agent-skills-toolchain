"""Configuration parsers under test: the live toolchain json.loads plus two controls."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
KEYS = HERE / "fixtures" / "keys"


def _load_text(name: str) -> str:
    return (KEYS / name).read_text(encoding="utf-8")


def fixture_case_distinct() -> str:
    return _load_text("case-distinct.json")


def fixture_duplicate_exact() -> str:
    return _load_text("duplicate-exact.json")


def fixture_control_clean() -> str:
    return _load_text("control-clean.json")


def parse_cpython_json_loads(text: str) -> dict[str, Any]:
    """The parser the A2 installer/freeze hook and generator actually call."""
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return {
            "parser": "json.loads",
            "ok": False,
            "error": f"{type(exc).__name__}:{exc}",
            "keys": [],
            "values": {},
            "outcome": "error",
        }
    if not isinstance(obj, dict):
        return {
            "parser": "json.loads",
            "ok": False,
            "error": f"not-object:{type(obj).__name__}",
            "keys": [],
            "values": {},
            "outcome": "error",
        }
    values = {str(k): obj[k] for k in obj}
    return {
        "parser": "json.loads",
        "ok": True,
        "error": None,
        "keys": list(obj.keys()),
        "values": values,
        "outcome": "parsed",
    }


def parse_strict_duplicate(text: str) -> dict[str, Any]:
    """Errors on exact duplicate keys. Distinguishes last-wins from a clear error."""

    def hook(pairs: list[tuple[Any, Any]]) -> dict[str, Any]:
        seen: dict[str, Any] = {}
        for key, val in pairs:
            if not isinstance(key, str):
                raise ValueError(f"non-string-key:{type(key).__name__}")
            if key in seen:
                raise ValueError(f"duplicate-key:{key}")
            seen[key] = val
        return seen

    try:
        obj = json.JSONDecoder(object_pairs_hook=hook).decode(text)
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "parser": "strict-duplicate",
            "ok": False,
            "error": f"{type(exc).__name__}:{exc}",
            "keys": [],
            "values": {},
            "outcome": "error",
        }
    return {
        "parser": "strict-duplicate",
        "ok": True,
        "error": None,
        "keys": list(obj.keys()),
        "values": {str(k): obj[k] for k in obj},
        "outcome": "parsed",
    }


def parse_casefold_last_wins(text: str) -> dict[str, Any]:
    """Case-insensitive last-wins consumer (Windows / PowerShell ConvertFrom-Json class)."""

    def hook(pairs: list[tuple[Any, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        fold: dict[str, str] = {}
        for key, val in pairs:
            if not isinstance(key, str):
                raise ValueError(f"non-string-key:{type(key).__name__}")
            fk = key.casefold()
            prev = fold.get(fk)
            if prev is not None:
                del out[prev]
            out[key] = val
            fold[fk] = key
        return out

    try:
        obj = json.JSONDecoder(object_pairs_hook=hook).decode(text)
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "parser": "casefold-last-wins",
            "ok": False,
            "error": f"{type(exc).__name__}:{exc}",
            "keys": [],
            "values": {},
            "outcome": "error",
        }
    return {
        "parser": "casefold-last-wins",
        "ok": True,
        "error": None,
        "keys": list(obj.keys()),
        "values": {str(k): obj[k] for k in obj},
        "outcome": "parsed",
    }


PARSERS: dict[str, Callable[[str], dict[str, Any]]] = {
    "json.loads": parse_cpython_json_loads,
    "strict-duplicate": parse_strict_duplicate,
    "casefold-last-wins": parse_casefold_last_wins,
}


def classify_keys(result: dict[str, Any], expected_pair: tuple[str, str]) -> str:
    if not result.get("ok"):
        return "error"
    keys = [str(k) for k in (result.get("keys") or [])]
    a, b = expected_pair
    fold = {k.casefold() for k in keys}
    has_a = a in keys
    has_b = b in keys
    if has_a and has_b:
        return "both-kept"
    if a.casefold() in fold and not (has_a and has_b):
        return "silent-last-wins"
    return "other"


def control_survived(result: dict[str, Any]) -> bool:
    if not result.get("ok"):
        return False
    keys = set(result.get("keys") or [])
    values = result.get("values") or {}
    return "alpha" in keys and "beta" in keys and values.get("alpha") == 1 and values.get("beta") == 2
