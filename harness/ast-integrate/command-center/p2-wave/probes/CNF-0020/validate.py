#!/usr/bin/env python3
"""Catalog flake-report validator plus the n=50 outcome-vector overlay.

The generated catalog shim (flake-report.schema.json) is generic_report: it
pins report.kind and the receipt envelope. It does not require
failures[].outcome_vector. The unit's completion sentinel does, so this module
layers a local overlay. Do not edit the generated shim.

jsonschema 4.10 on this host has no referencing `registry=` kwarg, so catalog
validation uses RefResolver over on-disk $id maps (no network).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_SCHEMA = "command-center/schema/flake-report.schema.json"
SHIM = REPO / CATALOG_SCHEMA
PROFILES = REPO / "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = REPO / "platform/schema/receipt.schema.json"

VECTOR_OVERLAY: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://ast-integrate.invalid/command-center/p2-wave/probes/CNF-0020/outcome-vector.overlay.schema.json",
    "type": "object",
    "required": ["report"],
    "properties": {
        "report": {
            "type": "object",
            "required": [
                "kind",
                "failures",
                "k_of_n_table",
                "seed",
                "sample",
                "measured_ids",
                "sampling_frame",
                "sampling_frame_sha256",
                "seed_both_states",
                "discard_control",
            ],
            "properties": {
                "kind": {"const": "flake-report"},
                "failures": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": [
                            "id",
                            "k",
                            "n",
                            "classification",
                            "interval",
                            "outcome_vector",
                        ],
                        "properties": {
                            "n": {"const": 50},
                            "outcome_vector": {
                                "type": "array",
                                "minItems": 50,
                                "maxItems": 50,
                                "items": {
                                    "type": "object",
                                    "required": ["run", "outcome"],
                                    "properties": {
                                        "run": {"type": "integer", "minimum": 1},
                                        "outcome": {"enum": ["RED", "GREEN"]},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }
    },
}

_catalog_validator: Draft202012Validator | None = None
_overlay_validator: Draft202012Validator | None = None


def flake_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain payload lives under report when the receipt envelope is present."""
    rep = doc.get("report")
    if isinstance(rep, dict) and isinstance(rep.get("failures"), list):
        return rep
    return doc


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"schema missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_validator() -> Draft202012Validator:
    global _catalog_validator
    if _catalog_validator is None:
        shim = _load(SHIM)
        profiles = _load(PROFILES)
        receipt = _load(RECEIPT)
        store = {
            str(shim.get("$id") or "https://ast-integrate.invalid/" + CATALOG_SCHEMA): shim,
            str(profiles["$id"]): profiles,
            str(receipt["$id"]): receipt,
        }
        resolver = RefResolver.from_schema(shim, store=store)
        _catalog_validator = Draft202012Validator(shim, resolver=resolver)
    return _catalog_validator


def overlay_validator() -> Draft202012Validator:
    global _overlay_validator
    if _overlay_validator is None:
        _overlay_validator = Draft202012Validator(VECTOR_OVERLAY)
    return _overlay_validator


def _fmt(err) -> str:
    loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
    return f"{loc}: {err.message}"


def catalog_errors(doc: Any) -> list[str]:
    return sorted(_fmt(e) for e in catalog_validator().iter_errors(doc))


def overlay_errors(doc: Any) -> list[str]:
    return sorted(_fmt(e) for e in overlay_validator().iter_errors(doc))


def all_errors(doc: Any) -> list[str]:
    return catalog_errors(doc) + overlay_errors(doc)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: validate.py <artifact.json>")
        return 2
    path = Path(args[0])
    if not path.is_file():
        path = REPO / args[0]
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = all_errors(doc)
    for e in errs[:20]:
        print(e)
    if errs:
        print(f"FAILED:CNF-0020-validate errors={len(errs)}")
        return 1
    print("SUCCESS:CNF-0020-validate catalog+overlay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
