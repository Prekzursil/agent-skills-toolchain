"""Offline jsonschema for ADV-0050 license-and-rights-record receipts.

jsonschema 4.10.3 follows $ref by fetching https://ast-integrate.invalid/...
which does not resolve. Map those $id URIs onto repo files via RefResolver.
Network retrieve is refused.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/license-and-rights-record.schema.json"
BASE = "https://ast-integrate.invalid/"
DISK_SCHEMAS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _disk_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in DISK_SCHEMAS:
        data = _load(rel)
        store[BASE + rel.replace("\\", "/")] = data
        ident = data.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = data
    return store


def validator():
    from jsonschema import Draft202012Validator, RefResolver

    shim = _load(SCHEMA_REL)
    store = _disk_store()

    def retrieve(uri: str) -> dict[str, Any]:
        import jsonschema

        key = uri.split("#", 1)[0]
        if key in store:
            return store[key]
        if key.startswith(BASE):
            rel = key[len(BASE) :]
            path = REPO / rel
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                store[key] = data
                return data
        raise jsonschema.exceptions.RefResolutionError(
            f"refusing network retrieve for {uri!r}"
        )

    resolver = RefResolver(
        base_uri=str(shim.get("$id") or BASE + SCHEMA_REL),
        referrer=shim,
        store=store,
        handlers={"https": retrieve, "http": retrieve},
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


def validate(doc: object) -> tuple[bool, str]:
    errs = errors_for(doc)
    if errs:
        return False, errs[0]
    return True, "ok"


def rejects_garbage() -> bool:
    garbage = [
        {},
        {"hello": "world"},
        {"unit_id": "ADV-0050", "state": "SUCCESS"},
        {"unit_id": "nope", "state": "SUCCESS", "sentinel": "x" * 20},
        {
            "schema_version": 1,
            "unit_id": "ADV-0050",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:ADV-0050",
            "spec_anchor": "_USER-PROMPTS.md:10858",
            "min_bytes_threshold": 1024,
            "artifacts": [{"path": "x", "bytes": 1, "sha256": "0" * 64, "exists": True}],
            "evidence": [
                {
                    "claim": "x",
                    "verdict": "NOT-CHECKED",
                    "anchor": "x",
                    "probes": [
                        {
                            "role": "source",
                            "method": "other",
                            "command": "x",
                            "raw_output": "x",
                            "fingerprint": "x",
                        }
                    ],
                }
            ],
            "timestamps": {
                "started_at": "2026-08-25T00:00:00Z",
                "ended_at": "2026-08-25T00:00:01Z",
            },
            "retry": {"count": 0, "policy": "two strikes then pivot"},
        },
    ]
    return all(errors_for(g) for g in garbage)
