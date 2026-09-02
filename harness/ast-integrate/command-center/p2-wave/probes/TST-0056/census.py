#!/usr/bin/env python3
"""Field census of numeric ranges in artifact JSON Schemas vs 2^53."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MAX_SAFE = 2**53 - 1
WIDE_NAME_RE = re.compile(
    r"(^|_)(id|ids|timestamp|time_ns|time_ms|epoch|byte|bytes|byte_count|"
    r"size_bytes|count|seed|seq)s?$",
    re.I,
)
SKIP_PARTS = frozenset({"node_modules", ".git"})
WALK_MAP = (
    "properties",
    "patternProperties",
    "dependentSchemas",
    "$defs",
    "definitions",
)
WALK_LIST = ("oneOf", "anyOf", "allOf", "prefixItems")
WALK_ONE = (
    "items",
    "additionalItems",
    "additionalProperties",
    "contains",
    "not",
    "if",
    "then",
    "else",
    "propertyNames",
    "unevaluatedProperties",
    "unevaluatedItems",
)


def type_set(node: dict) -> set[str]:
    t = node.get("type")
    if isinstance(t, str):
        return {t}
    if isinstance(t, list):
        return {x for x in t if isinstance(x, str)}
    return set()


def json_pointer_escape(part: str) -> str:
    return part.replace("~", "~0").replace("/", "~1")


def resolve_pointer(root: Any, pointer: str) -> Any:
    if pointer in ("", "#"):
        return root
    if pointer.startswith("#"):
        pointer = pointer[1:]
    if not pointer:
        return root
    if not pointer.startswith("/"):
        return None
    cur = root
    for raw in pointer.lstrip("/").split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def max_allowed(node: dict, types: set[str]) -> float:
    if "const" in node and isinstance(node["const"], (int, float)) and not isinstance(
        node["const"], bool
    ):
        return float(node["const"])
    if isinstance(node.get("enum"), list):
        nums = [
            float(x)
            for x in node["enum"]
            if isinstance(x, (int, float)) and not isinstance(x, bool)
        ]
        if nums:
            return max(nums)
    caps: list[float] = []
    mx = node.get("maximum")
    if isinstance(mx, (int, float)) and not isinstance(mx, bool):
        caps.append(float(mx))
    ex = node.get("exclusiveMaximum")
    if isinstance(ex, (int, float)) and not isinstance(ex, bool):
        if "integer" in types and "number" not in types:
            caps.append(float(ex) - 1.0)
        else:
            caps.append(float(ex))
    if not caps:
        return math.inf
    return min(caps)


def describe_field(node: dict, pointer: str, types: set[str], schema_rel: str) -> dict:
    cap = max_allowed(node, types)
    name = pointer.rstrip("/").split("/")[-1] if pointer else ""
    name = name.replace("~1", "/").replace("~0", "~")
    return {
        "schema": schema_rel,
        "pointer": pointer or "/",
        "name": name,
        "types": sorted(types),
        "minimum": node.get("minimum")
        if isinstance(node.get("minimum"), (int, float))
        else None,
        "maximum": node.get("maximum")
        if isinstance(node.get("maximum"), (int, float))
        else None,
        "unbounded": cap == math.inf,
        "max_allowed": None if cap == math.inf else cap,
        "can_exceed_2_53": cap > MAX_SAFE,
        "name_suggests_wide": bool(WIDE_NAME_RE.search(name)),
    }


def walk(
    node: Any,
    pointer: str,
    root: dict,
    fields: list[dict],
    visiting: set[int],
    schema_rel: str,
) -> None:
    if isinstance(node, list):
        for i, item in enumerate(node):
            walk(item, f"{pointer}/{i}", root, fields, visiting, schema_rel)
        return
    if not isinstance(node, dict):
        return
    obj_id = id(node)
    if obj_id in visiting:
        return
    visiting.add(obj_id)
    try:
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#"):
            target = resolve_pointer(root, ref)
            if target is not None:
                walk(target, pointer, root, fields, visiting, schema_rel)
            return
        types = type_set(node)
        if types & {"integer", "number"}:
            fields.append(describe_field(node, pointer, types, schema_rel))
        for key in WALK_MAP:
            sub = node.get(key)
            if isinstance(sub, dict):
                for name, child in sub.items():
                    walk(
                        child,
                        f"{pointer}/{key}/{json_pointer_escape(str(name))}",
                        root,
                        fields,
                        visiting,
                        schema_rel,
                    )
        for key in WALK_LIST:
            sub = node.get(key)
            if isinstance(sub, list):
                for i, child in enumerate(sub):
                    walk(
                        child,
                        f"{pointer}/{key}/{i}",
                        root,
                        fields,
                        visiting,
                        schema_rel,
                    )
        for key in WALK_ONE:
            sub = node.get(key)
            if isinstance(sub, dict):
                walk(sub, f"{pointer}/{key}", root, fields, visiting, schema_rel)
    finally:
        visiting.discard(obj_id)


def iter_schema_files(repo: Path) -> list[Path]:
    found: list[Path] = []
    for rel in ("command-center/schema", "tools"):
        root = repo / rel
        if not root.is_dir():
            continue
        for path in root.rglob("*.schema.json"):
            if SKIP_PARTS.intersection(path.parts):
                continue
            if "p2-wave" in path.parts and "probes" in path.parts:
                continue
            found.append(path)
    return sorted(set(found), key=lambda p: p.as_posix())


def fields_in_schema(path: Path, repo: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    doc = json.loads(raw)
    if not isinstance(doc, dict):
        return []
    rel = path.relative_to(repo).as_posix()
    fields: list[dict] = []
    walk(doc, "", doc, fields, set(), rel)
    return fields


def integer_fields_unbounded(schema: dict, schema_rel: str = "<memory>") -> list[dict]:
    fields: list[dict] = []
    if not isinstance(schema, dict):
        return fields
    walk(schema, "", schema, fields, set(), schema_rel)
    return [
        f
        for f in fields
        if "integer" in f["types"] and f["can_exceed_2_53"]
    ]


def js_lib_files(repo: Path) -> list[Path]:
    lib = repo / "tools" / "lib"
    if not lib.is_dir():
        return []
    return sorted(
        p for p in lib.iterdir() if p.is_file() and p.suffix in {".mjs", ".js"}
    )


def js_consumer_rows(repo: Path) -> list[dict]:
    rows = []
    for path in js_lib_files(repo):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(repo).as_posix()
        rows.append(
            {
                "path": rel,
                "bytes": len(text.encode("utf-8")),
                "has_json_parse": "JSON.parse" in text,
                "has_lossless": "parseLossless" in text
                and "rewriteUnsafeIntegerTokens" in text,
                "schema": "tools/lib/handled-ledger.schema.json"
                if path.name.startswith("handled-ledger")
                else None,
            }
        )
    return rows


def pick_widest(fields: list[dict]) -> dict | None:
    if not fields:
        return None

    def key(f: dict) -> tuple:
        cap = math.inf if f["unbounded"] else float(f["max_allowed"] or 0)
        wide = 1 if f.get("name_suggests_wide") else 0
        integer = 1 if "integer" in f["types"] else 0
        return (1 if f["can_exceed_2_53"] else 0, integer, wide, cap, f["schema"], f["pointer"])

    return max(fields, key=key)


def live_census(repo: Path | None = None) -> dict:
    repo = repo or REPO
    files = iter_schema_files(repo)
    fields: list[dict] = []
    parse_failures: list[str] = []
    for path in files:
        try:
            fields.extend(fields_in_schema(path, repo))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            parse_failures.append(f"{path.relative_to(repo).as_posix()}:{type(exc).__name__}")
    exceeding = [f for f in fields if f["can_exceed_2_53"]]
    wide_named = [f for f in exceeding if f.get("name_suggests_wide")]
    js_rows = js_consumer_rows(repo)
    js_schema = repo / "tools" / "lib" / "handled-ledger.schema.json"
    js_schema_fields: list[dict] = []
    if js_schema.is_file():
        js_schema_fields = fields_in_schema(js_schema, repo)
    return {
        "max_safe_integer": MAX_SAFE,
        "schema_file_count": len(files),
        "numeric_field_count": len(fields),
        "can_exceed_2_53_count": len(exceeding),
        "wide_named_exceeding_count": len(wide_named),
        "parse_failures": parse_failures,
        "widest": pick_widest(fields),
        "exceeding": exceeding,
        "js_consumers": js_rows,
        "js_consumed_schema": "tools/lib/handled-ledger.schema.json"
        if js_schema.is_file()
        else None,
        "js_consumed_numeric_fields": js_schema_fields,
        "js_consumed_unbounded_integers": integer_fields_unbounded(
            json.loads(js_schema.read_text(encoding="utf-8"))
            if js_schema.is_file()
            else {},
            "tools/lib/handled-ledger.schema.json",
        ),
    }


def detector_on_schema_file(path: Path, repo: Path) -> list[dict]:
    return [f for f in fields_in_schema(path, repo) if f["can_exceed_2_53"]]
