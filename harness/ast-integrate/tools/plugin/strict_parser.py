"""Strict plugin.json parser: reject bare unknown keys, accept x-."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FROZEN_PATH = HERE / "schema" / "frozen-keys.json"


def frozen_keys() -> set[str]:
    if FROZEN_PATH.is_file():
        data = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(map(str, data))
        if isinstance(data, dict):
            keys = data.get("frozen_top_level_keys") or data.get("keys") or data.get("frozen") or []
            return set(map(str, keys))
    return {
        "name",
        "version",
        "description",
        "author",
        "license",
        "keywords",
        "homepage",
        "compatibility",
        "interpreters",
        "entrypoints",
        "payload",
        "deploy",
        "min_client_version",
        "supported_clients",
    }


def parse_manifest(obj: dict[str, Any]) -> dict[str, Any]:
    frozen = frozen_keys()
    errors: list[str] = []
    classified: dict[str, str] = {}
    for key in obj.keys():
        if key in frozen:
            classified[key] = "frozen"
        elif str(key).startswith("x-"):
            classified[key] = "extension"
        else:
            classified[key] = "unknown-bare"
            errors.append(f"bare unknown key {key}")
    return {
        "ok": not errors,
        "errors": errors,
        "classified": classified,
        "keys": sorted(obj.keys()),
        "frozen": sorted(k for k, v in classified.items() if v == "frozen"),
    }


MARKET_SCHEMA_PATH = HERE / "schema" / "marketplace.schema.json"


def _market_schema() -> dict[str, Any]:
    return json.loads(MARKET_SCHEMA_PATH.read_text(encoding="utf-8"))


def parse_marketplace(doc: dict[str, Any]) -> dict[str, Any]:
    """Validate a marketplace index against the canonical marketplace schema.

    Every plugin entry is closed (additionalProperties: false), so a planted
    digest/sha256/origin key on an entry is a REJECTION, not an extension.
    """
    schema = _market_schema()
    errors: list[str] = []
    top_props = set((schema.get("properties") or {}).keys())
    for key in doc.keys():
        if key not in top_props:
            errors.append(f"marketplace top-level key {key} not allowed")
    for req in schema.get("required") or []:
        if req not in doc:
            errors.append(f"marketplace missing required key {req}")
    entry_schema = (schema.get("definitions") or {}).get("plugin_entry") or {}
    entry_props = set((entry_schema.get("properties") or {}).keys())
    entry_required = list(entry_schema.get("required") or [])
    plugins = doc.get("plugins")
    if not isinstance(plugins, list):
        errors.append("marketplace plugins must be an array")
        plugins = []
    for i, entry in enumerate(plugins):
        if not isinstance(entry, dict):
            errors.append(f"plugins/{i} must be an object")
            continue
        for key in entry.keys():
            if key not in entry_props:
                errors.append(f"plugins/{i} key {key} not allowed (additionalProperties: false)")
        for req in entry_required:
            if req not in entry:
                errors.append(f"plugins/{i} missing required key {req}")
    return _with_rejections(
        {
            "ok": not errors,
            "errors": errors,
            "kind": "marketplace",
            "keys": sorted(doc.keys()),
            "n_plugins": len(plugins),
        }
    )


def parse_path(path: Path | str) -> dict[str, Any]:
    if isinstance(path, dict):
        return _with_rejections(parse_manifest(path))
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise TypeError("marketplace document must be an object")
    return _with_rejections(parse_manifest(obj))


def _with_rejections(parsed: dict[str, Any]) -> dict[str, Any]:
    errors = list(parsed.get("errors") or [])
    parsed["rejection_messages"] = errors
    parsed["rejected"] = bool(errors)
    return parsed


def parse(*args: Any, obj: dict[str, Any] | None = None, path: Path | str | None = None, **kwargs: Any) -> dict[str, Any]:
    """Accept parse(path), parse(doc), parse(kind, doc), parse(path=...), parse(obj=...)."""
    payload: Any = None
    if len(args) >= 2 and args[0] == "marketplace":
        doc = args[1]
        if isinstance(doc, (str, Path)):
            doc = json.loads(Path(doc).read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            raise TypeError("marketplace document must be an object")
        return parse_marketplace(doc)
    if len(args) >= 2:
        payload = args[1]
    elif len(args) == 1:
        payload = args[0]
    elif path is not None:
        payload = path
    elif obj is not None:
        payload = obj
    elif kwargs:
        payload = kwargs.get("doc") or kwargs.get("data") or kwargs.get("manifest")
    if isinstance(payload, dict):
        return _with_rejections(parse_manifest(payload))
    if payload is None:
        return _with_rejections(parse_manifest({}))
    return parse_path(payload)
