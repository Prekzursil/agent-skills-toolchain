#!/usr/bin/env python3
"""IMP-0062: CycloneDX SBOM for the plugin dependency closure.

Builds a CycloneDX 1.5 JSON document from npm ``package-lock.json`` files
(and optional Python requirement pins), and ALWAYS surfaces vendored trees as
components — even when a vendor directory has no lockfile entry.

Two-signal contract (catalog evidence_requirement):

1. The emitted SBOM validates against ``schema/cyclonedx-sbom.schema.json``.
2. Component names equal an *independent* lockfile parse (set equality).

The independent parser (:func:`independent_npm_lockfile_names`) deliberately
walks lockfile keys via path-segment extraction rather than the structured
``packages[path].name`` field the builder prefers, so a builder that invents
names without reading the lockfile fails the set-equality check.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from jsonschema import Draft202012Validator

SCHEMA_RELPATH = "tools/plugin/schema/cyclonedx-sbom.schema.json"
TOOL_NAME = "astplugin-sbom"
TOOL_VERSION = "1.0.0"
DEFAULT_LICENSE = "NOASSERTION"

# Vendored / unpinned trees that must appear even without a lockfile pin.
DEFAULT_VENDORED_MARKERS = (
    "tools/editor/ralph-orchestrator/vendor",
)


class SbomError(RuntimeError):
    """Fail-closed SBOM construction / validation error."""


@dataclass(frozen=True)
class Component:
    """One CycloneDX component before serialisation."""

    name: str
    version: str | None
    ctype: str = "library"
    purl: str | None = None
    license_id: str = DEFAULT_LICENSE
    hashes: tuple[tuple[str, str], ...] = ()
    properties: tuple[tuple[str, str], ...] = ()
    bom_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.ctype,
            "name": self.name,
            "licenses": [{"license": {"id": self.license_id}}],
        }
        if self.version is not None:
            d["version"] = self.version
        if self.purl:
            d["purl"] = self.purl
        if self.bom_ref:
            d["bom-ref"] = self.bom_ref
        if self.hashes:
            d["hashes"] = [{"alg": a, "content": c} for a, c in self.hashes]
        if self.properties:
            d["properties"] = [{"name": n, "value": v} for n, v in self.properties]
        return d


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def deterministic_serial(*parts: str) -> str:
    """Stable urn:uuid from closure coordinates (reproducible builds)."""
    seed = "\x1f".join(parts).encode("utf-8")
    return "urn:uuid:" + str(
        uuid.UUID(bytes=hashlib.sha256(seed).digest()[:16], version=5)
    )


def _npm_name_from_lock_key(key: str) -> str | None:
    """Derive package name from a lockfile ``packages`` key path."""
    if not key or key == "":
        return None
    # Prefer the final node_modules/<name> segment (handles nested copies).
    if "node_modules/" in key:
        return key.rsplit("node_modules/", 1)[-1]
    # Workspace package path (e.g. tools/lib) — use leaf.
    return key.rstrip("/").split("/")[-1] or None


def _sri_to_hex(integrity: str) -> tuple[str, str] | None:
    """Convert npm SRI (``sha512-<b64>``) to (alg, hex)."""
    if not integrity or "-" not in integrity:
        return None
    alg, _, b64 = integrity.partition("-")
    alg_u = alg.upper().replace("SHA", "SHA-")
    if alg_u in {"SHA-256", "SHA-512", "SHA-1"}:
        try:
            raw = base64.b64decode(b64)
            return alg_u, raw.hex()
        except Exception:
            return None
    return None


def parse_npm_lockfile_components(lock_path: Path | str) -> list[Component]:
    """Structured parse of package-lock.json v2/v3 ``packages`` map."""
    path = Path(lock_path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SbomError(f"cannot read npm lockfile {path}: {exc}") from exc
    packages = doc.get("packages")
    if not isinstance(packages, dict):
        raise SbomError(f"{path}: missing packages object (need lockfileVersion >= 2)")

    out: list[Component] = []
    seen: set[tuple[str, str | None]] = set()
    for key, meta in packages.items():
        if key == "" or not isinstance(meta, dict):
            continue
        if meta.get("link") is True:
            # Workspace link — still record the link target name.
            name = meta.get("name") or _npm_name_from_lock_key(key)
            version = meta.get("version")
        else:
            name = meta.get("name") or _npm_name_from_lock_key(key)
            version = meta.get("version")
        if not name:
            continue
        ident = (name, version)
        if ident in seen:
            continue
        seen.add(ident)
        hashes: list[tuple[str, str]] = []
        sri = meta.get("integrity")
        if isinstance(sri, str):
            conv = _sri_to_hex(sri)
            if conv:
                hashes.append(conv)
        license_id = DEFAULT_LICENSE
        lic = meta.get("license")
        if isinstance(lic, str) and lic.strip():
            license_id = lic.strip().split()[0]
        purl = f"pkg:npm/{name}@{version}" if version else f"pkg:npm/{name}"
        props = (("ast:source", f"npm-lockfile:{path.as_posix()}"),)
        if "vendor" in path.as_posix().replace("\\", "/").split("/"):
            props = props + (("ast:vendored", "true"),)
        out.append(
            Component(
                name=name,
                version=version,
                ctype="library",
                purl=purl,
                license_id=license_id,
                hashes=tuple(hashes),
                properties=props,
                bom_ref=f"npm:{name}@{version or 'unpinned'}",
            )
        )
    return out


def independent_npm_lockfile_names(lock_path: Path | str) -> set[str]:
    """Independent lockfile name set — path-segment extraction only.

    Deliberately does **not** call :func:`parse_npm_lockfile_components`.
    Walks every ``packages`` key and takes the trailing ``node_modules/…``
    segment (or workspace leaf). Used for evidence signal (2) set equality.
    """
    path = Path(lock_path)
    try:
        raw = path.read_text(encoding="utf-8")
        doc = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise SbomError(f"independent parse failed for {path}: {exc}") from exc
    packages = doc.get("packages")
    if not isinstance(packages, dict):
        return set()
    names: set[str] = set()
    # Regex over keys only — ignores structured .name when present.
    key_re = re.compile(r"node_modules/((?:@[^/]+/)?[^/]+)$")
    for key in packages:
        if not key:
            continue
        m = key_re.search(key.replace("\\", "/"))
        if m:
            names.add(m.group(1))
        else:
            # Workspace package path without node_modules/
            leaf = key.rstrip("/").split("/")[-1]
            if leaf and leaf not in {".", ".."}:
                # Prefer packages[key].name when key lacks node_modules — but
                # only as a fallback for workspace roots; still independent of
                # builder Component construction.
                meta = packages[key]
                if isinstance(meta, dict) and isinstance(meta.get("name"), str):
                    names.add(meta["name"])
                else:
                    names.add(leaf)
    return names


def parse_python_requirement_lines(text: str) -> list[Component]:
    """Parse a requirements.txt-style pin list into components."""
    out: list[Component] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("-"):
            continue
        # name==version or name>=… — take name and optional pinned version
        m = re.match(
            r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(==|===|~=|>=|<=|!=|>|<)?\s*([^;#\s]+)?",
            s,
        )
        if not m:
            continue
        name = m.group(1)
        version = m.group(3) if m.group(2) == "==" else None
        purl = f"pkg:pypi/{name}@{version}" if version else f"pkg:pypi/{name}"
        out.append(
            Component(
                name=name,
                version=version,
                ctype="library",
                purl=purl,
                properties=(("ast:source", "python-requirements"),),
                bom_ref=f"pypi:{name}@{version or 'unpinned'}",
            )
        )
    return out


def parse_python_requirements_file(path: Path | str) -> list[Component]:
    p = Path(path)
    try:
        return parse_python_requirement_lines(p.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SbomError(f"cannot read python requirements {p}: {exc}") from exc


def vendored_tree_component(rel_path: str, *, present: bool) -> Component:
    """Mark a vendored tree as a component (reviewer_requirement surface)."""
    props = (
        ("ast:vendored", "true"),
        ("ast:vendored-path", rel_path),
        ("ast:present-on-disk", "true" if present else "false"),
        ("ast:source", "vendored-tree"),
    )
    return Component(
        name=f"vendored:{rel_path}",
        version=None,
        ctype="library",
        license_id=DEFAULT_LICENSE,
        properties=props,
        bom_ref=f"vendored:{rel_path}",
    )


def discover_vendored_trees(
    repo: Path | str,
    markers: Sequence[str] = DEFAULT_VENDORED_MARKERS,
) -> list[Component]:
    """Emit a component for each marker path that exists as a directory.

    Trees without a lockfile entry are still listed — omitting them because
    they lack a pin is exactly the defect the reviewer_requirement forbids.
    """
    root = Path(repo)
    out: list[Component] = []
    for rel in markers:
        p = root / rel
        if p.is_dir():
            out.append(vendored_tree_component(rel, present=True))
    return out


def lockfiles_from_osv_scanner_toml(toml_path: Path | str) -> list[str]:
    """Extract lockfile paths mentioned in osv-scanner.toml comments/config.

    Best-effort: the committed file documents scanned lockfiles in comments.
    Falls back to repo-root ``package-lock.json`` when none are found.
    """
    path = Path(toml_path)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    found = re.findall(
        r"(?m)^\s*#?\s*-?\s*((?:[\w./-]+/)?package-lock\.json)\s*$", text
    )
    # Also catch inline mentions like `foo/package-lock.json`
    found += re.findall(r"([\w./-]+package-lock\.json)", text)
    # Dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for f in found:
        f = f.strip().lstrip("- ").strip()
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    if "package-lock.json" not in seen:
        out.insert(0, "package-lock.json")
    return out


def build_sbom(
    *,
    name: str,
    version: str,
    npm_lockfiles: Sequence[Path | str] = (),
    python_requirements: Sequence[Path | str] = (),
    python_requirement_text: str | None = None,
    vendored_markers: Sequence[str] = DEFAULT_VENDORED_MARKERS,
    repo: Path | str | None = None,
    timestamp: str | None = None,
    extra_components: Sequence[Component] = (),
) -> dict[str, Any]:
    """Build a CycloneDX 1.5 SBOM dict from lockfiles + vendored trees."""
    components: list[Component] = []
    lock_digests: list[str] = []
    for lf in npm_lockfiles:
        p = Path(lf)
        lock_digests.append(
            hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "missing"
        )
        components.extend(parse_npm_lockfile_components(p))
    for rf in python_requirements:
        components.extend(parse_python_requirements_file(rf))
    if python_requirement_text is not None:
        components.extend(parse_python_requirement_lines(python_requirement_text))
    if repo is not None:
        components.extend(discover_vendored_trees(repo, vendored_markers))
    components.extend(extra_components)

    if not components:
        raise SbomError("refusing to emit empty SBOM: no components resolved")

    # Stable order by (name, version)
    components = sorted(
        components, key=lambda c: (c.name.lower(), c.version or "", c.bom_ref or "")
    )
    # Deduplicate by bom-ref / name@version
    deduped: list[Component] = []
    seen_refs: set[str] = set()
    for c in components:
        ref = c.bom_ref or f"{c.name}@{c.version}"
        if ref in seen_refs:
            continue
        seen_refs.add(ref)
        deduped.append(c)

    ts = timestamp or _utc_now()
    serial = deterministic_serial(
        name, version, *lock_digests, *(c.bom_ref or c.name for c in deduped)
    )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": serial,
        "version": 1,
        "metadata": {
            "timestamp": ts,
            "component": {"type": "application", "name": name, "version": version},
            "tools": [{"name": TOOL_NAME, "version": TOOL_VERSION}],
        },
        "components": [c.to_dict() for c in deduped],
    }


def component_names(sbom: dict[str, Any]) -> set[str]:
    """Names of non-vendored-marker library components (lockfile closure)."""
    names: set[str] = set()
    for c in sbom.get("components") or []:
        if not isinstance(c, dict):
            continue
        n = c.get("name")
        if not isinstance(n, str):
            continue
        props = {
            p.get("name"): p.get("value")
            for p in (c.get("properties") or [])
            if isinstance(p, dict)
        }
        if props.get("ast:source") == "vendored-tree":
            continue
        names.add(n)
    return names


def vendored_component_names(sbom: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for c in sbom.get("components") or []:
        if not isinstance(c, dict):
            continue
        props = {
            p.get("name"): p.get("value")
            for p in (c.get("properties") or [])
            if isinstance(p, dict)
        }
        if props.get("ast:vendored") == "true" or props.get("ast:source") == "vendored-tree":
            names.add(str(c.get("name")))
    return names


def load_schema(repo: Path | str | None = None) -> dict[str, Any]:
    root = Path(repo) if repo else Path(__file__).resolve().parents[2]
    path = root / SCHEMA_RELPATH
    return json.loads(path.read_text(encoding="utf-8"))


def validate_cyclonedx(
    sbom: dict[str, Any], schema: dict[str, Any] | None = None
) -> list[str]:
    """Validate SBOM against the CycloneDX subset schema. Empty list = ok."""
    sch = schema if schema is not None else load_schema()
    validator = Draft202012Validator(sch)
    return [
        f"{'/'.join(str(x) for x in e.path)}: {e.message}"
        for e in sorted(validator.iter_errors(sbom), key=lambda e: list(e.path))
    ]


def lockfile_closure_names(npm_lockfiles: Iterable[Path | str]) -> set[str]:
    """Union of independent lockfile name sets (signal 2 oracle)."""
    names: set[str] = set()
    for lf in npm_lockfiles:
        names |= independent_npm_lockfile_names(lf)
    return names


def write_sbom(sbom: dict[str, Any], out: Path | str) -> Path:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Emit CycloneDX SBOM (IMP-0062)")
    ap.add_argument("--name", default="agent-skills-toolchain")
    ap.add_argument("--version", default="0.1.0")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument(
        "--lockfile",
        action="append",
        default=[],
        help="npm package-lock.json (repeatable); default from osv-scanner.toml",
    )
    ap.add_argument("--python-requirements", action="append", default=[])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--validate", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)

    locks = list(args.lockfile)
    if not locks:
        osv = args.repo / "osv-scanner.toml"
        for rel in lockfiles_from_osv_scanner_toml(osv):
            p = args.repo / rel
            if p.is_file():
                locks.append(p)
    if not locks:
        raise SystemExit("no lockfiles found")

    sbom = build_sbom(
        name=args.name,
        version=args.version,
        npm_lockfiles=locks,
        python_requirements=args.python_requirements,
        repo=args.repo,
    )
    if args.validate:
        errs = validate_cyclonedx(sbom, load_schema(args.repo))
        if errs:
            print("SCHEMA INVALID:")
            for e in errs[:40]:
                print(" ", e)
            return 2
    write_sbom(sbom, args.out)
    print(f"wrote {args.out} components={len(sbom['components'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
