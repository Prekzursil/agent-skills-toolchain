"""Resolve a catalog ``output_schema`` declaration to a physical, compiling schema.

WHY THIS EXISTS
    All 2,007 catalogued work units declare ``output_schema`` under
    ``command-center/schema/``. That directory did not exist and the receipt schema
    was built at ``platform/schema/``, so every one of the 234 distinct declared
    files dangled and no unit could emit a schema-valid receipt.

    The fix is a resolver over a generated ``$ref``-shim tree. A shim makes the
    DECLARED path resolve on disk; the shim's body is a single ``$ref`` into
    ``platform/schema/`` so there is exactly one control plane. This module is the
    blessed way in: it maps a logical id to a compiled validator.

DESIGN RULES THIS MODULE KEEPS
    * FAIL CLOSED. An unknown logical id raises ``UnknownSchemaError``. It never
      degrades to a permissive schema -- a validator that accepts everything is
      worse than no validator, so "unresolvable" must stay loud.
    * NO NETWORK. Every ``$ref`` is retrieved from disk; the draft-2020-12
      meta-schema comes from the installed ``jsonschema`` package. A retrieval that
      would leave the filesystem raises.
    * NO REIMPLEMENTATION. Splitting a decorated catalog value into (file, fragment)
      is already owned by ``receipt_schema_gate.parse_schema_ref``; this module
      imports it.
    * NO PATH ESCAPE. A resolved ``$id`` is confined under the repo root.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
except ImportError as exc:  # pragma: no cover - dependency presence is a setup fact
    raise SystemExit(
        f"schema_resolver requires jsonschema>=4.18 (referencing API). Import failed: {exc}"
    ) from exc

sys.path.insert(0, str(Path(__file__).resolve().parent))
from receipt_schema_gate import parse_schema_ref  # noqa: E402  repo-owned splitter

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_URI = "https://ast-integrate.invalid/"
REGISTRY_PATH = REPO_ROOT / "platform" / "schema" / "ARTIFACT-CLASS-REGISTRY.json"
META_URL = "https://json-schema.org/draft/2020-12/schema"
_SCHEMA_TAIL = re.compile(r"/(platform/schema/|command-center/schema/)(.+)$")


def _root() -> Path:
    env = os.environ.get("AST_INTEGRATE_ROOT")
    if env:
        p = Path(env).resolve()
        if (p / "platform" / "schema" / "receipt.schema.json").is_file():
            return p
    return REPO_ROOT


def _uri_to_path(uri: str) -> Path:
    raw = uri.split("#", 1)[0]
    root = _root()
    if raw.startswith(BASE_URI):
        return (root / raw[len(BASE_URI) :]).resolve()
    path_s = raw
    if raw.startswith("file:"):
        path_s = urlparse(raw).path or ""
        if re.match(r"^/[A-Za-z]:/", path_s):
            path_s = path_s[1:]
    posix = path_s.replace("\\", "/")
    match = _SCHEMA_TAIL.search(posix)
    if match:
        return (root / (match.group(1) + match.group(2))).resolve()
    if raw.startswith("file:"):
        return Path(path_s)
    raise SchemaResolutionError(
        f"refusing to retrieve a non-local schema uri (no network): {uri!r}"
    )

__all__ = [
    "ResolvedSchema",
    "UnknownSchemaError",
    "SchemaResolutionError",
    "resolve",
    "validator_for",
    "validate_artifact",
    "load_registry",
    "build_registry",
]


class SchemaResolutionError(Exception):
    """Base class: resolution failed and must not be treated as a pass."""


class UnknownSchemaError(SchemaResolutionError):
    """The declared output_schema is not a known logical id. Fails closed."""


@dataclass(frozen=True)
class ResolvedSchema:
    """The outcome of resolving one ``output_schema`` declaration."""

    declared: str
    logical_id: str
    fragment: str | None
    kind: str
    shim_path: str | None
    physical_path: str
    physical_fragment: str | None
    artifact_class: str | None
    report_kind_pinned: bool

    @property
    def shim_exists(self) -> bool:
        return bool(self.shim_path) and (_root() / self.shim_path).is_file()

    @property
    def physical_exists(self) -> bool:
        return (_root() / self.physical_path).is_file()

    @property
    def resolves(self) -> bool:
        """True only when BOTH the declared path and its physical target exist.

        A shim whose target is missing is not resolution -- it is a dangling
        reference wearing a file name.
        """
        return self.shim_exists and self.physical_exists

    def as_dict(self) -> dict[str, Any]:
        return {
            "declared": self.declared,
            "logical_id": self.logical_id,
            "fragment": self.fragment,
            "kind": self.kind,
            "shim_path": self.shim_path,
            "shim_exists": self.shim_exists,
            "physical_path": self.physical_path,
            "physical_fragment": self.physical_fragment,
            "physical_exists": self.physical_exists,
            "artifact_class": self.artifact_class,
            "report_kind_pinned": self.report_kind_pinned,
            "resolves": self.resolves,
        }


_registry_cache: dict[str, Any] | None = None


def load_registry(path: Path | str = REGISTRY_PATH) -> dict[str, Any]:
    """Load ARTIFACT-CLASS-REGISTRY.json (cached)."""
    global _registry_cache
    if _registry_cache is None or path != REGISTRY_PATH:
        data = json.loads(Path(path).read_bytes().decode("utf-8"))
        if path == REGISTRY_PATH:
            _registry_cache = data
        return data
    return _registry_cache


def _retrieve(uri: str) -> Resource:
    """Fetch a ``$ref`` target from disk only. Never the network."""
    raw = str(uri).split("#", 1)[0]
    if raw == META_URL or raw.rstrip("#") == META_URL:
        return Resource.from_contents(
            dict(Draft202012Validator.META_SCHEMA), default_specification=DRAFT202012
        )
    root = _root()
    posix = raw.replace("\\", "/")
    local = (
        raw.startswith(BASE_URI)
        or raw.startswith("file:")
        or "/platform/schema/" in posix
        or "/command-center/schema/" in posix
    )
    if not local:
        raise SchemaResolutionError(
            f"refusing to retrieve a non-local schema uri (no network): {uri!r}"
        )
    target = _uri_to_path(uri)
    if not str(target).startswith(str(root) + os.sep) and target != root:
        raise SchemaResolutionError(f"schema uri escapes the repo root: {uri!r}")
    if not target.is_file():
        raise SchemaResolutionError(
            f"schema uri has no file on disk: {uri!r} -> {target}"
        )
    return Resource.from_contents(
        json.loads(target.read_bytes().decode("utf-8")),
        default_specification=DRAFT202012,
    )


def build_registry() -> Registry:
    """A referencing Registry whose retrieval is disk-only."""
    return Registry(retrieve=_retrieve)


def resolve(
    output_schema: str, registry_data: dict[str, Any] | None = None
) -> ResolvedSchema:
    """Map a declared ``output_schema`` string to its physical schema.

    Accepts every encoding the catalog uses: a bare path, a path plus a
    ``#/$defs/...`` pointer, a path plus a ``profile=... (required: ...)``
    annotation, and the bare draft-2020-12 meta-schema URL.

    Raises ``UnknownSchemaError`` for anything not in the registry.
    """
    if not isinstance(output_schema, str) or not output_schema.strip():
        raise UnknownSchemaError("output_schema is empty or not a string")

    reg = registry_data if registry_data is not None else load_registry()
    logical, fragment = parse_schema_ref(output_schema)
    logical = logical.replace("\\", "/")

    meta_alias = reg["meta_schema_url_alias"]
    if logical == meta_alias["id"]:
        return ResolvedSchema(
            declared=output_schema,
            logical_id=logical,
            fragment=fragment,
            kind="meta-schema-url",
            shim_path=None,
            physical_path=meta_alias["physical_path"],
            physical_fragment=None,
            artifact_class=None,
            report_kind_pinned=False,
        )

    entry = reg["entries"].get(logical)
    if entry is None:
        raise UnknownSchemaError(
            f"no registry entry for declared output_schema {logical!r} "
            f"(from {output_schema!r}). Refusing to guess a schema."
        )

    if entry["kind"] == "meta-schema-mirror":
        return ResolvedSchema(
            declared=output_schema,
            logical_id=logical,
            fragment=fragment,
            kind="meta-schema-mirror",
            shim_path=logical,
            physical_path=entry["physical_path"],
            physical_fragment=None,
            artifact_class=None,
            report_kind_pinned=False,
        )

    phys_path = entry["physical_path"]
    phys_frag = entry["physical_fragment"]
    artifact_class = entry.get("artifact_class")
    if fragment:
        name = fragment.lstrip("#").split("/")[-1]
        known = entry.get("fragments", {})
        if name not in known:
            raise UnknownSchemaError(
                f"{logical!r} declares no fragment {name!r}; known: {sorted(known)}"
            )
        # A fragment carries its OWN physical target. Reusing the file entry's
        # physical_path here was a real defect: the canonical receipt's 14 pointer
        # fragments resolved straight to receipt.schema.json and so bypassed the
        # report.kind pin, letting a cache_report receipt validate as a shell_report.
        phys_path = known[name]["physical_path"]
        phys_frag = known[name]["physical_fragment"]
        artifact_class = name
    return ResolvedSchema(
        declared=output_schema,
        logical_id=logical,
        fragment=fragment,
        kind=entry["kind"],
        shim_path=entry["shim_path"],
        physical_path=phys_path,
        physical_fragment=phys_frag,
        artifact_class=artifact_class,
        report_kind_pinned=bool(entry.get("report_kind_pinned")) or bool(fragment),
    )


def validator_for(output_schema: str) -> Draft202012Validator:
    """Compile a validator for a declared ``output_schema``. Fails closed."""
    res = resolve(output_schema)
    if res.kind in ("meta-schema-url", "meta-schema-mirror"):
        # A unit whose OUTPUT is a JSON Schema validates against the meta-schema.
        # Use the library's own copy so resolution is offline and authoritative.
        return Draft202012Validator(dict(Draft202012Validator.META_SCHEMA))
    if not res.physical_exists:
        raise SchemaResolutionError(
            f"physical schema missing for {res.logical_id!r}: {res.physical_path}"
        )
    phys = (_root() / res.physical_path).resolve()
    if not phys.is_file():
        raise SchemaResolutionError(
            f"physical schema missing for {res.logical_id!r}: {res.physical_path}"
        )
    uri = phys.as_uri() + (res.physical_fragment or "")
    return Draft202012Validator({"$ref": uri}, registry=build_registry())


def validate_artifact(artifact: Any, output_schema: str) -> list[str]:
    """Return sorted human-readable errors ('' empty list means valid)."""
    validator = validator_for(output_schema)
    out: list[str] = []
    for err in validator.iter_errors(artifact):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


# --------------------------------------------------------------------------- #
# CLI: audit every catalog declaration against disk
# --------------------------------------------------------------------------- #


def audit(catalog: Path | str | None = None) -> dict[str, Any]:
    """Resolve every ``output_schema`` in the catalog and count what resolves."""
    cat = (
        Path(catalog)
        if catalog
        else REPO_ROOT / "command-center" / "WORK-UNIT-CATALOG.json"
    )
    wus = json.loads(cat.read_bytes().decode("utf-8"))["work_units"]
    reg = load_registry()

    distinct: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, str]] = []
    refs_ok = 0
    for wu in wus:
        declared = wu.get("output_schema")
        try:
            res = resolve(declared, reg)
        except SchemaResolutionError as exc:
            unresolved.append(
                {"unit": wu.get("id", "?"), "declared": str(declared), "why": str(exc)}
            )
            continue
        if res.kind == "meta-schema-url" or res.resolves:
            refs_ok += 1
        distinct.setdefault(res.logical_id, res.as_dict())

    files = {k: v for k, v in distinct.items() if v["kind"] != "meta-schema-url"}
    return {
        "catalog_units": len(wus),
        "total_references": len(wus),
        "references_resolving": refs_ok,
        "references_unresolved": len(wus) - refs_ok,
        "distinct_logical_files": len(files),
        "distinct_logical_files_resolving": sum(
            1 for v in files.values() if v["resolves"]
        ),
        "distinct_logical_files_NOT_resolving": sorted(
            k for k, v in files.items() if not v["resolves"]
        ),
        "meta_schema_url_alias_present": "meta-schema-url"
        in {v["kind"] for v in distinct.values()},
        "unresolved_examples": unresolved[:10],
        "physical_control_plane": sorted(
            {v["physical_path"] for v in distinct.values()}
        ),
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--audit":
        rep = audit()
        print(json.dumps(rep, indent=2))
        ok = (
            rep["references_unresolved"] == 0
            and not rep["distinct_logical_files_NOT_resolving"]
            and rep["distinct_logical_files"] > 0
        )
        print("SUCCESS:schema-resolver-audit" if ok else "FAILED:schema-resolver-audit")
        return 0 if ok else 1
    if len(args) >= 2:
        errors = validate_artifact(
            json.loads(Path(args[0]).read_bytes().decode("utf-8")), args[1]
        )
        for e in errors:
            print(e)
        print(
            "SUCCESS:schema-valid"
            if not errors
            else f"FAILED:schema-invalid errors={len(errors)}"
        )
        return 0 if not errors else 1
    print(__doc__)
    print(
        "usage: schema_resolver.py --audit | <artifact.json> <output_schema-declaration>"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
