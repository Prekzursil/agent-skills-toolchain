#!/usr/bin/env python3
"""Emit or check a hook manifest for one explicit strict target dialect.

The Codex plugin-hooks parser rejects unknown top-level fields.  This boundary
therefore routes away only metadata explicitly named by the selected target
profile and rejects every other unsupported field instead of silently pruning
it.  Emission is read-only: generated JSON goes to stdout, while ``--check``
compares a source file with its canonical target rendering after normalizing
platform line endings.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


class ManifestError(ValueError):
    """The source cannot be emitted without violating the target contract."""


@dataclass(frozen=True)
class _TargetProfile:
    required: frozenset[str]
    supported_order: tuple[str, ...]
    routed_away: frozenset[str]


_TARGETS = {
    "codex-plugin": _TargetProfile(
        required=frozenset({"hooks"}),
        supported_order=("description", "hooks"),
        routed_away=frozenset({"$schema"}),
    )
}


def emit_manifest(source: Mapping[str, object], *, target: str) -> dict[str, object]:
    """Return a detached manifest containing only the selected target's fields."""
    try:
        profile = _TARGETS[target]
    except KeyError as exc:
        choices = ", ".join(sorted(_TARGETS))
        raise ManifestError(
            f"unknown target {target!r}; expected one of: {choices}"
        ) from exc

    if any(not isinstance(key, str) for key in source):
        raise ManifestError("manifest keys must be strings")

    source_keys = set(source)
    missing = profile.required - source_keys
    if missing:
        raise ManifestError(f"missing required keys: {', '.join(sorted(missing))}")

    supported = set(profile.supported_order)
    unknown = source_keys - supported - profile.routed_away
    if unknown:
        raise ManifestError(
            f"unsupported keys for {target}: {', '.join(sorted(unknown))}"
        )

    if not isinstance(source["hooks"], Mapping):
        raise ManifestError("hooks must be an object")
    if "description" in source and not isinstance(source["description"], str):
        raise ManifestError("description must be a string")

    projected = {key: source[key] for key in profile.supported_order if key in source}
    try:
        encoded = json.dumps(projected, ensure_ascii=False, allow_nan=False)
        encoded.encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"manifest is not strict JSON: {exc}") from exc

    detached = json.loads(encoded)
    if not isinstance(detached, dict):  # pragma: no cover - projected is always a dict
        raise AssertionError("internal error: projected manifest is not an object")
    return detached


def render_manifest(source: Mapping[str, object], *, target: str) -> str:
    """Render deterministic, newline-terminated JSON for ``target``."""
    emitted = emit_manifest(source, target=target)
    return json.dumps(emitted, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"duplicate key {key!r}")
        result[key] = value
    return result


def _load_source(path: Path) -> Mapping[str, object]:
    try:
        source = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read {path}: {exc}") from exc
    if not isinstance(source, dict):
        raise ManifestError(f"{path} must contain a JSON object")
    return source


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit", action="store_true", help="write target JSON to stdout")
    mode.add_argument(
        "--check",
        action="store_true",
        help="fail unless source text already equals the target rendering",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        rendered = render_manifest(_load_source(args.source), target=args.target)
        if args.check:
            actual = args.source.read_text(encoding="utf-8")
            if actual != rendered:
                print(
                    f"DRIFT: {args.source} is not canonical for target {args.target}",
                    file=sys.stderr,
                )
                return 1
            print(f"OK: {args.source} is canonical for target {args.target}")
            return 0
    except (ManifestError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
