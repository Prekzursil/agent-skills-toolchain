"""Offline validator for the catalog release-gate-report shim.

jsonschema 4.10 on this worker tries to fetch ast-integrate.invalid over
HTTPS. Map those $id URIs onto the repo files instead.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DECLARED = "command-center/schema/release-gate-report.schema.json"
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


def release_payload(doc: dict) -> dict:
    """Domain rows live in report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("conditions"), list):
        return report
    return doc


def _refuse(uri: str):
    raise ValueError(f"offline-refused {uri}")


def _store() -> dict:
    store: dict = {}
    for rel in STORE_FILES:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = doc
        store["file:///C:/Users/Prekzursil/source/ast-integrate/" + rel] = doc
        store["file:///home/prekzursil/p2-g1/" + rel] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    return store


def validator():
    store = _store()
    shim = json.loads((REPO / DECLARED).read_text(encoding="utf-8"))
    profiles = store.get(
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json"
    )
    target = shim
    if isinstance(profiles, dict):
        defs = profiles.get("$defs") or {}
        if isinstance(defs.get("release-gate-report"), dict):
            target = dict(defs["release-gate-report"])
            target["$defs"] = defs
    resolver = RefResolver(
        base_uri="https://ast-integrate.invalid/" + DECLARED,
        referrer=shim,
        store=store,
        handlers={"http": _refuse, "https": _refuse, "file": _refuse},
    )
    return Draft202012Validator(target, resolver=resolver)


def iter_errors(doc) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))
