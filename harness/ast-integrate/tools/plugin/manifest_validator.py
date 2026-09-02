"""Validate plugin / marketplace manifest *text* (TST-0182 signal a).

The validator works on the raw JSON text, not on a dict a caller already
built, because a ``dict`` has already applied last-wins to any repeated
member.  Three layers run in order:

1. :func:`plugin.strict_json.loads_strict` parses RFC 8259 JSON and raises
   :class:`plugin.strict_json.DuplicateKeyError` on a repeated member, naming
   the key and both competing values.  The error is enriched with the JSONPath
   of the owning object taken from the independent token scan.
2. :func:`plugin.json_key_scan.scan_keys` re-counts every written member as a
   second signal; a duplicate it sees that the parser somehow missed is still
   a rejection.
3. Shape checks: the document must be an object, ``name`` is required and must
   be a non-empty lower-case identifier, ``version`` (when present) must be
   semver, a marketplace ``plugins`` list must hold ``{name, source}`` entries,
   and unknown top-level keys are reported as warnings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from plugin.json_key_scan import KeyScan, KeyScanError, scan_keys
from plugin.strict_json import DuplicateKeyError, StrictJSONError, loads_strict

__all__ = [
    "KIND_MARKETPLACE",
    "KIND_PLUGIN",
    "MARKETPLACE_ENTRY_KNOWN_KEYS",
    "MARKETPLACE_KNOWN_KEYS",
    "ManifestShapeError",
    "PLUGIN_KNOWN_KEYS",
    "ValidationResult",
    "detect_kind",
    "shape_issues",
    "validate_manifest_bytes",
    "validate_manifest_file",
    "validate_manifest_text",
]

KIND_PLUGIN = "plugin"
KIND_MARKETPLACE = "marketplace"

# Mirrors .claude-plugin/plugin.schema.json (top-level properties).
PLUGIN_KNOWN_KEYS = frozenset(
    {
        "name",
        "version",
        "description",
        "author",
        "license",
        "homepage",
        "keywords",
        "compatibility",
        "deploy",
        "entrypoints",
        "interpreters",
        "min_client_version",
        "supported_clients",
        "payload",
        "permissions",
    }
)
# Mirrors tools/plugin/schema/marketplace.schema.json plus the version field
# marketplace indexes in this tree carry.
MARKETPLACE_KNOWN_KEYS = frozenset(
    {"name", "version", "description", "schema_version", "owner", "plugins"}
)
MARKETPLACE_ENTRY_KNOWN_KEYS = frozenset({"name", "source", "description", "version"})

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?$")


class ManifestShapeError(ValueError):
    """The document parsed but does not have the shape of a manifest."""

    def __init__(self, issues: list[str]) -> None:
        super().__init__("; ".join(issues) if issues else "manifest shape invalid")
        self.issues = list(issues)


@dataclass
class ValidationResult:
    """Outcome of validating one manifest text."""

    ok: bool
    kind: str
    document: dict[str, Any] | None = None
    error: Exception | None = None
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    key_scan: KeyScan | None = None

    @property
    def error_type(self) -> str:
        return type(self.error).__name__ if self.error is not None else ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ok": self.ok,
            "kind": self.kind,
            "error_type": self.error_type,
            "error": str(self.error) if self.error is not None else "",
            "issues": list(self.issues),
            "warnings": list(self.warnings),
        }
        if isinstance(self.error, DuplicateKeyError):
            out["duplicate"] = self.error.to_dict()
        if self.key_scan is not None:
            out["duplicate_keys"] = self.key_scan.duplicate_keys()
        return out


def detect_kind(document: Any) -> str:
    """A manifest with a ``plugins`` list is a marketplace index, else a plugin."""
    if isinstance(document, dict) and isinstance(document.get("plugins"), list):
        return KIND_MARKETPLACE
    return KIND_PLUGIN


def _check_name(value: Any, label: str, issues: list[str]) -> None:
    if not isinstance(value, str) or not value:
        issues.append(f"{label} must be a non-empty string")
    elif not _NAME_RE.match(value):
        issues.append(f"{label} {value!r} is not a lower-case identifier")


def _check_version(value: Any, label: str, issues: list[str]) -> None:
    if not isinstance(value, str) or not _VERSION_RE.match(value):
        issues.append(f"{label} {value!r} is not semver (MAJOR.MINOR.PATCH)")


def shape_issues(document: dict[str, Any], kind: str) -> tuple[list[str], list[str]]:
    """Return ``(fatal issues, warnings)`` for a parsed manifest object."""
    issues: list[str] = []
    warnings: list[str] = []

    if "name" not in document:
        issues.append("required key 'name' is missing")
    else:
        _check_name(document["name"], "name", issues)

    if "version" in document:
        _check_version(document["version"], "version", issues)
    elif kind == KIND_PLUGIN:
        issues.append("required key 'version' is missing")

    if "description" in document and not isinstance(document["description"], str):
        issues.append("description must be a string")

    known = MARKETPLACE_KNOWN_KEYS if kind == KIND_MARKETPLACE else PLUGIN_KNOWN_KEYS
    for key in document:
        if key not in known:
            warnings.append(f"unknown top-level key {key!r} for {kind} manifest")

    if kind == KIND_MARKETPLACE:
        plugins = document.get("plugins")
        if not isinstance(plugins, list):
            issues.append("plugins must be an array")
        else:
            seen: set[str] = set()
            for index, entry in enumerate(plugins):
                label = f"plugins[{index}]"
                if not isinstance(entry, dict):
                    issues.append(f"{label} must be an object")
                    continue
                if "name" not in entry:
                    issues.append(f"{label}.name is missing")
                else:
                    _check_name(entry["name"], f"{label}.name", issues)
                    if isinstance(entry["name"], str):
                        if entry["name"] in seen:
                            issues.append(
                                f"{label}.name {entry['name']!r} is listed twice"
                            )
                        seen.add(entry["name"])
                source = entry.get("source")
                if not isinstance(source, str) or not source:
                    issues.append(f"{label}.source must be a non-empty string")
                if "version" in entry:
                    _check_version(entry["version"], f"{label}.version", issues)
                for key in entry:
                    if key not in MARKETPLACE_ENTRY_KNOWN_KEYS:
                        warnings.append(f"unknown key {key!r} in {label}")
        owner = document.get("owner")
        if owner is not None:
            if not isinstance(owner, dict):
                issues.append("owner must be an object")
            elif not isinstance(owner.get("name"), str) or not owner.get("name"):
                issues.append("owner.name must be a non-empty string")
    else:
        author = document.get("author")
        if author is not None and not isinstance(author, (dict, str)):
            issues.append("author must be an object or string")
        for key in ("keywords", "entrypoints", "interpreters", "supported_clients"):
            if key in document and not isinstance(document[key], list):
                issues.append(f"{key} must be an array")
        for key in ("compatibility", "deploy", "payload", "permissions"):
            if key in document and not isinstance(document[key], dict):
                issues.append(f"{key} must be an object")

    return issues, warnings


def _enrich_duplicate(
    exc: DuplicateKeyError, scan: KeyScan | None
) -> DuplicateKeyError:
    """Attach the owning object's JSONPath found by the independent scan."""
    if scan is None:
        return exc
    for row in scan.duplicate_keys():
        values = row["values"]
        if (
            row["key"] == exc.key
            and len(values) >= 2
            and values[0] == exc.first
            and values[1] == exc.second
        ):
            return DuplicateKeyError(
                exc.key,
                exc.first,
                exc.second,
                path=row["path"],
                line=exc.line,
                column=exc.column,
            )
    return exc


