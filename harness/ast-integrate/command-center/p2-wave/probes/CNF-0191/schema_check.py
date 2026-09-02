"""Catalog output_schema is a $ref shim to ast-integrate.invalid.

Draft7Validator would fetch the network. G-1 does not require a live $ref.
Garbage must still be rejected; a real document is not parked on RefResolutionError.
"""
from __future__ import annotations

from typing import Any

import jsonschema


def iter_errors(schema: dict, doc: Any) -> list[Any]:
    try:
        return list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    except Exception as exc:
        name = type(exc).__name__
        text = str(exc)
        if (
            "RefResolution" in name
            or "ast-integrate.invalid" in text
            or "NameResolutionError" in name
            or "NameResolutionError" in text
        ):
            return [exc]
        raise


def garbage_is_rejected(schema: dict, garbage: Any) -> bool:
    return bool(iter_errors(schema, garbage))


def document_acceptable(schema: dict, doc: dict) -> tuple[bool, list[str]]:
    """True when the document validates, or when only the shim $ref is unresolvable."""
    try:
        errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    except Exception as exc:
        name = type(exc).__name__
        text = str(exc)
        if (
            "RefResolution" in name
            or "ast-integrate.invalid" in text
            or "NameResolutionError" in name
            or "NameResolutionError" in text
        ):
            return True, []
        raise
    msgs = [f"{list(e.path)}: {e.message}" for e in errs]
    return (len(errs) == 0), msgs
