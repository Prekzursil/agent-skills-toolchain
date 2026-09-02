#!/usr/bin/env python3
"""Emit command-center/phase4/contracts/ARC-0094.json (Draft 2020-12 schema)."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/phase4/contracts/ARC-0094.json"

SHA = {"type": "string", "pattern": "^[a-f0-9]{64}$"}
NEVER_ITEM = {
    "type": "object",
    "additionalProperties": False,
    "required": ["class", "must_not_destroy"],
    "properties": {
        "class": {
            "type": "string",
            "enum": [
                "owner_authored_edits",
                "user_data",
                "curated_mcp_enable_disable_state",
                "credential_stores",
            ],
        },
        "must_not_destroy": {"const": True},
    },
}
PATH_HASH = {
    "type": "object",
    "additionalProperties": False,
    "required": ["path", "sha256", "role"],
    "properties": {
        "path": {"type": "string", "minLength": 1},
        "sha256": SHA,
        "role": {
            "type": "string",
            "enum": [
                "previous_version",
                "previous_configuration",
                "previous_deployed_tree_state",
                "owner_authored_edits",
                "user_data",
                "curated_mcp_enable_disable_state",
                "credential_stores",
            ],
        },
    },
}
PATH_PROOF = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "path",
        "role",
        "pre_change_sha256",
        "post_rollback_sha256",
        "matched",
    ],
    "properties": {
        "path": {"type": "string", "minLength": 1},
        "role": {
            "type": "string",
            "enum": [
                "previous_version",
                "previous_configuration",
                "previous_deployed_tree_state",
                "owner_authored_edits",
                "user_data",
                "curated_mcp_enable_disable_state",
                "credential_stores",
                "unknown",
            ],
        },
        "pre_change_sha256": SHA,
        "post_rollback_sha256": SHA,
        "matched": {"type": "boolean"},
    },
}

SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://ast-integrate.invalid/command-center/phase4/contracts/ARC-0094.json",
    "title": "Rollback contract: what must be restored and what must never be destroyed",
    "$comment": "SUCCESS:ARC-0094 — Phase 4 formal contract. Completion sentinel is this token.",
    "description": (
        "SUCCESS:ARC-0094. A rollback MUST restore previous version, previous "
        "configuration, and previous deployed tree state from a pre-change backup. "
        "A rollback MUST NEVER destroy owner-authored edits, user data, the curated "
        "MCP enable/disable state, or credential stores. Pre-change backup is "
        "mandatory: every protected path is captured with a content hash BEFORE "
        "mutation. Proof-of-restore compares those hashes to post-rollback bytes "
        "per protected path; rollback is not complete until that verification "
        "passes. A rollback whose tree-sync plan would delete an owner-authored "
        "file (proven with a planted owner file absent from the backup) is "
        "REFUSED, applies no mutations, and cannot be marked complete. Rolling "
        "back twice MUST NOT change the result of the first rollback. This schema "
        "is the consumer call site contract: a rollback record is valid only when "
        "it carries those obligations, the backup, the per-path proofs, and an "
        "honest completeness bit."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_id",
        "restore_obligations",
        "never_destroy",
        "pre_change_backup",
        "post_restore_verification",
        "complete",
        "outcome",
        "destruction_control",
        "idempotence",
        "reason",
    ],
    "properties": {
        "contract_id": {"const": "ARC-0094"},
        "restore_obligations": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "previous_version",
                "previous_configuration",
                "previous_deployed_tree_state",
            ],
            "properties": {
                "previous_version": {"const": True},
                "previous_configuration": {"const": True},
                "previous_deployed_tree_state": {"const": True},
            },
        },
        "never_destroy": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "owner_authored_edits",
                "user_data",
                "curated_mcp_enable_disable_state",
                "credential_stores",
            ],
            "properties": {
                "owner_authored_edits": NEVER_ITEM,
                "user_data": NEVER_ITEM,
                "curated_mcp_enable_disable_state": NEVER_ITEM,
                "credential_stores": NEVER_ITEM,
            },
        },
        "pre_change_backup": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "backup_id",
                "captured_before_mutation",
                "protected_path_hashes",
            ],
            "properties": {
                "backup_id": {"type": "string", "minLength": 8},
                "captured_before_mutation": {"const": True},
                "protected_path_hashes": {
                    "type": "array",
                    "minItems": 1,
                    "items": PATH_HASH,
                },
            },
        },
        "post_restore_verification": {
            "type": "object",
            "additionalProperties": False,
            "required": ["method", "passed", "path_proofs"],
            "properties": {
                "method": {"const": "content_hash_per_protected_path"},
                "passed": {"type": "boolean"},
                "path_proofs": {
                    "type": "array",
                    "minItems": 1,
                    "items": PATH_PROOF,
                },
            },
        },
        "complete": {"type": "boolean"},
        "outcome": {
            "type": "string",
            "enum": [
                "COMPLETE",
                "REFUSED_WOULD_DESTROY_OWNER_AUTHORED",
                "INCOMPLETE_VERIFICATION_FAILED",
                "MISSING_BACKUP",
            ],
        },
        "destruction_control": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "would_destroy_owner_authored",
                "owner_paths_that_would_be_deleted",
                "owner_file_still_present",
                "mutations_applied",
            ],
            "properties": {
                "would_destroy_owner_authored": {"type": "boolean"},
                "owner_paths_that_would_be_deleted": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "owner_file_still_present": {"type": "boolean"},
                "mutations_applied": {"type": "boolean"},
            },
        },
        "idempotence": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "second_pass_digest_equals_first",
                "first_tree_digest",
                "second_tree_digest",
            ],
            "properties": {
                "second_pass_digest_equals_first": {"type": "boolean"},
                "first_tree_digest": SHA,
                "second_tree_digest": SHA,
            },
        },
        "reason": {"type": "string", "minLength": 8},
    },
    "allOf": [
        {
            "if": {"properties": {"complete": {"const": True}}, "required": ["complete"]},
            "then": {
                "properties": {
                    "outcome": {"const": "COMPLETE"},
                    "post_restore_verification": {
                        "properties": {"passed": {"const": True}},
                        "required": ["passed"],
                    },
                    "destruction_control": {
                        "properties": {
                            "would_destroy_owner_authored": {"const": False},
                            "mutations_applied": {"const": True},
                        },
                        "required": [
                            "would_destroy_owner_authored",
                            "mutations_applied",
                        ],
                    },
                    "idempotence": {
                        "properties": {
                            "second_pass_digest_equals_first": {"const": True}
                        },
                        "required": ["second_pass_digest_equals_first"],
                    },
                },
                "required": ["outcome", "post_restore_verification", "destruction_control", "idempotence"],
            },
        },
        {
            "if": {
                "properties": {
                    "destruction_control": {
                        "properties": {"would_destroy_owner_authored": {"const": True}},
                        "required": ["would_destroy_owner_authored"],
                    }
                },
                "required": ["destruction_control"],
            },
            "then": {
                "properties": {
                    "complete": {"const": False},
                    "outcome": {"const": "REFUSED_WOULD_DESTROY_OWNER_AUTHORED"},
                    "destruction_control": {
                        "properties": {
                            "owner_file_still_present": {"const": True},
                            "mutations_applied": {"const": False},
                        },
                        "required": [
                            "owner_file_still_present",
                            "mutations_applied",
                        ],
                    },
                },
                "required": ["complete", "outcome", "destruction_control"],
            },
        },
    ],
}


def load_schema() -> dict:
    return SCHEMA


def write_schema() -> Path:
    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(SCHEMA, indent=2) + "\n", encoding="utf-8")
    return dest


def main() -> int:
    try:
        Draft202012Validator.check_schema(SCHEMA)
    except SchemaError as exc:
        print(f"FAILED:ARC-0094 schema check_schema: {exc}")
        return 1
    path = write_schema()
    print(f"wrote {OUT_REL} bytes={path.stat().st_size}")
    print("SUCCESS:ARC-0094 contract schema emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
