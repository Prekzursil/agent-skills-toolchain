"""Offline validation of the BLD-0026 catalog contract (no network $ref)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/blindspot-register.schema.json"
BASE = "https://ast-integrate.invalid/"
GARBAGE = [
    ("empty-object", {}),
    ("unrelated-passing-tests", {"passing_tests": 999999, "totally": "unrelated"}),
    ("two-thousand-x", {"blob": "x" * 2000}),
]


def _no_network(uri: str) -> None:
    raise RuntimeError(f"refusing network schema fetch: {uri}")


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    roots = [
        REPO / "platform" / "schema",
        REPO / "command-center" / "schema",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            rel = path.resolve().relative_to(REPO).as_posix()
            store[rel] = doc
            store[BASE + rel] = doc
            store[path.resolve().as_uri()] = doc
            sid = doc.get("$id")
            if isinstance(sid, str) and sid:
                store[sid] = doc
    return store


def validator() -> Draft202012Validator:
    schema_path = REPO / SCHEMA_REL
    referrer = json.loads(schema_path.read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(referrer.get("$id") or (BASE + SCHEMA_REL)),
        referrer=referrer,
        store=_store(),
        handlers={"http": _no_network, "https": _no_network},
    )
    return Draft202012Validator(referrer, resolver=resolver)


def validate_doc(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def schema_rejects_garbage() -> dict:
    rows = []
    for name, payload in GARBAGE:
        errs = validate_doc(payload)
        rows.append({"name": name, "rejected": bool(errs), "n_errors": len(errs)})
    if not all(r["rejected"] for r in rows):
        raise AssertionError(f"schema failed to reject garbage: {rows}")
    return {"probes": rows, "all_rejected": True}


def register_entries(doc: dict) -> list:
    if isinstance(doc.get("entries"), list):
        return doc["entries"]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    for candidate in (report.get("entries"), ext.get("entries")):
        if isinstance(candidate, list):
            return candidate
    return []
