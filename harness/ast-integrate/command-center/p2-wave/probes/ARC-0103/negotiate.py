#!/usr/bin/env python3
"""Schema version negotiation (ARC-0103).

Version field location
  Document-root integer ``schema_version`` (JSON Pointer /schema_version).
  This is the live convention: WORK-UNIT-CATALOG.json, seed.py, catalog.py,
  unit_manifest.py, and the A2 registry all use that key. Nested or
  string-typed versions are not this field.

Compatibility rule (integer schema versions)
  producer P, consumer C:
    P == C -> ACCEPT (same schema)
    P <  C -> ACCEPT (older artifact, newer consumer: additive / previous schema)
    P >  C -> REFUSE (newer artifact, older consumer: forward-incompatible)
  Missing, non-integer, or boolean schema_version -> REFUSE.
  Adjacent-cell inference is forbidden: an untested pair is NOT-CHECKED,
  never an implied ACCEPT (ARC-0095).

Loud refusal
  Incompatible reads raise VersionRefusal. The exception carries producer
  and consumer versions plus producer vs consumer field counts. A reader
  that keeps a subset of keys and returns a partial object is the silent
  partial-read anti-pattern this unit forbids.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

VERSION_FIELD = "schema_version"
VERSION_PATH = "/schema_version"

# seed.py:188-207 return keys. That is the v1 catalog producer shape.
CATALOG_V1_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "contract",
        "provenance",
        "terminal_dispositions",
        "defaults",
        "owner_questions",
        "items",
    }
)

CATALOG_CLASS = "work-unit-catalog"
MANIFEST_CLASS = "unit-artifact-manifest"
REGISTRY_CLASS = "a2-registry"


class VersionRefusal(Exception):
    """Loud refusal: versions are incompatible. Never a partial document."""

    def __init__(
        self,
        *,
        artifact_class: str,
        producer_version: int | None,
        consumer_version: int,
        producer_fields: Iterable[str],
        consumer_fields: Iterable[str],
        reason: str,
        version_path: str = VERSION_PATH,
    ) -> None:
        self.artifact_class = artifact_class
        self.producer_version = producer_version
        self.consumer_version = consumer_version
        self.producer_fields = frozenset(producer_fields)
        self.consumer_fields = frozenset(consumer_fields)
        self.producer_field_count = len(self.producer_fields)
        self.consumer_field_count = len(self.consumer_fields)
        self.dropped_fields = tuple(sorted(self.producer_fields - self.consumer_fields))
        self.dropped_count = len(self.dropped_fields)
        self.reason = reason
        self.version_path = version_path
        super().__init__(
            f"VERSION-REFUSAL {artifact_class} producer={producer_version} "
            f"consumer={consumer_version} producer_fields={self.producer_field_count} "
            f"consumer_fields={self.consumer_field_count} dropped={self.dropped_count} "
            f"path={version_path}: {reason}"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "REFUSE",
            "loud": True,
            "artifact_class": self.artifact_class,
            "producer_version": self.producer_version,
            "consumer_version": self.consumer_version,
            "producer_field_count": self.producer_field_count,
            "consumer_field_count": self.consumer_field_count,
            "dropped_fields": list(self.dropped_fields),
            "dropped_count": self.dropped_count,
            "version_path": self.version_path,
            "reason": self.reason,
        }


def field_set(doc: Mapping[str, Any] | Any) -> frozenset[str]:
    if isinstance(doc, Mapping):
        return frozenset(str(k) for k in doc.keys())
    return frozenset()


def locate_version(doc: Any) -> tuple[str, int | None, str | None]:
    """Return (path, version, error). error is set when the field is unusable."""
    if not isinstance(doc, dict):
        return VERSION_PATH, None, f"root is {type(doc).__name__}, expected object"
    if VERSION_FIELD not in doc:
        return VERSION_PATH, None, f"{VERSION_FIELD} absent at {VERSION_PATH}"
    raw = doc[VERSION_FIELD]
    if isinstance(raw, bool) or not isinstance(raw, int):
        return (
            VERSION_PATH,
            None,
            f"{VERSION_FIELD} is {type(raw).__name__}, expected integer",
        )
    return VERSION_PATH, raw, None


def compatible(producer: int, consumer: int) -> bool:
    return producer <= consumer


def silent_partial_read(
    doc: Mapping[str, Any], consumer_fields: Iterable[str]
) -> dict[str, Any]:
    """Anti-pattern: keep known keys, drop the rest. Used only as a control."""
    keep = frozenset(consumer_fields)
    return {str(k): v for k, v in doc.items() if str(k) in keep}


def negotiate(
    doc: Any,
    consumer_version: int,
    consumer_fields: Iterable[str],
    artifact_class: str,
) -> dict[str, Any]:
    """ACCEPT a compatible artifact or raise VersionRefusal.

    On ACCEPT the full document is implied; this function does not strip keys.
    """
    path, producer, err = locate_version(doc)
    producer_fields = field_set(doc)
    consumer_set = frozenset(consumer_fields)
    if err is not None:
        raise VersionRefusal(
            artifact_class=artifact_class,
            producer_version=producer,
            consumer_version=consumer_version,
            producer_fields=producer_fields,
            consumer_fields=consumer_set,
            reason=err,
            version_path=path,
        )
    assert producer is not None
    if not compatible(producer, consumer_version):
        raise VersionRefusal(
            artifact_class=artifact_class,
            producer_version=producer,
            consumer_version=consumer_version,
            producer_fields=producer_fields,
            consumer_fields=consumer_set,
            reason=(
                f"producer schema_version {producer} is newer than consumer "
                f"{consumer_version}; a silent subset read would drop "
                f"{len(producer_fields - consumer_set)} field(s)"
            ),
            version_path=path,
        )
    return {
        "status": "ACCEPT",
        "loud": False,
        "artifact_class": artifact_class,
        "producer_version": producer,
        "consumer_version": consumer_version,
        "producer_field_count": len(producer_fields),
        "consumer_field_count": len(consumer_set),
        "dropped_fields": [],
        "dropped_count": 0,
        "version_path": path,
        "reason": (
            "compatible: producer "
            f"{producer} <= consumer {consumer_version} at {path}"
        ),
    }


def try_negotiate(
    doc: Any,
    consumer_version: int,
    consumer_fields: Iterable[str],
    artifact_class: str,
) -> dict[str, Any]:
    try:
        return negotiate(doc, consumer_version, consumer_fields, artifact_class)
    except VersionRefusal as exc:
        return exc.as_dict()


def catalog_v1_projection(catalog: Mapping[str, Any]) -> dict[str, Any]:
    """Previous-schema catalog: seed.py keys, schema_version forced to 1.

    Payload (items, contract, ...) is taken from the live v2 file, which
    work_units_meta.preserved says still carries the pre-merge backlog.
    """
    out: dict[str, Any] = {}
    for key in sorted(CATALOG_V1_KEYS):
        if key == VERSION_FIELD:
            continue
        if key in catalog:
            out[key] = catalog[key]
    out[VERSION_FIELD] = 1
    return out


def planted_incompatible() -> tuple[dict[str, Any], int, frozenset[str]]:
    """Toy pair used as a both-states control, not as the live evidence pair."""
    artifact = {
        VERSION_FIELD: 3,
        "keep": 1,
        "drop_a": "would-be-silent",
        "drop_b": ["would", "drop"],
    }
    consumer_version = 1
    consumer_fields = frozenset({VERSION_FIELD, "keep"})
    return artifact, consumer_version, consumer_fields
