"""IMP-0007: strict-parser unknown-field policy + reserved ``x-`` extension namespace.

Forward-compatibility rule for plugin manifests:

* Top-level keys in ``FROZEN_TOP_LEVEL_KEYS`` are the only non-extension keys a
  strict client may understand. Additive fields MUST use the reserved
  ``EXTENSION_PREFIX`` (``x-``); a bare unknown key fails closed (blocking).
* This module is the explicit policy / compatibility linter. Schema validation
  (IMP-0006 ``manifest_schema`` dual-library path) remains the machine-checkable
  SSOT for types/required; this linter refuses non-prefixed additive fields even
  if a schema dialect quirk were to soft-accept them.
* ``FROZEN_TOP_LEVEL_KEYS`` is declared to match what
  ``platform/plugin/manifest.py`` ``ALLOWED[""]`` parses — the catalog reviewer
  must confirm that alignment (not trust the schema alone).
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Reserved extension namespace (catalog + client loader).
EXTENSION_PREFIX = "x-"

# Frozen top-level keys: the only non-``x-`` keys a strict client accepts.
# Must stay aligned with platform/plugin/manifest.py ALLOWED[""] and with
# .claude-plugin/plugin.schema.json ``properties`` (IMP-0006).
FROZEN_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "version",
        "description",
        "author",
        "license",
        "keywords",
        "homepage",
        "compatibility",
        "interpreters",
        "entrypoints",
        "payload",
        "deploy",
    }
)

ERR_UNKNOWN_TOP_LEVEL = "unknown-top-level-key"
ERR_NON_EXTENSION_ADDITIVE = "non-extension-additive-field"
ERR_POLICY = "strict-policy-violation"
ERR_OTHER = "other"


class StrictParserPolicyError(ValueError):
    """Raised when a manifest violates the unknown-field / extension policy."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class PolicyVerdict:
    ok: bool
    error_code: str | None = None
    message: str | None = None
    unknown_keys: tuple[str, ...] = ()
    extension_keys: tuple[str, ...] = ()


def is_extension_key(key: str) -> bool:
    return key.startswith(EXTENSION_PREFIX)


