"""Offline schema registry for the marketplace contracts. No network, ever.

WHY NOT REUSE ``platform/lib/schema_resolver.py`` DIRECTLY
    That module is bound to ``platform/schema/`` and the receipt substrate; its retrieval
    hook is hard-wired to one ``BASE_URI``. Marketplace-first section 4.4 says to reuse its
    CONTAINMENT idiom verbatim rather than re-derive it -- that is exactly what
    :func:`mkt.canon.ensure_within` does. This module is the same pattern applied to a
    second, disjoint schema root, and it keeps the same two rules:

      * a ``$ref`` that is not one of the local documents raises rather than being fetched;
      * an unknown schema name raises. There is no permissive fallback, because a
        validator that accepts everything is worse than no validator.

CROSS-FILE ``$ref``
    The marketplace schemas ``$ref`` each other by RELATIVE filename
    (``common.schema.json#/$defs/sha256``). ``referencing`` resolves those against the
    referring document's ``$id``, so the registry is keyed by absolute ``$id`` and the
    relative form resolves without a retrieval hook firing at all. The hook below is
    therefore a DENY-BY-DEFAULT backstop, not the normal path.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
except ImportError as exc:  # pragma: no cover - dependency presence is a setup fact
    raise ImportError(
        "mkt.schemas needs jsonschema + referencing (already required by platform/lib)"
    ) from exc

SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schema"
BASE_URI = "https://ast-integrate.invalid/platform/marketplace/schema/"
META_URL = "https://json-schema.org/draft/2020-12/schema"

#: Every contract document, by its filename stem. The list is EXPLICIT: a glob would make
#: a deleted schema look like a schema that was never required.
SCHEMA_NAMES = (
    "advisory",
    "benchmark-evidence",
    "collection",
    "common",
    "governance-policy",
    "install-receipt",
    "lint-report",
    "lockfile",
    "mirror",
    "moderation-case",
    "offline-bundle",
    "package-manifest",
    "publisher",
    "quality-score",
    "registry-index",
    "revocation",
    "sbom",
    "signature",
    "trust-policy",
)


class SchemaError(RuntimeError):
    """An unknown schema name, an unreadable document, or a refused retrieval."""


class ValidationFailed(ValueError):
    """A document did not validate. Carries every error, not just the first."""

    def __init__(self, schema_name: str, errors: list[str]) -> None:
        self.schema_name = schema_name
        self.errors = errors
        joined = "; ".join(errors[:8]) + (
            f" (+{len(errors) - 8} more)" if len(errors) > 8 else ""
        )
        super().__init__(f"{schema_name}: {len(errors)} validation error(s): {joined}")


def schema_path(name: str) -> Path:
    if name not in SCHEMA_NAMES:
        raise SchemaError(
            f"unknown marketplace schema {name!r}; known: {', '.join(SCHEMA_NAMES)}"
        )
    path = SCHEMA_ROOT / f"{name}.schema.json"
    if not path.is_file():
        raise SchemaError(f"declared schema has no file on disk: {name!r} -> {path}")
    return path


@lru_cache(maxsize=None)
def load(name: str) -> dict[str, Any]:
    return json.loads(schema_path(name).read_bytes().decode("utf-8"))


def _retrieve(uri: str) -> Resource:
    """Deny-by-default retrieval hook: local marketplace documents and the meta-schema only."""
    if uri == META_URL:
        return Resource.from_contents(
            dict(Draft202012Validator.META_SCHEMA), default_specification=DRAFT202012
        )
    if not uri.startswith(BASE_URI):
        raise SchemaError(
            f"refusing to retrieve a non-local schema uri (no network): {uri!r}"
        )
    rel = uri[len(BASE_URI) :]
    from .canon import (
        ensure_within,
    )  # local import keeps the module import graph acyclic

    target = ensure_within(SCHEMA_ROOT, rel)
    if not target.is_file():
        raise SchemaError(f"schema uri has no file on disk: {uri!r} -> {target}")
    return Resource.from_contents(
        json.loads(target.read_bytes().decode("utf-8")),
        default_specification=DRAFT202012,
    )


@lru_cache(maxsize=1)
def registry() -> Registry:
    """A ``referencing`` Registry pre-loaded with every marketplace schema, disk-only."""
    reg: Registry = Registry(retrieve=_retrieve)
    for name in SCHEMA_NAMES:
        doc = load(name)
        reg = reg.with_resource(
            doc["$id"], Resource.from_contents(doc, default_specification=DRAFT202012)
        )
    return reg


@lru_cache(maxsize=None)
def validator_for(name: str) -> Draft202012Validator:
    return Draft202012Validator(load(name), registry=registry())


def errors_for(name: str, doc: Any) -> list[str]:
    """Every validation error as ``$.path: message``, sorted for determinism."""
    out = []
    for err in validator_for(name).iter_errors(doc):
        pointer = "$" + "".join(
            f"[{p!r}]" if isinstance(p, int) else f".{p}" for p in err.absolute_path
        )
        out.append(f"{pointer}: {err.message}")
    return sorted(out)


def validate(name: str, doc: Any) -> None:
    """Raise :class:`ValidationFailed` unless ``doc`` validates against schema ``name``."""
    errs = errors_for(name, doc)
    if errs:
        raise ValidationFailed(name, errs)


def self_check() -> dict[str, Any]:
    """Assert the POSITIVE: every declared schema exists, is draft-2020-12 valid, and compiles.

    Returns counts rather than a bare boolean so a caller cannot read "no exception" as
    "all schemas checked". A guard that swallowed an error and reported ``0 checked / 0
    failing`` is the defect class this build was warned about; ``declared`` and ``checked``
    must be compared by the caller.
    """
    meta = Draft202012Validator(Draft202012Validator.META_SCHEMA)
    checked, failures = 0, []
    for name in SCHEMA_NAMES:
        doc = load(name)
        meta_errors = sorted(e.message for e in meta.iter_errors(doc))
        if meta_errors:
            failures.append({"schema": name, "meta_errors": meta_errors})
            continue
        validator_for(name)  # compiles $refs through the registry
        checked += 1
    return {"declared": len(SCHEMA_NAMES), "checked": checked, "failures": failures}
