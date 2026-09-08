"""IMP-0006 / IMP-0009: validate `.claude-plugin/plugin.json` against its JSON Schema.

Two independent JSON-Schema libraries must agree on the same file:

* ``jsonschema.Draft202012Validator`` (primary / wire-up)
* ``fastjsonschema`` (second implementation — different code path)

IMP-0009 adds a case-distinct JSON key collision guard at parse time via
``object_pairs_hook``. Schema alone cannot see duplicate / case-folded keys.
A plain ``dict`` load is not a second signal for exact duplicates (it collapses
them); pair extraction is.

The schema lives at ``.claude-plugin/plugin.schema.json`` (materialised from
``platform/plugin/schemas.py``). This module does **not** introduce a second
manifest file; it only validates the existing control plane.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_RELPATH = ".claude-plugin/plugin.schema.json"
MANIFEST_RELPATH = ".claude-plugin/plugin.json"
DISPATCH_MANIFEST_RELPATH = "hooks/_dispatch/manifest.json"

# Distinct error codes for the six negative-control mutants (catalog IMP-0006).
ERR_MISSING_NAME = "missing-name"
ERR_BAD_SEMVER = "bad-semver"
ERR_UNKNOWN_TOP_LEVEL = "unknown-top-level-key"
ERR_WRONG_TYPE = "wrong-type"
ERR_EMPTY_KEYWORDS = "empty-keywords"
ERR_DUPLICATE_KEY = "duplicate-key"
# IMP-0009: keys that differ only by case (case-insensitive downstream collapse).
ERR_CASE_COLLISION = "case-collision"
ERR_SCHEMA = "schema-invalid"
ERR_OTHER = "other"


class ManifestSchemaError(ValueError):
    """Raised when a manifest fails parse or schema validation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class Verdict:
    """Shared two-library verdict for one instance."""

    ok: bool
    library: str
    error_code: str | None = None
    message: str | None = None


def repo_root_from(start: Path | None = None) -> Path:
    """Walk up from *start* (or this file) until ``.claude-plugin/plugin.json`` exists."""
    cur = (start or Path(__file__).resolve()).resolve()
    if cur.is_file():
        cur = cur.parent
    for candidate in (cur, *cur.parents):
        if (candidate / MANIFEST_RELPATH).is_file():
            return candidate
    raise FileNotFoundError(f"cannot locate {MANIFEST_RELPATH} above {cur}")


def load_schema(repo: Path | None = None) -> dict[str, Any]:
    root = repo or repo_root_from()
    path = root / SCHEMA_RELPATH
    return json.loads(path.read_text(encoding="utf-8"))


