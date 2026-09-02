#!/usr/bin/env python3
"""Write the twelve fixture JSON Schema contracts for ARC-0105.

These are stand-ins for command-center/phase4/contracts/ARC-0078.json …
ARC-0089.json. They exist only under probes/ARC-0105/fixtures/ so the
checker can be proven without claiming those contract units delivered.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "fixtures" / "contracts"

ART_ID = "^ART-[0-9]{4}$"
UNIT_ID = "^[A-Z]{2,5}-[0-9]{4}$"
DIGEST = "^sha256:[0-9a-f]{64}$"
SCHEMA_REF = "^[A-Za-z0-9._/-]+\\.schema\\.json$"


def schema(uid: str, title: str, defs: dict, properties: dict, required: list[str] | None = None) -> dict:
    doc: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{uid}.json",
        "title": title,
        "type": "object",
        "x-contract-id": uid,
        "$defs": defs,
        "properties": properties,
        "additionalProperties": True,
    }
    if required:
        doc["required"] = required
    return doc


def dump(uid: str, doc: dict) -> None:
    path = OUT / f"{uid}.json"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    dump(
        "ARC-0078",
        schema(
            "ARC-0078",
            "Plugin manifest contract",
            {"pluginId": {"type": "string", "pattern": "^plugin:[a-z0-9][a-z0-9.-]*$"}},
            {"id": {"$ref": "#/$defs/pluginId"}},
            ["id"],
        ),
    )
    dump(
        "ARC-0079",
        schema(
            "ARC-0079",
            "Marketplace registry entry contract",
            {"marketplaceEntryId": {"type": "string", "pattern": "^mp:[a-z0-9][a-z0-9.-]*$"}},
            {
                "id": {"$ref": "#/$defs/marketplaceEntryId"},
                "package_digest": {
                    "$ref": "ARC-0080.json#/$defs/packageDigest",
                    "x-refers-to": {
                        "contract": "ARC-0080",
                        "def": "packageDigest",
                        "kind": "package_digest",
                    },
                },
            },
            ["id", "package_digest"],
        ),
    )
    dump(
        "ARC-0080",
        schema(
            "ARC-0080",
            "Package content-boundary contract",
            {"packageDigest": {"type": "string", "pattern": DIGEST}},
            {"digest": {"$ref": "#/$defs/packageDigest"}},
            ["digest"],
        ),
    )
    dump(
        "ARC-0081",
        schema(
            "ARC-0081",
            "Permission vocabulary contract",
            {"permissionId": {"type": "string", "pattern": "^perm:[a-z][a-z0-9._-]*$"}},
            {"id": {"$ref": "#/$defs/permissionId"}},
            ["id"],
        ),
    )
    dump(
        "ARC-0082",
        schema(
            "ARC-0082",
            "Workflow DSL contract",
            {"workflowId": {"type": "string", "pattern": "^wf:[a-z0-9][a-z0-9.-]*$"}},
            {"id": {"$ref": "#/$defs/workflowId"}},
            ["id"],
        ),
    )
    dump(
        "ARC-0083",
        schema(
            "ARC-0083",
            "Work-unit schema contract",
            {"workUnitId": {"type": "string", "pattern": UNIT_ID}},
            {"id": {"$ref": "#/$defs/workUnitId"}},
            ["id"],
        ),
    )
    dump(
        "ARC-0084",
        schema(
            "ARC-0084",
            "Artifact envelope contract",
            {
                "artifactId": {"type": "string", "pattern": ART_ID},
                "schemaRef": {"type": "string", "pattern": SCHEMA_REF},
            },
            {
                "id": {"$ref": "#/$defs/artifactId"},
                "schema_ref": {"$ref": "#/$defs/schemaRef"},
            },
            ["id", "schema_ref"],
        ),
    )
    dump(
        "ARC-0085",
        schema(
            "ARC-0085",
            "Claim record contract",
            {"claimId": {"type": "string", "pattern": "^CLM-[0-9]{4}$"}},
            {
                "id": {"$ref": "#/$defs/claimId"},
                "artifact_id": {
                    "$ref": "ARC-0084.json#/$defs/artifactId",
                    "x-refers-to": {
                        "contract": "ARC-0084",
                        "def": "artifactId",
                        "kind": "artifact_id",
                    },
                },
            },
            ["id", "artifact_id"],
        ),
    )
    dump(
        "ARC-0086",
        schema(
            "ARC-0086",
            "Append-only event contract",
            {"eventId": {"type": "string", "pattern": "^EVT-[0-9]{6}$"}},
            {
                "id": {"$ref": "#/$defs/eventId"},
                "unit_id": {
                    "$ref": "ARC-0083.json#/$defs/workUnitId",
                    "x-refers-to": {
                        "contract": "ARC-0083",
                        "def": "workUnitId",
                        "kind": "work_unit_id",
                    },
                },
            },
            ["id", "unit_id"],
        ),
    )
    dump(
        "ARC-0087",
        schema(
            "ARC-0087",
            "Completion predicate contract",
            {"predicateId": {"type": "string", "pattern": "^PRED-[0-9]{2}$"}},
            {
                "id": {"$ref": "#/$defs/predicateId"},
                "artifact_schema": {
                    "$ref": "ARC-0084.json#/$defs/schemaRef",
                    "x-refers-to": {
                        "contract": "ARC-0084",
                        "def": "schemaRef",
                        "kind": "artifact_schema",
                    },
                },
            },
            ["id", "artifact_schema"],
        ),
    )
    dump(
        "ARC-0088",
        schema(
            "ARC-0088",
            "Hook contract",
            {"hookId": {"type": "string", "pattern": "^hook:[a-z][a-z0-9._-]*$"}},
            {"id": {"$ref": "#/$defs/hookId"}},
            ["id"],
        ),
    )
    dump(
        "ARC-0089",
        schema(
            "ARC-0089",
            "Skill contract",
            {"skillId": {"type": "string", "pattern": "^skill:[a-z][a-z0-9._-]*$"}},
            {"id": {"$ref": "#/$defs/skillId"}},
            ["id"],
        ),
    )
    print(f"wrote {len(list(OUT.glob('ARC-*.json')))} fixture contracts to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
