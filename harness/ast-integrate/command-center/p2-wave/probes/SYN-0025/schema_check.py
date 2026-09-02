"""Disk-only validator for the catalog injection-defence-report $ref shim.

Bare jsonschema.Draft7Validator follows https://ast-integrate.invalid/ over
the network and raises. This tree's jsonschema 4.10 takes RefResolver, not
registry=. Do not regenerate the generated shim; resolve it from disk.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/injection-defence-report.schema.json"
BASE = "https://ast-integrate.invalid/"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 200},
)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _store() -> dict:
    out: dict = {}
    for rel in STORE_RELS:
        body = _load(rel)
        sid = body.get("$id")
        if isinstance(sid, str) and sid:
            out[sid] = body
        out[BASE + rel] = body
    return out


def _retrieve(uri: str) -> dict:
    if uri.startswith(BASE):
        rel = uri[len(BASE) :].split("#", 1)[0]
        path = REPO / rel
        if path.is_file():
            return _load(rel)
    raise ValueError(f"non-local schema uri: {uri}")


def validator() -> Draft202012Validator:
    schema = _load(SCHEMA_REL)
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (BASE + SCHEMA_REL)),
        referrer=schema,
        store=_store(),
        handlers={"https": _retrieve},
    )
    return Draft202012Validator(schema, resolver=resolver)


def errors(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def rejects_garbage() -> tuple[bool, list[str]]:
    notes: list[str] = []
    rejected = 0
    for i, g in enumerate(GARBAGE):
        errs = errors(g)
        if errs:
            rejected += 1
            notes.append(f"garbage[{i}] rejected:{errs[0][:120]}")
        else:
            notes.append(f"garbage[{i}] ACCEPTED")
    return rejected == len(GARBAGE), notes


def domain(doc: dict) -> dict:
    """Lab fields live under report when the receipt is schema-valid."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "injection-defence-report"
        or "planted_injections" in report
        or "differential" in report
    ):
        return report
    return doc