def _duplicate_key_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject exact duplicate keys and case-distinct collisions (IMP-0006 / IMP-0009)."""
    exact: set[str] = set()
    folded: dict[str, str] = {}
    for key, _ in pairs:
        if key in exact:
            raise ManifestSchemaError(
                ERR_DUPLICATE_KEY,
                f"duplicate object key {key!r} (also seen earlier in the same object)",
            )
        low = key.casefold()
        if low in folded and folded[low] != key:
            raise ManifestSchemaError(
                ERR_CASE_COLLISION,
                f"case-distinct duplicate keys {folded[low]!r} and {key!r}",
            )
        exact.add(key)
        folded[low] = key
    return dict(pairs)


def extract_object_key_occurrences(raw: str) -> list[list[str]]:
    """Return every object's key list (innermost first, outermost last).

    Uses ``json.loads(..., object_pairs_hook=...)`` so duplicate / case-distinct
    keys are preserved in the occurrence lists. A naive ``dict`` load of an
    *exact* duplicate key pair destroys that evidence before any check runs.
    """
    occurrences: list[list[str]] = []

    def _capture(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        occurrences.append([key for key, _ in pairs])
        # Collapse for nested structure only AFTER recording every key occurrence.
        return {key: value for key, value in pairs}

    try:
        json.loads(raw, object_pairs_hook=_capture)
    except json.JSONDecodeError as exc:
        raise ManifestSchemaError(ERR_OTHER, f"manifest is not valid JSON: {exc}") from exc
    return occurrences


def top_level_key_occurrences(raw: str) -> list[str]:
    """Outer-object key occurrences in source order (duplicates preserved)."""
    occ = extract_object_key_occurrences(raw)
    if not occ:
        return []
    return occ[-1]


def find_case_collisions(keys: list[str]) -> list[tuple[str, str]]:
    """Return (first, second) pairs of keys that differ only by case."""
    folded: dict[str, str] = {}
    hits: list[tuple[str, str]] = []
    for key in keys:
        low = key.casefold()
        if low in folded and folded[low] != key:
            hits.append((folded[low], key))
        else:
            folded[low] = key
    return hits


def find_exact_duplicate_keys(keys: list[str]) -> list[str]:
    """Return keys that appear more than once (exact string match)."""
    seen: set[str] = set()
    dups: list[str] = []
    for key in keys:
        if key in seen and key not in dups:
            dups.append(key)
        seen.add(key)
    return dups


def lint_json_text_for_key_collisions(raw: str) -> None:
    """Fail closed if any object has exact-duplicate or case-distinct keys.

    Shared SSOT with ``parse_manifest_text`` (same ``object_pairs_hook``).
    """
    parse_manifest_text(raw)


def parse_manifest_text(raw: str) -> dict[str, Any]:
    """Parse JSON with duplicate-key / case-collision rejection."""
    try:
        doc = json.loads(raw, object_pairs_hook=_duplicate_key_hook)
    except ManifestSchemaError:
        raise
    except json.JSONDecodeError as exc:
        raise ManifestSchemaError(ERR_OTHER, f"manifest is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise ManifestSchemaError(ERR_WRONG_TYPE, "manifest root must be an object")
    return doc


def load_manifest(path: Path) -> dict[str, Any]:
    return parse_manifest_text(path.read_text(encoding="utf-8"))


def assert_path_free_of_key_collisions(path: Path) -> None:
    """Parse *path* with the collision guard (plugin.json or dispatch manifest)."""
    parse_manifest_text(path.read_text(encoding="utf-8"))


def _classify_jsonschema_error(exc: BaseException, instance: dict[str, Any]) -> str:
    """Map a jsonschema ValidationError onto one of the six distinct codes."""
    msg = str(exc)
    validator = getattr(exc, "validator", None)
    relative = list(getattr(exc, "relative_path", []) or [])

    if validator == "required" and "name" in msg:
        return ERR_MISSING_NAME
    if relative == ["version"] and validator in {"pattern", "type"}:
        return ERR_BAD_SEMVER if validator == "pattern" else ERR_WRONG_TYPE
    if validator == "additionalProperties":
        return ERR_UNKNOWN_TOP_LEVEL
    if relative[:1] == ["keywords"] and (
        validator == "minItems" or "minItems" in msg or "too short" in msg.lower()
    ):
        return ERR_EMPTY_KEYWORDS
    if validator == "type":
        return ERR_WRONG_TYPE
    if "name" not in instance and "'name' is a required property" in msg:
        return ERR_MISSING_NAME
    return ERR_SCHEMA


def _classify_fastjsonschema_error(exc: BaseException, instance: dict[str, Any]) -> str:
    msg = str(exc)
    low = msg.lower()
    if "name" not in instance and ("name" in low and "required" in low):
        return ERR_MISSING_NAME
    if "must match pattern" in low and "version" in low:
        return ERR_BAD_SEMVER
    if "must not contain" in low and "properties" in low:
        return ERR_UNKNOWN_TOP_LEVEL
    if "keywords" in low and (
        "too short" in low or "minitems" in low or "must contain" in low
    ):
        return ERR_EMPTY_KEYWORDS
    if "must be" in low and ("string" in low or "object" in low or "array" in low):
        # Prefer more specific codes when the path is obvious.
        if "version" in low and "string" in low:
            return ERR_WRONG_TYPE
        if "keywords" in low:
            return ERR_WRONG_TYPE
        return ERR_WRONG_TYPE
    if "name" in low and "required" in low:
        return ERR_MISSING_NAME
    return ERR_SCHEMA


def validate_with_jsonschema(
    instance: dict[str, Any], schema: dict[str, Any] | None = None
) -> Verdict:
    """Primary validator (jsonschema Draft 2020-12)."""
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError

    sch = schema if schema is not None else load_schema()
    try:
        Draft202012Validator(sch).validate(instance)
        return Verdict(ok=True, library="jsonschema")
    except ValidationError as exc:
        code = _classify_jsonschema_error(exc, instance)
        return Verdict(ok=False, library="jsonschema", error_code=code, message=str(exc))


def validate_with_fastjsonschema(
    instance: dict[str, Any], schema: dict[str, Any] | None = None
) -> Verdict:
    """Second validator (fastjsonschema) — independent implementation."""
    import fastjsonschema
    from fastjsonschema import JsonSchemaValueException

    sch = schema if schema is not None else load_schema()
    try:
        compiled = fastjsonschema.compile(sch)
        compiled(instance)
        return Verdict(ok=True, library="fastjsonschema")
    except JsonSchemaValueException as exc:
        code = _classify_fastjsonschema_error(exc, instance)
        return Verdict(
            ok=False, library="fastjsonschema", error_code=code, message=str(exc)
        )


def validate_manifest(
    instance: dict[str, Any], schema: dict[str, Any] | None = None
) -> tuple[Verdict, Verdict]:
    """Run both libraries; return (jsonschema, fastjsonschema) verdicts."""
    return (
        validate_with_jsonschema(instance, schema),
        validate_with_fastjsonschema(instance, schema),
    )


def assert_valid(
    instance: dict[str, Any], schema: dict[str, Any] | None = None
) -> None:
    """Raise ManifestSchemaError unless both libraries accept *instance*.

    IMP-0007: after dual-library schema green, also run the strict unknown-field
    / ``x-`` extension compatibility linter so a non-prefixed additive field
    cannot warn-as-green.
    """
    sch = schema if schema is not None else load_schema()
    # Policy frozen keys must stay aligned with this schema's properties.
    try:
        from strict_parser_policy import (  # noqa: WPS433
            StrictParserPolicyError,
            assert_frozen_matches_schema,
            assert_policy,
        )

        assert_frozen_matches_schema(sch)
        assert_policy(instance)
    except StrictParserPolicyError as exc:
        raise ManifestSchemaError(exc.code, str(exc)) from exc

    v1, v2 = validate_manifest(instance, sch)
    if v1.ok and v2.ok:
        return
    # Prefer primary library's classification when both fail.
    if not v1.ok:
        raise ManifestSchemaError(v1.error_code or ERR_SCHEMA, v1.message or "invalid")
    raise ManifestSchemaError(v2.error_code or ERR_SCHEMA, v2.message or "invalid")


def assert_live_manifest_valid(repo: Path | None = None) -> tuple[Verdict, Verdict]:
    """Load the live manifest + schema and require a dual-library green verdict."""
    root = repo or repo_root_from()
    schema = load_schema(root)
    instance = load_manifest(root / MANIFEST_RELPATH)
    # IMP-0007: fail closed on unknown fields / frozen-key drift before library pass.
    try:
        from strict_parser_policy import (  # noqa: WPS433
            StrictParserPolicyError,
            assert_frozen_matches_schema,
            assert_policy,
        )

        assert_frozen_matches_schema(schema)
        assert_policy(instance)
    except StrictParserPolicyError as exc:
        raise ManifestSchemaError(exc.code, str(exc)) from exc
    v1, v2 = validate_manifest(instance, schema)
    if not (v1.ok and v2.ok):
        raise ManifestSchemaError(
            v1.error_code or v2.error_code or ERR_SCHEMA,
            f"live manifest failed: jsonschema={v1} fastjsonschema={v2}",
        )
    if v1.ok != v2.ok:
        raise ManifestSchemaError(
            ERR_OTHER,
            f"library disagreement: jsonschema={v1} fastjsonschema={v2}",
        )
    return v1, v2


def with_additional_properties(
    schema: dict[str, Any], *, allowed: bool
) -> dict[str, Any]:
    """Return a deep-ish copy of *schema* with root ``additionalProperties`` set.

    Used by the MUTATION control: relax the rule and assert the unknown-key
    mutant goes green (proving the case tests the rule it claims to).
    """
    import copy

    out = copy.deepcopy(schema)
    out["additionalProperties"] = allowed
    return out


def mutate_missing_name(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out.pop("name", None)
    return out


def mutate_bad_semver(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out["version"] = "1.0"  # missing PATCH
    return out


def mutate_unknown_top_level(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out["surprise_unknown_field"] = True
    return out


def mutate_wrong_type(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out["version"] = 123  # must be string semver
    return out


def mutate_empty_keywords(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out["keywords"] = []
    return out


def mutate_duplicate_key_text(raw: str) -> str:
    """Inject a duplicate top-level ``\"name\"`` key into a JSON object text."""
    # Place a second "name" immediately after the opening brace.
    stripped = raw.lstrip()
    if not stripped.startswith("{"):
        raise ValueError("expected object JSON")
    return '{\n  "name": "duplicate-injected",\n' + stripped[1:]