def classify_top_level_keys(doc: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Return (frozen_present, extension_keys, unknown_bare_keys)."""
    frozen: list[str] = []
    extensions: list[str] = []
    unknown: list[str] = []
    for key in doc:
        if is_extension_key(key):
            extensions.append(key)
        elif key in FROZEN_TOP_LEVEL_KEYS:
            frozen.append(key)
        else:
            unknown.append(key)
    return frozen, extensions, unknown


def lint_unknown_fields(doc: dict[str, Any]) -> PolicyVerdict:
    """Fail closed on any bare (non-``x-``) top-level key outside the frozen set."""
    if not isinstance(doc, dict):
        return PolicyVerdict(
            ok=False,
            error_code=ERR_OTHER,
            message="manifest root must be an object",
        )
    _frozen, extensions, unknown = classify_top_level_keys(doc)
    if unknown:
        # Prefer the additive-field code when the key looks like a deliberate add.
        code = ERR_NON_EXTENSION_ADDITIVE
        if len(unknown) == 1 and unknown[0] in {"surprise_unknown_field", "unexpected"}:
            code = ERR_UNKNOWN_TOP_LEVEL
        elif any(not k.startswith("_") for k in unknown):
            code = ERR_UNKNOWN_TOP_LEVEL
        return PolicyVerdict(
            ok=False,
            error_code=code,
            message=(
                f"unknown field(s) {unknown!r} at <root>; "
                f"use the reserved {EXTENSION_PREFIX!r} namespace for extensions "
                f"(frozen={sorted(FROZEN_TOP_LEVEL_KEYS)})"
            ),
            unknown_keys=tuple(sorted(unknown)),
            extension_keys=tuple(sorted(extensions)),
        )
    return PolicyVerdict(
        ok=True,
        extension_keys=tuple(sorted(extensions)),
    )


def assert_policy(doc: dict[str, Any]) -> PolicyVerdict:
    """Raise StrictParserPolicyError unless *doc* satisfies the unknown-field policy."""
    verdict = lint_unknown_fields(doc)
    if not verdict.ok:
        raise StrictParserPolicyError(
            verdict.error_code or ERR_POLICY,
            verdict.message or "strict policy violation",
        )
    return verdict


def compatibility_lint(doc: dict[str, Any]) -> None:
    """Compatibility linter: refuse any non-prefixed additive top-level field.

    Alias of ``assert_policy`` with the catalog-facing name.
    """
    assert_policy(doc)


def frozen_keys_from_schema(schema: dict[str, Any]) -> frozenset[str]:
    """Extract the frozen top-level key set from a JSON Schema ``properties`` map."""
    props = schema.get("properties") or {}
    if not isinstance(props, dict):
        raise StrictParserPolicyError(ERR_POLICY, "schema.properties must be an object")
    return frozenset(props.keys())


def assert_frozen_matches_schema(
    schema: dict[str, Any], *, require_strict_additional: bool = True
) -> None:
    """Policy frozen set must equal schema properties (single SSOT surface)."""
    from_schema = frozen_keys_from_schema(schema)
    if from_schema != FROZEN_TOP_LEVEL_KEYS:
        missing = sorted(FROZEN_TOP_LEVEL_KEYS - from_schema)
        extra = sorted(from_schema - FROZEN_TOP_LEVEL_KEYS)
        raise StrictParserPolicyError(
            ERR_POLICY,
            f"frozen-key drift vs schema properties: missing_in_schema={missing} "
            f"extra_in_schema={extra}",
        )
    if require_strict_additional:
        # Fail closed if schema stopped rejecting unknown keys.
        if schema.get("additionalProperties") is not False:
            raise StrictParserPolicyError(
                ERR_POLICY,
                "schema.additionalProperties must be false (unknown fields fail closed)",
            )
        patterns = schema.get("patternProperties") or {}
        if not isinstance(patterns, dict) or "^x-" not in patterns:
            raise StrictParserPolicyError(
                ERR_POLICY,
                "schema.patternProperties must reserve ^x- extension namespace",
            )


def mutate_bare_unknown(doc: dict[str, Any], key: str = "surprise_unknown_field") -> dict[str, Any]:
    out = copy.deepcopy(doc)
    out[key] = True
    return out


def mutate_under_extension(
    doc: dict[str, Any], bare_key: str = "surprise_unknown_field"
) -> dict[str, Any]:
    """Same semantic payload as ``mutate_bare_unknown``, but under ``x-``."""
    out = copy.deepcopy(doc)
    out[f"{EXTENSION_PREFIX}{bare_key}"] = True
    return out


def fixture_base_manifest() -> dict[str, Any]:
    """Minimal fixture accepted by both schema (IMP-0006) and real client loader.

    Includes ``compatibility`` so ``platform/plugin/manifest.py`` can parse it —
    live repo-root plugin.json omits Phase-4 fields and is schema-only green.
    """
    return {
        "name": "strict-policy-probe",
        "version": "1.0.0",
        "description": "IMP-0007 accept/reject fixture",
        "author": {"name": "IMP-0007"},
        "license": "MIT",
        "keywords": ["strict-parser", "x-extension"],
        "compatibility": {
            "min_client": "1.0.0",
            "platforms": ["linux"],
            "schema_version": 1,
        },
    }


def accept_reject_pair(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the catalog accept/reject pair against the fixture policy linter."""
    base = doc if doc is not None else fixture_base_manifest()
    bad = mutate_bare_unknown(base)
    good = mutate_under_extension(base)

    bad_v = lint_unknown_fields(bad)
    good_v = lint_unknown_fields(good)
    base_v = lint_unknown_fields(base)

    return {
        "base_ok": base_v.ok,
        "reject_bare_unknown": (not bad_v.ok)
        and bad_v.error_code
        in {ERR_UNKNOWN_TOP_LEVEL, ERR_NON_EXTENSION_ADDITIVE},
        "reject_error_code": bad_v.error_code,
        "reject_unknown_keys": list(bad_v.unknown_keys),
        "accept_under_x": good_v.ok,
        "accept_extension_keys": list(good_v.extension_keys),
        "extension_prefix": EXTENSION_PREFIX,
        "frozen_top_level_keys": sorted(FROZEN_TOP_LEVEL_KEYS),
        "pair_confirmed": (
            base_v.ok
            and (not bad_v.ok)
            and good_v.ok
            and f"{EXTENSION_PREFIX}surprise_unknown_field" in good_v.extension_keys
        ),
    }


def load_client_allowed_top_level(repo: Path) -> frozenset[str]:
    """Read the real client's ``ALLOWED['']`` via ``PYTHONPATH=platform`` import.

    Prefer calling this from a subprocess (catalog signal 2) so the fixture
    policy and the client loader do not share an in-process import graph.
    """
    import sys

    platform_root = str(repo / "platform")
    if platform_root not in sys.path:
        sys.path.insert(0, platform_root)
    from plugin import manifest as client_manifest  # type: ignore[import-not-found]

    top = client_manifest.ALLOWED.get("")
    if not isinstance(top, frozenset):
        raise StrictParserPolicyError(ERR_OTHER, "client ALLOWED[''] missing")
    return frozenset(top)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pair",
        action="store_true",
        help="run accept/reject pair on the built-in fixture and print JSON",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="lint a manifest file (JSON object)",
    )
    args = parser.parse_args(argv)
    if args.pair:
        result = accept_reject_pair()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("pair_confirmed") else 1
    if args.manifest is not None:
        doc = json.loads(args.manifest.read_text(encoding="utf-8"))
        try:
            assert_policy(doc)
        except StrictParserPolicyError as exc:
            print(json.dumps({"ok": False, "code": exc.code, "error": str(exc)}))
            return 1
        print(json.dumps({"ok": True}))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
