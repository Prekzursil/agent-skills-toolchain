"""Shared RES-0008 helpers: fixtures, version waterfall, schema extract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "RES-0008"
OUT_REL = "command-center/research/RES-0008.json"
SCHEMA_URL = "https://json.schemastore.org/claude-code-marketplace.json"
DOCS_MARKETPLACES = "https://code.claude.com/docs/en/plugin-marketplaces.md"
DOCS_REFERENCE = "https://code.claude.com/docs/en/plugins-reference.md"
GITHUB_ISSUE = "https://api.github.com/repos/anthropics/claude-code/issues/54280"
PINNED = "0.2.0"
MARKET_ONLY_BUMP = "9.9.9"
PLUGIN_WINS_MARKERS = (
    "plugin.json wins",
    "always uses the `plugin.json` value without warning",
    "always uses the plugin.json value without warning",
    "the plugin.json version **takes priority**",
    "plugin.json version takes priority",
)
VALIDATE_WARNS_MARKERS = (
    "warns when the entry's `version` doesn't match",
    "warns when the entry's version doesn't match",
)

SNAP = HERE / "snapshots"
FIXTURES = HERE / "fixtures"


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_paths(kind: str) -> tuple[Path, Path]:
    root = FIXTURES / kind
    market = root / ".claude-plugin" / "marketplace.json"
    plugin = (
        root
        / "plugins"
        / "res-0008-pin"
        / ".claude-plugin"
        / "plugin.json"
    )
    return market, plugin


def load_fixture(kind: str) -> dict[str, Any]:
    market_path, plugin_path = fixture_paths(kind)
    marketplace = load_json(market_path)
    plugin = load_json(plugin_path)
    plugins = marketplace.get("plugins") or []
    if not plugins:
        raise ValueError(f"{kind} marketplace has no plugins[]")
    entry = plugins[0]
    return {
        "kind": kind,
        "marketplace_path": str(market_path.relative_to(REPO).as_posix()),
        "plugin_path": str(plugin_path.relative_to(REPO).as_posix()),
        "marketplace": marketplace,
        "plugin": plugin,
        "entry": entry,
        "verdict": resolve_plugin_version(plugin, entry),
    }


def _version(doc: dict, key: str = "version") -> str | None:
    val = doc.get(key)
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


def resolve_plugin_version(plugin: dict, entry: dict) -> dict[str, Any]:
    """Documented waterfall: plugin.json version, then marketplace entry version.

    This is the published order in plugins-reference Version management, not a
    guess. A live `claude` binary is a separate observation.
    """
    pv = _version(plugin)
    mv = _version(entry)
    if pv is not None:
        honoured, source = pv, "plugin.json"
    elif mv is not None:
        honoured, source = mv, "marketplace.json"
    else:
        honoured, source = None, "unset"
    contest = pv is not None and mv is not None
    return {
        "plugin_json_version": pv,
        "marketplace_version": mv,
        "honoured_version": honoured,
        "honoured_source": source,
        "contest": contest,
        "identical": bool(contest and pv == mv),
        "precedence_signal": bool(contest and pv != mv),
    }


def extract_marketplace_schema(schema: dict) -> dict[str, Any]:
    if not isinstance(schema, dict):
        raise TypeError("schema must be an object")
    props = schema.get("properties") or {}
    if not isinstance(props, dict):
        props = {}
    plugins = props.get("plugins") or {}
    items = plugins.get("items") if isinstance(plugins, dict) else {}
    item_props = (items.get("properties") or {}) if isinstance(items, dict) else {}
    item_required = list(items.get("required") or []) if isinstance(items, dict) else []
    version_field = item_props.get("version") if isinstance(item_props, dict) else {}
    version_desc = ""
    if isinstance(version_field, dict):
        version_desc = str(version_field.get("description") or "")
    root_ap = schema.get("additionalProperties", "<omitted-default-true>")
    item_ap = items.get("additionalProperties", "<omitted-default-true>") if isinstance(items, dict) else None
    return {
        "$id": schema.get("$id"),
        "$schema": schema.get("$schema"),
        "$comment": schema.get("$comment"),
        "title": schema.get("title"),
        "description": schema.get("description"),
        "required": list(schema.get("required") or []),
        "root_property_names": sorted(props.keys()),
        "root_additionalProperties": root_ap,
        "plugin_entry_required": item_required,
        "plugin_entry_property_names": sorted(item_props.keys())
        if isinstance(item_props, dict)
        else [],
        "plugin_entry_additionalProperties": item_ap,
        "plugin_entry_version_description": version_desc,
        "plugin_entry_version_mentions_plugin_json_priority": any(
            m.lower() in version_desc.lower()
            for m in ("takes priority", "plugin.json wins", "takes precedence")
        ),
    }


def snapshot_path(name: str) -> Path:
    return SNAP / name


def load_fetch_log() -> dict[str, Any]:
    path = SNAP / "FETCH-LOG.json"
    if not path.is_file():
        return {}
    doc = load_json(path)
    return doc if isinstance(doc, dict) else {}


def rail_from_log(key: str) -> dict[str, Any] | None:
    log = load_fetch_log()
    sources = log.get("sources") or {}
    if isinstance(sources, dict) and isinstance(sources.get(key), dict):
        return sources[key]
    return None


def snapshot_text(name: str) -> str:
    path = snapshot_path(name)
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def contains_any(haystack: str, needles: tuple[str, ...]) -> list[str]:
    found = []
    lower = haystack.lower()
    for n in needles:
        if n.lower() in lower:
            found.append(n)
    return found
