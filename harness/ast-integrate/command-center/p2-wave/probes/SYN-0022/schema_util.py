"""Offline Draft7 validator for the reprobe-record shim.

command-center/schema/reprobe-record.schema.json $ref's
https://ast-integrate.invalid/... . jsonschema 4.10 tries requests.get on that
host and raises RefResolutionError. Map those $id URLs onto files already on
disk. Never fetch.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/reprobe-record.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
)


def _refuse(uri: str) -> Any:
    raise RefResolutionError(f"offline-refused {uri}")


def disk_validator(schema_path: Path | None = None) -> jsonschema.Draft7Validator:
    path = schema_path or (REPO / SCHEMA_REL)
    shim = json.loads(path.read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        str(shim.get("$id") or ""): shim,
        str(profiles.get("$id") or ""): profiles,
        str(receipt.get("$id") or ""): receipt,
        "https://ast-integrate.invalid/command-center/schema/reprobe-record.schema.json": shim,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
    }
    resolver = jsonschema.RefResolver(
        base_uri=str(shim.get("$id") or path.as_uri()),
        referrer=shim,
        store=store,
        cache_remote=False,
        handlers={"http": _refuse, "https": _refuse},
    )
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def schema_errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in disk_validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_rejected() -> tuple[bool, int]:
    validator = disk_validator()
    n = 0
    for item in GARBAGE:
        if list(validator.iter_errors(item)):
            n += 1
    return n == len(GARBAGE), n
