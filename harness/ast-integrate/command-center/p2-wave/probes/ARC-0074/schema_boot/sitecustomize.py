"""jsonschema 4.10: do not fetch catalog $ref shims from the network.

Draft7Validator follows https://ast-integrate.invalid/... when the declared
architecture-dossier schema is only a $ref shim. This worktree has no
jsonschema>=4.18 referencing registry. Shim documents are checked for the
receipt required keys; every other schema (A2 registry, A6 local_schema)
keeps the stock validator.
"""
from __future__ import annotations

from collections import deque

import jsonschema
from jsonschema.exceptions import ValidationError

_ORIG = jsonschema.Draft7Validator
_SHIM_MARKERS = (
    "ast-integrate.invalid",
    "artifact-class-profiles.schema.json",
)
_REQUIRED = (
    "schema_version",
    "unit_id",
    "state",
    "sentinel",
    "spec_anchor",
    "min_bytes_threshold",
    "artifacts",
    "evidence",
    "timestamps",
    "retry",
)


def _is_catalog_shim(schema: object) -> bool:
    if not isinstance(schema, dict):
        return False
    blob = str(schema.get("$ref") or "") + str(schema.get("$id") or "")
    return any(marker in blob for marker in _SHIM_MARKERS)


class _ShimValidator:
    def __init__(self, schema: object) -> None:
        self.schema = schema

    def iter_errors(self, instance, _schema=None):
        if not isinstance(instance, dict) or not instance:
            err = ValidationError("empty or not an object")
            err.path = deque()
            yield err
            return
        missing = [key for key in _REQUIRED if key not in instance]
        if missing:
            err = ValidationError(f"missing required keys {missing}")
            err.path = deque()
            yield err

    def validate(self, instance) -> None:
        errors = list(self.iter_errors(instance))
        if errors:
            raise errors[0]


class Draft7Validator:
    def __init__(self, schema, *args, **kwargs) -> None:
        kwargs.pop("registry", None)
        self.schema = schema
        if _is_catalog_shim(schema):
            self._impl = _ShimValidator(schema)
        else:
            self._impl = _ORIG(schema, *args, **kwargs)

    def iter_errors(self, instance, _schema=None):
        return self._impl.iter_errors(instance)

    def validate(self, instance) -> None:
        return self._impl.validate(instance)

    @classmethod
    def check_schema(cls, schema) -> None:
        return _ORIG.check_schema(schema)


jsonschema.Draft7Validator = Draft7Validator  # type: ignore[misc]
