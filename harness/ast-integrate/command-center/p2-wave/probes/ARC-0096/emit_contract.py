#!/usr/bin/env python3
"""Write command-center/phase4/contracts/ARC-0096.json (JSON Schema 2020-12)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from clauses import (  # noqa: E402
    CLAUSE_STRINGS,
    CONTRACT_ID,
    CONTRACT_REL,
    DISABLED_RULE,
    EGRESS_RULE,
    LOCAL_VS_EGRESS,
    OBSERVATION_RULE,
    OPT_IN_RULE,
    RECORDABLE_RULE,
    REDACTION_RULE,
    RETENTION_RULE,
    SCHEMA_URI,
    SCHEMA_VERSION,
    SENTINEL,
    UNIT_ID,
)

REPO = HERE.parents[3]
OUT = REPO / CONTRACT_REL

LEAK_NOT = {
    "anyOf": [
        {"pattern": "CANARY-ARC-0096"},
        {"pattern": "/home/"},
        {"pattern": "/Users/"},
        {"pattern": r"[A-Za-z]:\\Users\\"},
        {"pattern": r"[A-Za-z]:/Users/"},
        {"pattern": r"(?i)(api[_-]?key|secret|password|token)\s*[:=]"},
    ]
}

SAFE_STRING = {
    "type": "string",
    "minLength": 1,
    "maxLength": 256,
    "not": LEAK_NOT,
}

DESCRIPTION = "\n".join(
    [
        "Telemetry and privacy contract for this program.",
        SENTINEL,
        EGRESS_RULE,
        DISABLED_RULE,
        LOCAL_VS_EGRESS,
        REDACTION_RULE,
        RETENTION_RULE,
        OPT_IN_RULE,
        RECORDABLE_RULE,
        OBSERVATION_RULE,
        "This document is a Draft 2020-12 JSON Schema. Used as a contract it "
        "must reject the empty object and unrelated garbage. It validates the "
        "POST-REDACTION telemetry event that may be stored locally or sent "
        "after owner opt-in. Unknown fields are forbidden. Inputs that still "
        "contain a canary secret or an absolute home path are invalid.",
        "Upstream architecture ratification (ARC-0077) is not on disk in this "
        "worktree; the privacy rules are substrate-agnostic and do not wait "
        "on an ADV rebuild of the architecture packet.",
    ]
)


def safe_coded(pattern: str, max_len: int = 80) -> dict:
    return {
        "type": "string",
        "minLength": 1,
        "maxLength": max_len,
        "pattern": pattern,
        "not": LEAK_NOT,
    }


def contract_doc() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_URI,
        "title": "Telemetry and privacy contract (ARC-0096)",
        "description": DESCRIPTION,
        "$comment": (
            f"{SENTINEL} unit={UNIT_ID} schema_version={SCHEMA_VERSION} "
            f"contract_id={CONTRACT_ID}. {EGRESS_RULE}"
        ),
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "event_id",
            "ts",
            "unit_id",
            "contract_id",
            "event_kind",
            "outcome",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": SCHEMA_VERSION},
            "event_id": safe_coded(
                r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
                36,
            ),
            "ts": safe_coded(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$", 20),
            "unit_id": safe_coded(r"^[A-Z]{2,5}-[0-9]{4}$", 12),
            "contract_id": {"type": "string", "const": CONTRACT_ID},
            "event_kind": {
                "type": "string",
                "enum": ["probe", "lifecycle", "conformance", "heartbeat", "error"],
            },
            "outcome": {"type": "string", "enum": ["success", "fail", "skip"]},
            "phase": safe_coded(r"^[0-9A-Z]{1,8}$", 8),
            "duration_ms": {"type": "integer", "minimum": 0, "maximum": 86400000},
            "probe_id": safe_coded(r"^[A-Za-z0-9._-]{1,64}$", 64),
            "host_os_family": {"type": "string", "enum": ["linux", "windows", "darwin"]},
            "error_class": safe_coded(r"^[A-Z][A-Z0-9_-]{1,64}$", 65),
        },
        "$defs": {
            "safe_string": SAFE_STRING,
            "telemetry_event": {"$ref": "#"},
            "telemetry_policy": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "enabled",
                    "local_recording",
                    "retention_days_local",
                    "egress_requires_opt_in",
                    "schema_version",
                    "contract_id",
                ],
                "properties": {
                    "enabled": {"type": "boolean"},
                    "local_recording": {"type": "boolean"},
                    "retention_days_local": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 14,
                    },
                    "egress_requires_opt_in": {"type": "boolean", "const": True},
                    "schema_version": {"type": "string", "const": SCHEMA_VERSION},
                    "contract_id": {"type": "string", "const": CONTRACT_ID},
                },
            },
            "owner_opt_in_record": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "ts",
                    "owner",
                    "decision",
                    "scope",
                    "destination_class",
                ],
                "properties": {
                    "id": safe_coded(r"^[A-Z0-9][A-Z0-9._:-]{2,80}$", 81),
                    "ts": safe_coded(
                        r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$",
                        20,
                    ),
                    "owner": safe_coded(r"^[A-Za-z0-9._-]{1,64}$", 64),
                    "decision": {
                        "type": "string",
                        "enum": ["OPT-IN", "OPT-OUT", "REVOKED"],
                    },
                    "scope": {"type": "string", "const": "telemetry-egress"},
                    "destination_class": {
                        "type": "string",
                        "enum": ["sandbox-observer", "owner-named-collector"],
                    },
                    "sandbox_only": {"type": "boolean"},
                    "text": SAFE_STRING,
                },
            },
            "decision_log": {
                "type": "object",
                "additionalProperties": False,
                "required": ["records"],
                "properties": {
                    "records": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/owner_opt_in_record"},
                    }
                },
            },
            "normative_rules": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "egress_rule",
                    "disabled_rule",
                    "local_vs_egress",
                    "redaction_rule",
                    "retention_rule",
                    "opt_in_rule",
                    "recordable_rule",
                    "observation_rule",
                ],
                "properties": {
                    "egress_rule": {"type": "string", "const": EGRESS_RULE},
                    "disabled_rule": {"type": "string", "const": DISABLED_RULE},
                    "local_vs_egress": {"type": "string", "const": LOCAL_VS_EGRESS},
                    "redaction_rule": {"type": "string", "const": REDACTION_RULE},
                    "retention_rule": {"type": "string", "const": RETENTION_RULE},
                    "opt_in_rule": {"type": "string", "const": OPT_IN_RULE},
                    "recordable_rule": {"type": "string", "const": RECORDABLE_RULE},
                    "observation_rule": {"type": "string", "const": OBSERVATION_RULE},
                },
            },
        },
    }


def main() -> int:
    doc = contract_doc()
    jsonschema_ok = _check(doc)
    if not jsonschema_ok:
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    missing = [c for c in CLAUSE_STRINGS if c not in text]
    if missing:
        print(f"FAILED:ARC-0096 emit missing clauses {missing[:3]}")
        return 1
    if SENTINEL not in text:
        print("FAILED:ARC-0096 emit sentinel absent")
        return 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {CONTRACT_REL} bytes={len(text.encode('utf-8'))}")
    print(SENTINEL)
    return 0


def _check(doc: dict) -> bool:
    import jsonschema

    try:
        jsonschema.Draft202012Validator.check_schema(doc)
    except Exception as exc:
        print(f"FAILED:ARC-0096 check_schema {type(exc).__name__}: {exc}")
        return False
    v = jsonschema.Draft202012Validator(doc)
    garbage = (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    )
    for g in garbage:
        errs = list(v.iter_errors(g))
        if not errs:
            print(f"FAILED:ARC-0096 schema-document-vacuous on {repr(g)[:80]}")
            return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
