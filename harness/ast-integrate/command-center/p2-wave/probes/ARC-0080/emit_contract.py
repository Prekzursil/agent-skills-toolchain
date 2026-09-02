#!/usr/bin/env python3
"""Write command-center/phase4/contracts/ARC-0080.json (JSON Schema 2020-12).

The file IS the schema packer.py validates reports against, plus x-normative
rules the consumer reads. A denylist packer is unrepresentable: selection_policy
is const allowlist and on_exceed is const fail.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center" / "phase4" / "contracts" / "ARC-0080.json"
SENTINEL = "SUCCESS:ARC-0080"

HARD_CEILING_BYTES = 5 * 1024 * 1024
DIGEST_ALG = "sha256"
GENERATOR_ID = "arc-0080-allowlist-packer"
GENERATOR_VERSION = "1.0.0"
EVALUATION_SURFACE = (
    "stage-walk then mandatory-exclusion then credential-needles "
    "then allowlist-select then archive-member-rescan"
)
SELECTION_POLICY = "allowlist"
ON_EXCEED = "fail"

EXCLUSION_CLASSES = {
    "git": [".git", ".git/**", "**/.git", "**/.git/**"],
    "caches": [
        "**/.cache/**",
        "**/__pycache__/**",
        "**/*.pyc",
        "**/node_modules/**",
        "**/.pytest_cache/**",
    ],
    "logs": ["**/*.log", "**/logs/**"],
    "transcripts": ["**/transcripts/**", "**/*.transcript", "**/*transcript*.jsonl"],
    "credentials": [
        "**/*.credentials",
        "**/*credential*",
        "**/.env",
        "**/.env.*",
        "**/secrets/**",
        "**/*.pem",
        "**/*.key",
    ],
}

CREDENTIAL_NEEDLES = [
    "CANARY_CREDENTIAL_ARC0080",
    "BEGIN OPENSSH PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "AWS_SECRET_ACCESS_KEY=",
]

DESCRIPTION = "\n".join(
    [
        "Package content-boundary contract (ARC-0080).",
        SENTINEL,
        "A package IS the allowlisted member set after mandatory exclusion, "
        "not the repository tree and not 'everything except a denylist'.",
        "Content boundary: selection_policy is allowlist-only. The glob '**' "
        "is forbidden; deny-by-default would collapse into shipping the tree.",
        "Mandatory exclusions (fail-loud, never silent omit): .git, caches, "
        "logs, transcripts, credentials. A planted .git directory or canary "
        "credential in the build input is excluded from members AND the build "
        "fails rather than producing an archive.",
        "Size ceiling: max_total_bytes is 1..hard_ceiling_bytes. Exceeding "
        "the ceiling fails the build (on_exceed=fail). Warn is unrepresentable. "
        "Unrelated gigabyte blobs cannot be packaged.",
        "Integrity digest is sha256 over sorted (path, content-sha256) pairs "
        "of packaged members only.",
        "Build reproducibility: sorted members, timestamps pinned to "
        "1980-01-01, generator_id+generator_version recorded, repeat digest "
        "must agree.",
        "This document is a Draft 2020-12 JSON Schema. Used as a contract it "
        "must reject the empty object, unrelated garbage, on_exceed=warn, "
        "selection_policy=denylist, and a report missing integrity.",
        "Consumer call site: command-center/p2-wave/probes/ARC-0080/packer.py.",
        "No ADV rebuild of ARC-0077 is required to freeze this substrate-agnostic "
        "package-boundary schema.",
    ]
)


def glob_item() -> dict:
    return {
        "type": "string",
        "minLength": 1,
        "maxLength": 256,
        "not": {"const": "**"},
    }


def path_item() -> dict:
    return {
        "type": "string",
        "minLength": 1,
        "maxLength": 512,
        "pattern": r"^(?!\.\./)(?!/)[A-Za-z0-9._+@=-]+(/[A-Za-z0-9._+@=-]+)*$",
    }


def sha256_hex() -> dict:
    return {
        "type": "string",
        "minLength": 64,
        "maxLength": 64,
        "pattern": r"^[a-f0-9]{64}$",
    }


def exclusion_patterns() -> dict:
    return {
        "type": "array",
        "minItems": 1,
        "maxItems": 32,
        "items": glob_item(),
        "uniqueItems": True,
    }


def build_schema() -> dict:
    member = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "path",
            "bytes",
            "sha256",
            "allowlist_glob",
            "exists_in_repository",
            "justification",
        ],
        "properties": {
            "path": path_item(),
            "bytes": {"type": "integer", "minimum": 0},
            "sha256": sha256_hex(),
            "allowlist_glob": glob_item(),
            "exists_in_repository": {"type": "boolean"},
            "justification": {"type": "string", "minLength": 8, "maxLength": 512},
        },
    }
    failure = {
        "type": "object",
        "additionalProperties": False,
        "required": ["class", "path", "message"],
        "properties": {
            "class": {
                "type": "string",
                "enum": [
                    "declaration",
                    "size_ceiling",
                    "symlink",
                    "git",
                    "caches",
                    "logs",
                    "transcripts",
                    "credentials",
                ],
            },
            "path": {"type": "string", "minLength": 1, "maxLength": 512},
            "pattern": {"type": "string", "minLength": 1, "maxLength": 256},
            "message": {"type": "string", "minLength": 8, "maxLength": 512},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.local/command-center/phase4/contracts/ARC-0080.json",
        "title": "Package metadata, content boundary and exclusion contract (ARC-0080)",
        "description": DESCRIPTION,
        "$comment": (
            f"{SENTINEL} A package is the allowlisted member set after "
            "mandatory exclusion. selection_policy=allowlist; on_exceed=fail; "
            "denylist and warn are unrepresentable."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": [
            "contract_id",
            "package_id",
            "package_version",
            "content_boundary",
            "mandatory_exclusions",
            "size_ceiling",
            "integrity",
            "reproducibility",
            "members",
            "failures",
            "verdict",
        ],
        "properties": {
            "contract_id": {"type": "string", "const": "ARC-0080"},
            "package_id": {
                "type": "string",
                "minLength": 3,
                "maxLength": 64,
                "pattern": r"^[a-z][a-z0-9-]{1,62}$",
            },
            "package_version": {
                "type": "string",
                "pattern": r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$",
            },
            "content_boundary": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "evaluation_surface",
                    "selection_policy",
                    "allowlist_globs",
                ],
                "properties": {
                    "evaluation_surface": {
                        "type": "string",
                        "const": EVALUATION_SURFACE,
                    },
                    "selection_policy": {
                        "type": "string",
                        "const": SELECTION_POLICY,
                    },
                    "allowlist_globs": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 64,
                        "items": glob_item(),
                    },
                },
            },
            "mandatory_exclusions": {
                "type": "object",
                "additionalProperties": False,
                "required": ["git", "caches", "logs", "transcripts", "credentials"],
                "properties": {
                    "git": exclusion_patterns(),
                    "caches": exclusion_patterns(),
                    "logs": exclusion_patterns(),
                    "transcripts": exclusion_patterns(),
                    "credentials": exclusion_patterns(),
                },
            },
            "size_ceiling": {
                "type": "object",
                "additionalProperties": False,
                "required": ["max_total_bytes", "on_exceed"],
                "properties": {
                    "max_total_bytes": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": HARD_CEILING_BYTES,
                    },
                    "on_exceed": {"type": "string", "const": ON_EXCEED},
                },
            },
            "integrity": {
                "type": "object",
                "additionalProperties": False,
                "required": ["algorithm", "digest", "member_count", "total_bytes"],
                "properties": {
                    "algorithm": {"type": "string", "const": DIGEST_ALG},
                    "digest": sha256_hex(),
                    "member_count": {"type": "integer", "minimum": 0},
                    "total_bytes": {"type": "integer", "minimum": 0},
                },
            },
            "reproducibility": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "declared",
                    "sorted_members",
                    "normalized_timestamps",
                    "generator_id",
                    "generator_version",
                    "repeat_digest_agrees",
                ],
                "properties": {
                    "declared": {"type": "boolean", "const": True},
                    "sorted_members": {"type": "boolean", "const": True},
                    "normalized_timestamps": {"type": "boolean", "const": True},
                    "generator_id": {"type": "string", "const": GENERATOR_ID},
                    "generator_version": {
                        "type": "string",
                        "const": GENERATOR_VERSION,
                    },
                    "repeat_digest_agrees": {"type": "boolean"},
                },
            },
            "members": {"type": "array", "items": member},
            "failures": {"type": "array", "items": failure},
            "verdict": {"type": "string", "enum": ["accept", "reject"]},
        },
        "state": "SUCCESS",
        "x-normative": {
            "contract_id": "ARC-0080",
            "evaluation_surface": EVALUATION_SURFACE,
            "selection_policy": SELECTION_POLICY,
            "on_exceed": ON_EXCEED,
            "hard_ceiling_bytes": HARD_CEILING_BYTES,
            "digest_algorithm": DIGEST_ALG,
            "generator_id": GENERATOR_ID,
            "generator_version": GENERATOR_VERSION,
            "exclusion_classes": EXCLUSION_CLASSES,
            "credential_content_needles": CREDENTIAL_NEEDLES,
            "total_wildcard_forbidden": True,
            "silent_omit_forbidden": True,
            "denylist_unrepresentable": True,
            "warn_unrepresentable": True,
        },
        "$defs": {
            "glob": glob_item(),
            "rel_path": path_item(),
            "sha256_hex": sha256_hex(),
            "member": member,
            "failure": failure,
        },
    }


def _check(doc: dict) -> bool:
    import jsonschema

    try:
        jsonschema.Draft202012Validator.check_schema(doc)
    except Exception as exc:
        print(f"FAILED:ARC-0080 check_schema {type(exc).__name__}: {exc}")
        return False
    v = jsonschema.Draft202012Validator(doc)
    garbage = (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"contract_id": "ARC-0080"},
        {"$schema": "https://json-schema.org/draft/2020-12/schema"},
    )
    for g in garbage:
        errs = list(v.iter_errors(g))
        if not errs:
            print(f"FAILED:ARC-0080 schema-document-vacuous on {repr(g)[:80]}")
            return False
    return True


def emit() -> dict:
    doc = build_schema()
    if not _check(doc):
        raise RuntimeError("ARC-0080 schema failed self-check")
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        raise RuntimeError("ARC-0080 sentinel absent from emitted text")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    return doc


def main() -> int:
    emit()
    raw = OUT.read_bytes()
    print(f"wrote command-center/phase4/contracts/ARC-0080.json bytes={len(raw)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
