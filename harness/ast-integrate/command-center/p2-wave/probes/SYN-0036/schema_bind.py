"""Disk-only validator for command-center/schema/reliability-weighting.schema.json.

jsonschema 4.10.3 has no referencing.Registry. A bare Draft202012Validator
follows the shim $ref over HTTPS to ast-integrate.invalid and raises
RefResolutionError. Map those $ids onto files already on this worktree.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/reliability-weighting.schema.json"
PROFILES_REL = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_REL = "platform/schema/receipt.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "SYN-0036", "state": "SUCCESS"},
)


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    shim = _load(SCHEMA_REL)
    profiles = _load(PROFILES_REL)
    receipt = _load(RECEIPT_REL)
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
        "https://ast-integrate.invalid/" + SCHEMA_REL: shim,
        "https://ast-integrate.invalid/" + PROFILES_REL: profiles,
        "https://ast-integrate.invalid/" + RECEIPT_REL: receipt,
    }
    resolver = RefResolver(base_uri=shim["$id"], referrer=shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def schema_errors(doc: dict) -> list[str]:
    out = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def error_fingerprint(errs: list[str]) -> str:
    blob = "\n".join(sorted(errs)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def garbage_accepted() -> list[str]:
    v = validator()
    hits = []
    for g in GARBAGE:
        if not list(v.iter_errors(g)):
            hits.append(str(list(g)[:2]))
    return hits


def domain(doc: dict) -> dict:
    blob = doc.get("report")
    return blob if isinstance(blob, dict) else doc
