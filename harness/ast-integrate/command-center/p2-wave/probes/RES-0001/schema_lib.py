#!/usr/bin/env python3
"""Load and validate against the RES-0001 schema family."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_DIR = REPO / "command-center" / "schema"

SCHEMA_FILES = (
    "research-claim-record.schema.json",
    "source-lineage.schema.json",
    "evidence-tier.schema.json",
    "confidence-band.schema.json",
    "settling-probe.schema.json",
    "claim-edge.schema.json",
    "freshness-stamp.schema.json",
    "snapshot-sha256.schema.json",
)

CLAIM_SCHEMA_NAME = "research-claim-record.schema.json"
ID_PREFIX = "https://ast-integrate.local/schema/"

REQUIRED_FIELDS = (
    "claim_id",
    "canonical_mechanism",
    "source_lineage",
    "evidence_tier",
    "confidence_band",
    "settling_probe",
    "contradiction_edges",
    "support_edges",
    "freshness_stamp",
    "snapshot_sha256",
)


def schema_paths() -> list[Path]:
    return [SCHEMA_DIR / name for name in SCHEMA_FILES]


def missing_schema_files() -> list[str]:
    return [p.as_posix() for p in schema_paths() if not p.is_file() or p.stat().st_size <= 0]


def load_store() -> dict[str, dict]:
    store: dict[str, dict] = {}
    for path in schema_paths():
        doc = json.loads(path.read_text(encoding="utf-8"))
        rid = str(doc.get("$id") or (ID_PREFIX + path.name))
        store[rid] = doc
        store[path.name] = doc
        store[ID_PREFIX + path.name] = doc
    return store


def claim_validator() -> Draft202012Validator:
    path = SCHEMA_DIR / CLAIM_SCHEMA_NAME
    schema = json.loads(path.read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(schema, store=load_store())
    return Draft202012Validator(schema, resolver=resolver)


def schema_errors(instance: Any, validator: Draft202012Validator | None = None) -> list[str]:
    v = validator or claim_validator()
    out: list[str] = []
    for err in v.iter_errors(instance):
        loc = ".".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def validate_claim(instance: Any, validator: Draft202012Validator | None = None) -> tuple[bool, list[str]]:
    errs = schema_errors(instance, validator)
    return len(errs) == 0, errs


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def roundtrip_bytes(obj: Any) -> tuple[bool, str, str]:
    first = canonical_dumps(obj)
    reloaded = json.loads(first)
    second = canonical_dumps(reloaded)
    return first == second, first, second
