#!/usr/bin/env python3
"""Validate rollback-contract JSON fixtures against the six typed schemas."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def unshadow_stdlib() -> None:
    cleaned: list[str] = []
    for p in sys.path:
        try:
            resolved = Path(p or ".").resolve()
        except OSError:
            cleaned.append(p)
            continue
        if resolved == REPO:
            continue
        cleaned.append(p)
    sys.path[:] = cleaned


unshadow_stdlib()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from jsonschema import Draft7Validator  # noqa: E402
from jsonschema.validators import RefResolver  # noqa: E402

from contract import RULES  # noqa: E402
from ledger import CREATION_PATHS, default_ledger  # noqa: E402

SCHEMA_DIR = HERE / "schemas"
FIXTURE_DIR = HERE / "fixtures"

SCHEMA_FILES: tuple[tuple[str, str], ...] = (
    ("creation-set", "command-center/p2-wave/probes/TST-0048/schemas/creation-set.schema.json"),
    ("preserve-set", "command-center/p2-wave/probes/TST-0048/schemas/preserve-set.schema.json"),
    ("inverse-action", "command-center/p2-wave/probes/TST-0048/schemas/inverse-action.schema.json"),
    ("backup-record", "command-center/p2-wave/probes/TST-0048/schemas/backup-record.schema.json"),
    ("proof-of-restore", "command-center/p2-wave/probes/TST-0048/schemas/proof-of-restore.schema.json"),
    ("rollback-contract", "command-center/p2-wave/probes/TST-0048/schemas/rollback-contract.schema.json"),
)

RULE_SCHEMA: dict[str, str] = {
    "R1-RESTORE-VERSION": "rollback-contract",
    "R2-RESTORE-CONFIG": "rollback-contract",
    "R3-RESTORE-DEPLOYED-TREE": "rollback-contract",
    "R4-PRESERVE-OWNER-EDITS": "preserve-set",
    "R5-PRESERVE-USER-DATA": "preserve-set",
    "R6-PRESERVE-MCP-CURATION": "preserve-set",
    "R7-PRESERVE-CREDENTIALS": "preserve-set",
    "R8-PRE-CHANGE-BACKUP": "backup-record",
    "R9-PROOF-OF-RESTORE": "proof-of-restore",
    "R10-COMPLETE-ONLY-AFTER-VERIFY": "proof-of-restore",
    "R11-INVERSE-CREATION-SET": "inverse-action",
    "R12-INVERSE-PREEXISTING": "preserve-set",
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for p in sorted(SCHEMA_DIR.glob("*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        store[p.name] = doc
        store[p.relative_to(REPO).as_posix()] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    return store


def validator_for(schema_rel: str) -> Draft7Validator:
    schema_path = REPO / schema_rel
    referrer = json.loads(schema_path.read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=schema_path.resolve().as_uri(),
        referrer=referrer,
        store=_store(),
    )
    return Draft7Validator(referrer, resolver=resolver)


def report_schema_validator() -> Draft7Validator:
    """Local floor the named probes actually read.

    Catalog output_schema is a generated $ref shim to
    https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json
    (comment: carries NO constraints of its own). Following that $ref fetches a
    non-resolving host and is an ADV rebuild circle. Do not fetch it. The six
    rollback-contract schemas under probes/TST-0048/schemas/ remain the typed
    surface this unit exercises.
    """
    local = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "tst-0048-conformance-report-local.schema.json",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "kind",
            "sentinel",
            "answer",
            "inventory",
            "both_states",
            "both_states_control",
            "contract_rules",
            "schemas_under_test",
            "real_artifact_exercises",
            "all_negatives_fired",
            "construction",
        ],
        "properties": {
            "unit_id": {"const": "TST-0048"},
            "state": {"type": "string", "minLength": 1},
            "kind": {"const": "conformance-report"},
            "sentinel": {"const": "SUCCESS:TST-0048"},
            "answer": {"type": "string", "minLength": 40},
            "inventory": {
                "type": "object",
                "required": ["zero_loss", "before", "after"],
                "properties": {
                    "zero_loss": {"const": True},
                    "before": {"type": "array", "minItems": 1},
                    "after": {"type": "array"},
                },
            },
            "both_states": {
                "type": "object",
                "required": ["detector_ok", "vacuous_suite"],
                "properties": {
                    "detector_ok": {"const": True},
                    "vacuous_suite": {"const": False},
                },
            },
            "both_states_control": {
                "type": "object",
                "required": ["fired_on_bad", "silent_on_good"],
                "properties": {
                    "fired_on_bad": {"const": True},
                    "silent_on_good": {"const": True},
                },
            },
            "contract_rules": {"type": "array", "minItems": 12},
            "schemas_under_test": {"type": "array", "minItems": 6},
            "real_artifact_exercises": {"type": "array", "minItems": 1},
            "all_negatives_fired": {"const": True},
            "construction": {
                "type": "object",
                "required": ["inverse_restricted_to_creation_set"],
                "properties": {
                    "inverse_restricted_to_creation_set": {"const": True},
                },
            },
        },
    }
    return Draft7Validator(local)


def error_list(doc: Any, schema_rel: str) -> list[str]:
    v = validator_for(schema_rel)
    out = []
    for err in sorted(v.iter_errors(doc), key=lambda e: list(e.path)):
        path = "/".join(str(x) for x in err.path) or "$"
        out.append(f"{path}: {err.message}")
    return out


def write_fixtures() -> None:
    """Materialize good and bad JSON fixtures used as real-artifact exercises."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    led = default_ledger()
    creation = {
        "paths": sorted(CREATION_PATHS),
        "disjoint_from_preserve": True,
    }
    preserve = {
        "owner_authored": sorted(led.owner_authored),
        "user_data": sorted(led.user_data),
        "mcp_curation": sorted(led.mcp),
        "credentials": sorted(led.credentials),
        "preexisting_commands_skills_settings": sorted(led.preexisting),
    }
    inverse_ok = {
        "path": "plugin.json",
        "kind": "restore-bytes",
        "in_creation_set": True,
        "backup_sha256": "a" * 64,
    }
    inverse_bad = {
        "path": "data/user-notes.txt",
        "kind": "restore-bytes",
        "in_creation_set": False,
    }
    backup_ok = {
        "recorded_before_first_write": True,
        "files": {
            "plugin.json": {"existed": True, "sha256": "a" * 64},
            "plugin-extra.json": {"existed": False, "sha256": None},
        },
    }
    backup_bad = {
        "recorded_before_first_write": False,
        "files": {"plugin.json": {"existed": True}},
    }
    proof_ok = {
        "hashes": {"plugin.json": "a" * 64},
        "all_match": True,
        "complete": True,
    }
    proof_bad = {
        "hashes": {"plugin.json": "MISMATCH"},
        "all_match": False,
        "complete": True,
    }
    plan_ok = {
        "strategy": "inverse-plan",
        "restore": [
            "previous-version",
            "previous-configuration",
            "previous-deployed-tree-installer-managed",
        ],
        "preserve": [
            "owner-authored-edits",
            "user-data",
            "mcp-enable-disable-curation",
            "credential-stores",
            "pre-existing-commands-skills-settings",
        ],
        "creation_set": creation,
        "inverse_actions": [
            inverse_ok,
            {
                "path": "plugin-extra.json",
                "kind": "unlink-created",
                "in_creation_set": True,
                "backup_sha256": None,
            },
        ],
        "backup": backup_ok,
        "verification": proof_ok,
    }
    plan_naive = {
        "strategy": "rmtree-managed-root",
        "restore": ["previous-version"],
        "preserve": [],
        "creation_set": creation,
        "inverse_actions": [inverse_bad],
        "backup": backup_bad,
        "verification": proof_bad,
    }
    files = {
        "creation-set.ok.json": creation,
        "preserve-set.ok.json": preserve,
        "inverse-action.ok.json": inverse_ok,
        "inverse-action.bad.json": inverse_bad,
        "backup-record.ok.json": backup_ok,
        "backup-record.bad.json": backup_bad,
        "proof-of-restore.ok.json": proof_ok,
        "proof-of-restore.bad.json": proof_bad,
        "rollback-contract.ok.json": plan_ok,
        "rollback-contract.bad.json": plan_naive,
    }
    for name, doc in files.items():
        (FIXTURE_DIR / name).write_text(
            json.dumps(doc, indent=2) + "\n", encoding="utf-8"
        )


