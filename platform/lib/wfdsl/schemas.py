"""Offline schema loading + per-profile validators.

Design notes
------------
* Every ``$id`` is resolved from disk through a :class:`referencing.Registry` whose
  ``retrieve`` callback RAISES. A schema that accidentally references an external URI
  therefore fails loudly instead of silently reaching the network (and a CI box with no
  egress would otherwise produce a different verdict than a developer box).
* Profiles are three real draft-2020-12 documents composed with ``allOf``, not flags:
  ``structural`` -> ``normative`` -> ``strict``, each strictly narrower than the last.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource
from referencing.jsonschema import DRAFT202012

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"
REPO_ROOT = Path(__file__).resolve().parents[3]

#: filename -> the $id it declares (asserted at load time so a rename cannot silently
#: orphan a $ref)
SCHEMA_FILES: dict[str, str] = {
    "work-unit.schema.json": "https://schema.ast-integrate.local/work-unit/1.0.0",
    "work-unit.normative.schema.json": "https://schema.ast-integrate.local/work-unit-normative/1.0.0",
    "work-unit.strict.schema.json": "https://schema.ast-integrate.local/work-unit-strict/1.0.0",
    "work-unit-catalog.schema.json": "https://schema.ast-integrate.local/work-unit-catalog/1.0.0",
    "workflow-dsl.schema.json": "https://schema.ast-integrate.local/workflow-dsl/1.0.0",
}

WORK_UNIT_PROFILES: dict[str, str] = {
    "structural": "https://schema.ast-integrate.local/work-unit/1.0.0",
    "normative": "https://schema.ast-integrate.local/work-unit-normative/1.0.0",
    "strict": "https://schema.ast-integrate.local/work-unit-strict/1.0.0",
}

CATALOG_ID = "https://schema.ast-integrate.local/work-unit-catalog/1.0.0"
WORKFLOW_ID = "https://schema.ast-integrate.local/workflow-dsl/1.0.0"

CAPABILITY_MAP_PATH = SCHEMA_DIR / "workflow-dsl.capability-map.json"


class SchemaLoadError(RuntimeError):
    """Raised when a schema file is missing, unparseable, or declares the wrong $id."""


@lru_cache(maxsize=1)
def load_all() -> dict[str, dict[str, Any]]:
    """Load every schema document, keyed by ``$id``. Fails loudly on any mismatch."""
    out: dict[str, dict[str, Any]] = {}
    for fname, expected_id in SCHEMA_FILES.items():
        path = SCHEMA_DIR / fname
        if not path.is_file():
            raise SchemaLoadError(f"missing schema document: {path}")
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (
            json.JSONDecodeError
        ) as exc:  # pragma: no cover - exercised by a test fixture
            raise SchemaLoadError(f"{path} is not valid JSON: {exc}") from exc
        got = doc.get("$id")
        if got != expected_id:
            raise SchemaLoadError(
                f"{path} declares $id={got!r}, expected {expected_id!r}"
            )
        out[expected_id] = doc
    return out


def _retrieve_schema(uri: str) -> Resource:  # noqa: ANN202 - referencing callback
    """Retrieve a schema from our local offline collection by URI.

    This is called when the referencing library encounters a $ref that needs resolution.
    We look up the schema in our loaded docs and return it as a Resource.
    """
    docs = load_all()
    if uri in docs:
        return Resource.from_contents(docs[uri], default_specification=DRAFT202012)
    # If not found locally, refuse the fetch
    raise NoSuchResource(
        ref=f"offline registry cannot resolve {uri!r}: not in local schema set. Known: {sorted(docs)}"
    )


@lru_cache(maxsize=1)
def registry() -> Registry:
    """A fully offline :class:`referencing.Registry` over the local schema set.

    Uses a custom retrieve function that directly looks up schemas by their $id URI
    in the local docs dictionary. When the referencing library encounters a $ref,
    it calls this function to resolve the base schema. For references with JSON
    Pointer fragments (e.g., #/$defs/tool_token), the library extracts the fragment,
    calls retrieve to get the base schema, then navigates the pointer.
    """
    return Registry(retrieve=_retrieve_schema)


@lru_cache(maxsize=None)
def validator_for(schema_id: str) -> Draft202012Validator:
    """Return a cached validator for a schema ``$id``."""
    docs = load_all()
    if schema_id not in docs:
        raise SchemaLoadError(
            f"unknown schema $id {schema_id!r}; known: {sorted(docs)}"
        )
    return Draft202012Validator(docs[schema_id], registry=registry())


def work_unit_validator(profile: str = "normative") -> Draft202012Validator:
    if profile not in WORK_UNIT_PROFILES:
        raise SchemaLoadError(
            f"unknown work-unit profile {profile!r}; known: {sorted(WORK_UNIT_PROFILES)}"
        )
    return validator_for(WORK_UNIT_PROFILES[profile])


def catalog_validator() -> Draft202012Validator:
    return validator_for(CATALOG_ID)


def workflow_validator() -> Draft202012Validator:
    return validator_for(WORKFLOW_ID)


def check_metaschema() -> dict[str, str]:
    """Validate every schema document against the draft 2020-12 metaschema.

    Returns ``{$id: "OK"}`` or raises :class:`jsonschema.exceptions.SchemaError`.
    """
    out: dict[str, str] = {}
    for schema_id, doc in load_all().items():
        Draft202012Validator.check_schema(doc)
        out[schema_id] = "OK"
    return out


def error_summary(errors: Iterable[Any], limit: int = 6) -> list[str]:
    """Compact, deterministic, human-readable error lines (sorted, deduped, capped)."""
    seen: list[str] = []
    for err in errors:
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        kw = err.validator
        msg = err.message
        if len(msg) > 220:
            msg = msg[:217] + "..."
        line = f"{loc}: [{kw}] {msg}"
        if line not in seen:
            seen.append(line)
        if len(seen) >= limit:
            break
    return seen


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
