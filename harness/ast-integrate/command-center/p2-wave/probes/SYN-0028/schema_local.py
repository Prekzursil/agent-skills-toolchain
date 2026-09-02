"""Offline validator for the catalog option-closure shim.

jsonschema 4.10 on this worker tries to fetch ast-integrate.invalid over
HTTPS. Map those $id URIs onto the repo files instead.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DECLARED = "command-center/schema/option-closure.schema.json"
STORE_FILES = (
    DECLARED,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain rows live in report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "option-closure" or "dispositions" in report
    ):
        return report
    return doc


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in STORE_FILES:
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = data
        ident = data.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = data
    return store


def validator():
    shim = json.loads((REPO / DECLARED).read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(shim.get("$id") or ("https://ast-integrate.invalid/" + DECLARED)),
        referrer=shim,
        store=_store(),
    )
    return Draft202012Validator(shim, resolver=resolver)


def iter_errors(doc: object) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))


def errors_for(doc: object) -> list[str]:
    out: list[str] = []
    for err in iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out
