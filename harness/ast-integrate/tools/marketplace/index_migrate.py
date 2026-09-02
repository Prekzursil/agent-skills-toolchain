"""Marketplace index schema versioning and forward/back migration (IMP-0073)."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

CURRENT_SCHEMA_VERSION = 2
COMPATIBILITY_WINDOW_VERSIONS = 1
UNSUPPORTED = "UNSUPPORTED"


@dataclass
class ParseResult:
    status: str
    records: list[Any] | None
    parsed_record_count: int | None
    file_record_count: int
    reason: str = ""


def schema_version_of(doc: dict[str, Any] | None) -> int:
    if not isinstance(doc, dict):
        return 1
    for key in ("schema_version", "index_schema_version"):
        if key in doc:
            try:
                return int(doc[key])
            except (TypeError, ValueError):
                return 1
    return 1


def file_record_count(doc: dict[str, Any] | None) -> int:
    if not isinstance(doc, dict):
        return 0
    files = doc.get("files")
    if isinstance(files, list):
        return len(files)
    n = 0
    for key in ("plugins", "packages"):
        val = doc.get(key)
        if isinstance(val, list):
            n += len(val)
    return n


def _plugin_records(doc: dict[str, Any]) -> list[Any]:
    recs: list[Any] = []
    for key in ("plugins", "packages"):
        val = doc.get(key)
        if isinstance(val, list):
            recs.extend(val)
    return recs


def semantics(doc: dict[str, Any]) -> str:
    body = copy.deepcopy(doc) if isinstance(doc, dict) else {}
    for key in ("schema_version", "index_schema_version", "compatibility_window", "files"):
        body.pop(key, None)
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def migrate(doc: dict[str, Any], target: int) -> dict[str, Any]:
    out = copy.deepcopy(doc) if isinstance(doc, dict) else {}
    src = schema_version_of(out)
    target_i = int(target)
    if src == target_i:
        return out
    if src == 1 and target_i == 2:
        plugins = list(out.get("plugins") or [])
        files = []
        for i, plug in enumerate(plugins):
            name = plug.get("name") if isinstance(plug, dict) else f"p{i}"
            files.append({"path": f"plugins/{name}/plugin.json", "plugin": name})
            files.append({"path": f"plugins/{name}/README.md", "plugin": name})
        out["files"] = files
        out["schema_version"] = 2
        out["compatibility_window"] = COMPATIBILITY_WINDOW_VERSIONS
        return out
    if src == 2 and target_i == 1:
        out.pop("files", None)
        out.pop("compatibility_window", None)
        out["schema_version"] = 1
        return out
    out["schema_version"] = target_i
    return out


def lossy_migrate_1_to_2(doc: dict[str, Any]) -> dict[str, Any]:
    out = migrate(doc, 2)
    files = list(out.get("files") or [])
    if files:
        out["files"] = files[: max(1, len(files) // 2)]
    plugins = list(out.get("plugins") or [])
    if len(plugins) > 1:
        out["plugins"] = plugins[:1]
    return out


def parse_index(doc: dict[str, Any], parser_version: int) -> ParseResult:
    file_n = file_record_count(doc)
    src = schema_version_of(doc)
    if int(parser_version) < src:
        return ParseResult(
            status=UNSUPPORTED,
            records=None,
            parsed_record_count=None,
            file_record_count=file_n,
            reason=f"parser_version={parser_version} cannot read schema_version={src}",
        )
    recs = _plugin_records(doc)
    return ParseResult(
        status="OK",
        records=recs,
        parsed_record_count=len(recs),
        file_record_count=file_n,
    )


def lenient_v1_parse(doc: dict[str, Any]) -> list[Any]:
    return list(_plugin_records(doc))
