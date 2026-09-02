"""JSON Schema 2020-12 for the ARC-0078 plugin manifest contract."""

from __future__ import annotations

from clauses import (
    COMPAT_RULE,
    CONTRACT_REL,
    INTERPRETER_RULE,
    NO_ADV_RULE,
    REQUIRED_FIELDS_RULE,
    SCHEMA_URI,
    SCHEMA_VERSION,
    SENTINEL,
    UNKNOWN_FIELD_POLICY,
    ZERO_HOOKS_RULE,
)

SEMVER = (
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:[-+][A-Za-z0-9.-]+)?$"
)
PLUGIN_NAME = r"^[a-z0-9][a-z0-9-]{0,62}$"
HOOK_ID = r"^[a-z][a-z0-9._-]{0,62}$"
X_KEY = r"^x-[a-z0-9][a-z0-9-]*$"
HOOKS_PATH = r"^\./.+\.json$"
SCRIPT_PATH = r"^[A-Za-z0-9._/=+-][A-Za-z0-9._/=+-]*$"

INTERPRETERS = ["python3", "bash", "pwsh", "node"]
CLIENTS = ["claude-code", "codex", "cursor"]
EVENTS = [
    "PreToolUse",
    "PostToolUse",
    "UserPromptSubmit",
    "Notification",
    "Stop",
    "SessionStart",
    "SessionEnd",
    "PreCompact",
    "SubagentStart",
    "PermissionRequest",
]

KNOWN_PLUGIN_KEYS = [
    "name",
    "version",
    "description",
    "author",
    "license",
    "keywords",
    "homepage",
    "repository",
    "commands",
    "skills",
    "hooks",
    "engines",
]

SAFE_STRING = {
    "type": "string",
    "minLength": 1,
    "maxLength": 256,
}


def script_entry() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "interpreter", "script"],
        "properties": {
            "name": {
                "type": "string",
                "minLength": 1,
                "maxLength": 64,
                "pattern": r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
            },
            "interpreter": {"type": "string", "enum": INTERPRETERS},
            "script": {
                "type": "string",
                "minLength": 1,
                "maxLength": 256,
                "pattern": SCRIPT_PATH,
            },
            "min_interpreter_version": {"type": "string", "pattern": SEMVER},
            "args": {
                "type": "array",
                "items": {"type": "string", "maxLength": 128},
                "maxItems": 16,
            },
        },
    }


def hook_entry() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "event", "interpreter", "script"],
        "properties": {
            "id": {"type": "string", "pattern": HOOK_ID},
            "event": {"type": "string", "enum": EVENTS},
            "matcher": {"type": "string", "minLength": 1, "maxLength": 128},
            "interpreter": {"type": "string", "enum": INTERPRETERS},
            "script": {
                "type": "string",
                "minLength": 1,
                "maxLength": 256,
                "pattern": SCRIPT_PATH,
            },
            "min_interpreter_version": {"type": "string", "pattern": SEMVER},
            "args": {
                "type": "array",
                "items": {"type": "string", "maxLength": 128},
                "maxItems": 16,
            },
        },
    }


def hooks_file() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["hooks"],
        "propertyNames": {
            "enum": ["schema_version", "dispatcher", "hooks"],
        },
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "dispatcher": {
                "type": "string",
                "const": "explicit-interpreter-only",
            },
            "hooks": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": {"$ref": "#/$defs/hook_entry"},
            },
        },
        "not": {"required": ["$schema"]},
    }


def engines() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["host"],
        "properties": {
            "host": {
                "type": "object",
                "additionalProperties": False,
                "required": ["min", "clients"],
                "properties": {
                    "min": {"type": "string", "pattern": SEMVER},
                    "max": {"type": "string", "pattern": SEMVER},
                    "clients": {
                        "type": "array",
                        "minItems": 1,
                        "uniqueItems": True,
                        "items": {"type": "string", "enum": CLIENTS},
                    },
                },
            }
        },
    }


def author() -> dict:
    return {
        "oneOf": [
            {"type": "string", "minLength": 1, "maxLength": 128},
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 128},
                    "email": {"type": "string", "maxLength": 128},
                    "url": {"type": "string", "maxLength": 256},
                },
            },
        ]
    }


def build_schema() -> dict:
    description = "\n".join(
        [
            "Plugin manifest contract (ARC-0078).",
            SENTINEL,
            REQUIRED_FIELDS_RULE,
            UNKNOWN_FIELD_POLICY,
            INTERPRETER_RULE,
            COMPAT_RULE,
            ZERO_HOOKS_RULE,
            NO_ADV_RULE,
            "This document is a Draft 2020-12 JSON Schema. Used as a contract "
            "it must reject the empty object, unrelated garbage, a missing "
            "required field, a script entry with no interpreter, and the "
            "recorded zero-hooks hooks.json that carries a $schema key. "
            "Unknown fields are forbidden except the x- extension prefix.",
        ]
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_URI,
        "title": "Plugin manifest contract and load-zero-hooks rejection (ARC-0078)",
        "description": description,
        "$comment": (
            f"{SENTINEL} schema_version={SCHEMA_VERSION} "
            f"contract_rel={CONTRACT_REL}. {UNKNOWN_FIELD_POLICY} "
            f"{INTERPRETER_RULE} {ZERO_HOOKS_RULE}"
        ),
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "version", "description", "engines"],
        "propertyNames": {
            "anyOf": [
                {"enum": KNOWN_PLUGIN_KEYS},
                {"pattern": X_KEY},
            ]
        },
        "patternProperties": {X_KEY: True},
        "properties": {
            "name": {
                "type": "string",
                "minLength": 1,
                "maxLength": 64,
                "pattern": PLUGIN_NAME,
            },
            "version": {"type": "string", "pattern": SEMVER},
            "description": {
                "type": "string",
                "minLength": 8,
                "maxLength": 512,
            },
            "author": author(),
            "license": {"type": "string", "minLength": 1, "maxLength": 64},
            "keywords": {
                "type": "array",
                "maxItems": 16,
                "items": {"type": "string", "minLength": 1, "maxLength": 32},
            },
            "homepage": {"type": "string", "minLength": 1, "maxLength": 256},
            "repository": {"type": "string", "minLength": 1, "maxLength": 256},
            "commands": {
                "type": "array",
                "maxItems": 64,
                "items": {"$ref": "#/$defs/script_entry"},
            },
            "skills": {
                "type": "array",
                "maxItems": 64,
                "items": {"type": "string", "minLength": 1, "maxLength": 256},
            },
            "hooks": {
                "oneOf": [
                    {"type": "string", "pattern": HOOKS_PATH},
                    {"$ref": "#/$defs/hooks_file"},
                ]
            },
            "engines": engines(),
        },
        "$defs": {
            "safe_string": SAFE_STRING,
            "script_entry": script_entry(),
            "hook_entry": hook_entry(),
            "hooks_file": hooks_file(),
            "engines": engines(),
        },
        "not": {"required": ["$schema"]},
    }