def mutate_case_collision_text(raw: str) -> str:
    """Inject a case-distinct twin of ``name`` as ``Name`` (IMP-0009 fixture)."""
    stripped = raw.lstrip()
    if not stripped.startswith("{"):
        raise ValueError("expected object JSON")
    return '{\n  "Name": "CaseCollisionPlant",\n' + stripped[1:]


NEGATIVE_MUTATORS: dict[str, Any] = {
    ERR_MISSING_NAME: mutate_missing_name,
    ERR_BAD_SEMVER: mutate_bad_semver,
    ERR_UNKNOWN_TOP_LEVEL: mutate_unknown_top_level,
    ERR_WRONG_TYPE: mutate_wrong_type,
    ERR_EMPTY_KEYWORDS: mutate_empty_keywords,
    ERR_DUPLICATE_KEY: mutate_duplicate_key_text,
    ERR_CASE_COLLISION: mutate_case_collision_text,
}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="repo root (default: discover from cwd / this file)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="manifest path (default: <repo>/.claude-plugin/plugin.json)",
    )
    args = parser.parse_args(argv)
    root = args.repo or repo_root_from(Path.cwd())
    path = args.manifest or (root / MANIFEST_RELPATH)
    schema = load_schema(root)
    try:
        instance = load_manifest(path)
    except ManifestSchemaError as exc:
        print(f"PARSE-FAIL code={exc.code} {exc}")
        return 1
    v1, v2 = validate_manifest(instance, schema)
    print(
        json.dumps(
            {
                "manifest": str(path),
                "schema": str(root / SCHEMA_RELPATH),
                "jsonschema": v1.__dict__,
                "fastjsonschema": v2.__dict__,
                "agree": v1.ok == v2.ok,
                "ok": v1.ok and v2.ok,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if (v1.ok and v2.ok and v1.ok == v2.ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
