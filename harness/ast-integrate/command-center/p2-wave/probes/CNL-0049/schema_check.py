#!/usr/bin/env python3
"""Disk-local validator for command-center/schema/council-detector-spec.schema.json.

The catalog shim $ref points at https://ast-integrate.invalid/... . A bare
jsonschema.Draft7Validator tries the network and raises RefResolutionError, so
garbage rejection and artifact acceptance both crash. This module maps those
$ids onto files under the repo and never fetches.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM_REL = "command-center/schema/council-detector-spec.schema.json"
PROF_REL = "platform/schema/artifact-class-profiles.schema.json"
REC_REL = "platform/schema/receipt.schema.json"
BASE = "https://ast-integrate.invalid/"


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    shim = _load(SHIM_REL)
    store = {
        BASE + PROF_REL: _load(PROF_REL),
        BASE + REC_REL: _load(REC_REL),
        BASE + SHIM_REL: shim,
    }
    resolver = RefResolver(base_uri=BASE + SHIM_REL, referrer=shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def both_states_of(artifact: dict[str, Any]) -> dict[str, Any]:
    """Read both-states from receipt-core or the legacy top-level shape."""
    if not isinstance(artifact, dict):
        return {}
    for blob in (
        artifact.get("both_states"),
        (artifact.get("report") or {}).get("both_states")
        if isinstance(artifact.get("report"), dict)
        else None,
        (artifact.get("extensions") or {}).get("both_states")
        if isinstance(artifact.get("extensions"), dict)
        else None,
    ):
        if isinstance(blob, dict) and blob:
            return blob
    ncs = artifact.get("negative_controls")
    if isinstance(ncs, list) and ncs:
        fired = all(
            isinstance(c, dict) and c.get("fired_on_bad_state") is True for c in ncs
        )
        silent = all(
            isinstance(c, dict) and c.get("silent_on_good_state") is True for c in ncs
        )
        return {"fired_on_bad": fired, "silent_on_good": silent}
    return {}