def schemas_under_test() -> list[dict[str, Any]]:
    rows = []
    for sid, rel in SCHEMA_FILES:
        path = REPO / rel
        sha, size = sha256_file(path)
        rows.append(
            {
                "id": sid,
                "path": rel,
                "bytes": size,
                "sha256": sha,
                "present": path.is_file(),
            }
        )
    return rows


EXERCISES: tuple[tuple[str, str, str, bool], ...] = (
    ("rollback-contract", "rollback-contract.ok.json", "rollback-contract", True),
    ("rollback-contract", "rollback-contract.bad.json", "rollback-contract", False),
    ("inverse-action", "inverse-action.ok.json", "inverse-action", True),
    ("inverse-action", "inverse-action.bad.json", "inverse-action", False),
    ("backup-record", "backup-record.ok.json", "backup-record", True),
    ("backup-record", "backup-record.bad.json", "backup-record", False),
    ("proof-of-restore", "proof-of-restore.ok.json", "proof-of-restore", True),
    ("proof-of-restore", "proof-of-restore.bad.json", "proof-of-restore", False),
    ("preserve-set", "preserve-set.ok.json", "preserve-set", True),
    ("creation-set", "creation-set.ok.json", "creation-set", True),
)


def real_artifact_exercises() -> list[dict[str, Any]]:
    write_fixtures()
    schema_map = dict(SCHEMA_FILES)
    rows = []
    for schema_id, fixture_name, _, want_accept in EXERCISES:
        schema_rel = schema_map[schema_id]
        artifact_rel = f"command-center/p2-wave/probes/TST-0048/fixtures/{fixture_name}"
        doc = json.loads((REPO / artifact_rel).read_text(encoding="utf-8"))
        errs = error_list(doc, schema_rel)
        accepted = not errs
        if accepted != want_accept:
            raise RuntimeError(
                f"fixture polarity drift {fixture_name}: accepted={accepted} want={want_accept} errs={errs[:4]}"
            )
        rows.append(
            {
                "schema_path": schema_rel,
                "artifact_path": artifact_rel,
                "unit_id": "TST-0048",
                "error_count": len(errs),
                "accepted": accepted,
                "note": "want-accept" if want_accept else "want-reject",
            }
        )
    return rows


def contract_rule_rows(suite_negatives: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fired = {n["rule"]: n["fired_on_bad_state"] for n in suite_negatives}
    rows = []
    for rule in RULES:
        rid = rule["id"]
        rows.append(
            {
                "id": rid,
                "schema_id": RULE_SCHEMA[rid],
                "rule": rule.get("restores") or rule.get("preserves") or rule.get("requires"),
                "negative_case": rule["negative"],
                "result": "PASS" if fired.get(rid) else "FAIL",
            }
        )
    return rows