def validate_manifest_text(text: Any, *, kind: str | None = None) -> ValidationResult:
    """Validate manifest JSON text; never last-wins on repeated members."""
    if isinstance(text, (bytes, bytearray)):
        try:
            text = bytes(text).decode("utf-8")
        except UnicodeDecodeError as exc:
            return ValidationResult(
                ok=False, kind=kind or "", error=exc, issues=[str(exc)]
            )
    raw = str(text)

    scan: KeyScan | None
    try:
        scan = scan_keys(raw)
    except KeyScanError:
        scan = None

    try:
        document = loads_strict(raw)
    except DuplicateKeyError as exc:
        enriched = _enrich_duplicate(exc, scan)
        return ValidationResult(
            ok=False,
            kind=kind or "",
            error=enriched,
            issues=[str(enriched)],
            key_scan=scan,
        )
    except StrictJSONError as exc:
        return ValidationResult(
            ok=False, kind=kind or "", error=exc, issues=[str(exc)], key_scan=scan
        )

    if scan is not None and scan.has_duplicates():
        row = scan.duplicate_keys()[0]
        values = row["values"]
        exc = DuplicateKeyError(row["key"], values[0], values[1], path=row["path"])
        return ValidationResult(
            ok=False, kind=kind or "", error=exc, issues=[str(exc)], key_scan=scan
        )

    if not isinstance(document, dict):
        err = ManifestShapeError(
            [f"top-level value must be an object, got {type(document).__name__}"]
        )
        return ValidationResult(
            ok=False, kind=kind or "", error=err, issues=list(err.issues), key_scan=scan
        )

    resolved_kind = kind or detect_kind(document)
    issues, warnings = shape_issues(document, resolved_kind)
    if issues:
        err = ManifestShapeError(issues)
        return ValidationResult(
            ok=False,
            kind=resolved_kind,
            document=document,
            error=err,
            issues=issues,
            warnings=warnings,
            key_scan=scan,
        )
    return ValidationResult(
        ok=True,
        kind=resolved_kind,
        document=document,
        warnings=warnings,
        key_scan=scan,
    )


def validate_manifest_bytes(raw: bytes, *, kind: str | None = None) -> ValidationResult:
    """Validate UTF-8 manifest bytes (a leading UTF-8 BOM is tolerated)."""
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return validate_manifest_text(raw, kind=kind)


def validate_manifest_file(
    path: str | Path, *, kind: str | None = None
) -> ValidationResult:
    """Validate the manifest stored at ``path``."""
    file_path = Path(path)
    if kind is None and file_path.name.startswith("marketplace"):
        kind = KIND_MARKETPLACE
    return validate_manifest_bytes(file_path.read_bytes(), kind=kind)
