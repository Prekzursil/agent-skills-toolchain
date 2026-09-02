#!/usr/bin/env python3
"""Draft-07 validator over the captured SchemaStore plugin.json schema.

Also reconstructs Codex HooksFile deny_unknown_fields from the captured
codex-rs source. Neither path claims to be a live `claude plugin validate`
binary; this worktree does not ship that CLI.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SNAP = HERE / "snapshots"
SCHEMA_PATH = SNAP / "claude-code-plugin-manifest.schema.json"
CODEX_RS = SNAP / "codex-hook_config.rs"

# Official docs table as of the captured plugins-reference.html (2026-08-24).
# Required: name only. Optional keys listed in the metadata + component tables.
DOCS_REQUIRED = ("name",)
DOCS_OPTIONAL = (
    "$schema",
    "displayName",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "metadata",
    "defaultEnabled",
    "skills",
    "commands",
    "agents",
    "workflows",
    "hooks",
    "mcpServers",
    "outputStyles",
    "lspServers",
    "experimental",
    "userConfig",
    "channels",
    "dependencies",
)
DOCS_KNOWN = frozenset(DOCS_REQUIRED + DOCS_OPTIONAL)

HOOKSFILE_FIELD_RE = re.compile(
    r"pub struct HooksFile \{(?P<body>.*?)\n\}",
    re.DOTALL,
)
HOOKSFILE_MEMBER_RE = re.compile(r"pub ([a-zA-Z0-9_]+):")


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def schema_known_keys(schema: dict | None = None) -> frozenset[str]:
    schema = schema if schema is not None else load_schema()
    props = schema.get("properties") or {}
    return frozenset(str(k) for k in props.keys())


def schema_field_table(schema: dict | None = None) -> list[dict]:
    schema = schema if schema is not None else load_schema()
    required = set(schema.get("required") or [])
    rows = []
    for name, spec in (schema.get("properties") or {}).items():
        types = spec.get("type")
        if types is None and "anyOf" in spec:
            types = [x.get("type") for x in spec["anyOf"] if isinstance(x, dict)]
        rows.append(
            {
                "name": name,
                "required": name in required,
                "schema_type": types,
                "listed_in_schemastore_properties": True,
                "listed_in_docs_2026_08_24": name in DOCS_KNOWN,
                "description": spec.get("description"),
            }
        )
    listed = {r["name"] for r in rows}
    for name in DOCS_KNOWN:
        if name in listed:
            continue
        rows.append(
            {
                "name": name,
                "required": name in DOCS_REQUIRED,
                "schema_type": None,
                "listed_in_schemastore_properties": False,
                "listed_in_docs_2026_08_24": True,
                "description": (
                    "Present in code.claude.com/docs/en/plugins-reference "
                    "on 2026-08-24; absent from SchemaStore properties "
                    "(generated 2026-04-23). Root additionalProperties is "
                    "unspecified so Draft-07 accepts the key silently."
                ),
            }
        )
    rows.sort(key=lambda r: (not r["required"], r["name"]))
    return rows


def validate_plugin_manifest(instance: dict, schema: dict | None = None) -> dict:
    schema = schema if schema is not None else load_schema()
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    messages = [e.message for e in errors]
    known = schema_known_keys(schema)
    unknown = [k for k in instance.keys() if k not in known]
    docs_unknown = [k for k in instance.keys() if k not in DOCS_KNOWN]
    missing_required = [
        k for k in (schema.get("required") or []) if k not in instance
    ]
    valid = len(errors) == 0
    if unknown:
        docs_mode = "WARNING"
    elif valid:
        docs_mode = "OK"
    else:
        docs_mode = "ERROR"
    return {
        "validator": "jsonschema.Draft7Validator",
        "jsonschema_version": jsonschema.__version__,
        "schema_id": schema.get("$id"),
        "schema_comment": schema.get("$comment"),
        "schema_path": str(SCHEMA_PATH.relative_to(REPO)),
        "root_additionalProperties": schema.get(
            "additionalProperties", "<ABSENT default true>"
        ),
        "valid": valid,
        "errors": messages,
        "missing_required": missing_required,
        "unknown_top_level_keys_vs_schemastore_properties": unknown,
        "unknown_top_level_keys_vs_docs": docs_unknown,
        "docs_mode_verdict": docs_mode,
        "instance_keys": list(instance.keys()),
    }


def hooksfile_allowed_fields(source: str | None = None) -> list[str]:
    text = source if source is not None else CODEX_RS.read_text(encoding="utf-8")
    match = HOOKSFILE_FIELD_RE.search(text)
    if not match:
        raise RuntimeError("HooksFile struct not found in captured Codex source")
    body = match.group("body")
    names = HOOKSFILE_MEMBER_RE.findall(body)
    if not names:
        raise RuntimeError("HooksFile members not parsed")
    return names


def deny_unknown_fields_holds(source: str | None = None) -> bool:
    text = source if source is not None else CODEX_RS.read_text(encoding="utf-8")
    return bool(
        re.search(
            r"#\[serde\(deny_unknown_fields\)\]\s*\n(?:#\[[^\]]+\]\s*\n)*"
            r"pub struct HooksFile",
            text,
        )
    )


def validate_codex_hooksfile(instance: dict) -> dict:
    allowed = hooksfile_allowed_fields()
    unknown = [k for k in instance.keys() if k not in allowed]
    valid = len(unknown) == 0
    expected = " or ".join(f"`{n}`" for n in allowed)
    errors = []
    if unknown:
        shown = unknown[0]
        errors.append(f"unknown field `{shown}`, expected {expected}")
    return {
        "validator": "codex-HooksFile-deny_unknown_fields-replica",
        "source_path": str(CODEX_RS.relative_to(REPO)),
        "deny_unknown_fields": deny_unknown_fields_holds(),
        "allowed_fields": allowed,
        "valid": valid,
        "errors": errors,
        "unknown_keys": unknown,
        "instance_keys": list(instance.keys()),
    }


def format_verbatim(label: str, result: dict) -> str:
    payload = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True)
    return f"BEGIN {label}\n{payload}\nEND {label}"
