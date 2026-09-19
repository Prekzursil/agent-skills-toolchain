"""Read-only reconciliation of repository and live skill surfaces.

The reconciler inventories every first-level entry in each skill root, preserves
the provenance of every name in the union, and compares content with SHA-256
after normalizing CRLF to LF for text. It never chooses a winner: one-sided
names and unequal copies are owner-routing findings, not permission to copy,
overwrite, or remove anything.
"""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from pathlib import Path
from typing import TypeAlias, TypedDict

SCHEMA = "skill-surface-reconcile/v1"

REPO_CANONICAL = "repo_canonical"
REPO_PROJECTION = "repo_projection"
LIVE_VAULT = "live_vault"
LIVE_DAILY = "live_daily"
ROOT_ARTIFACT = "<root-artifacts>"

SURFACE_ORDER = (
    REPO_CANONICAL,
    REPO_PROJECTION,
    LIVE_VAULT,
    LIVE_DAILY,
)
REPO_SURFACES = frozenset({REPO_CANONICAL, REPO_PROJECTION})
LIVE_SURFACES = frozenset({LIVE_VAULT, LIVE_DAILY})

DEPLOY_EXCLUDE_NAMES = frozenset(
    {
        "installed.json",
        "backups",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".deploy.lock",
    }
)
DEPLOY_EXCLUDE_SUFFIXES = (".bak",)
DEPLOY_STAGE_PREFIX = ".deploy-stage-"

FileMap: TypeAlias = dict[str, str]
Inventory: TypeAlias = dict[str, FileMap | None]
Inventories: TypeAlias = dict[str, Inventory]


class SkillRecord(TypedDict):
    """One reconciled skill (or the root-artifacts pseudo-skill) across surfaces."""

    skill: str
    identity: str
    kind: str
    status: str
    sources: list[str]
    surface_names: dict[str, list[str]]
    fingerprints: dict[str, str | None]
    differences: list[dict[str, object]]
    reparse_paths: list[str]
    reasons: list[str]
    route: str | None


class ClassifyResult(TypedDict):
    """The structured classification the reconciler builds and its callers read."""

    all_names: list[str]
    counts: dict[str, object]
    records: list[SkillRecord]
    findings: list[SkillRecord]


class SurfaceReadError(RuntimeError):
    """A required surface could not be inventoried reliably."""


def _is_reparse(path: Path) -> bool:
    """Recognize POSIX symlinks and Windows reparse points without following."""
    metadata = path.lstat()
    attributes = getattr(metadata, "st_file_attributes", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def is_deploy_excluded(name: str) -> bool:
    """Match the deployer's managed-file exclusion contract exactly."""
    return (
        name in DEPLOY_EXCLUDE_NAMES
        or name.endswith(DEPLOY_EXCLUDE_SUFFIXES)
        or ".bak-" in name
        or name.startswith(DEPLOY_STAGE_PREFIX)
    )


def _hash_path(path: Path) -> str:
    """Comparison SHA-256; normalize text EOLs, but never transform binary bytes."""
    digest = hashlib.sha256()
    if _is_reparse(path):
        digest.update(b"symlink\0")
        digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        return f"symlink:{digest.hexdigest()}"
    with path.open("rb") as handle:
        head = handle.read(8000)
        if b"\0" in head:
            digest.update(head)
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            return f"file:{digest.hexdigest()}"

        carry = b""
        chunk = head
        while chunk:
            data = carry + chunk
            carry = b"\r" if data.endswith(b"\r") else b""
            if carry:
                data = data[:-1]
            digest.update(data.replace(b"\r\n", b"\n"))
            chunk = handle.read(1024 * 1024)
        digest.update(carry)
    return f"file:{digest.hexdigest()}"


def comparison_hash(path: Path) -> str:
    """Public single-file form of the reconciler's comparison contract."""
    return _hash_path(Path(path))


def _root_resolution_token(root: Path) -> str:
    """Hash the fully resolved root identity without exposing its local path."""
    resolved = Path(root).resolve(strict=True)
    return hashlib.sha256(os.fsencode(str(resolved))).hexdigest()


def scan_surface(root: Path) -> Inventory:
    """Inventory every file the skills deployer can write under one root."""
    root = Path(root)
    if not root.exists():
        raise SurfaceReadError(f"missing surface root: {root}")
    if not root.is_dir():
        raise SurfaceReadError(f"surface root is not a directory: {root}")

    try:
        entries = sorted(root.iterdir(), key=lambda path: path.name.casefold())
    except OSError as exc:
        raise SurfaceReadError(
            f"cannot enumerate surface root {root}: {type(exc).__name__}"
        ) from exc

    skill_names: set[str] = set()
    for entry in entries:
        if is_deploy_excluded(entry.name):
            continue
        try:
            is_skill = entry.is_dir()
        except OSError as exc:
            raise SurfaceReadError(
                f"cannot inspect skill candidate {entry}: {type(exc).__name__}"
            ) from exc
        if is_skill:
            skill_names.add(entry.name)

    inventory: Inventory = {name: {} for name in skill_names}
    root_files: FileMap = {}

    def add_path(path: Path, *, directory_link: bool = False) -> None:
        rel = path.relative_to(root)
        parts = rel.parts
        if parts and parts[0] in skill_names:
            files = inventory[parts[0]]
            assert files is not None
            inner = Path(*parts[1:]).as_posix() if len(parts) > 1 else "@surface-link"
            if directory_link and inner != "@surface-link":
                inner += "/"
            files[inner] = _hash_path(path)
            return
        rel_text = rel.as_posix() + ("/" if directory_link else "")
        root_files[rel_text] = _hash_path(path)

    def raise_walk_error(exc: OSError) -> None:
        raise exc

    try:
        for dirpath, dirnames, filenames in os.walk(
            root, onerror=raise_walk_error, followlinks=False
        ):
            walkable = []
            for name in sorted(dirnames):
                if is_deploy_excluded(name):
                    continue
                path = Path(dirpath) / name
                if _is_reparse(path):
                    add_path(path, directory_link=True)
                else:
                    walkable.append(name)
            dirnames[:] = walkable
            for name in sorted(filenames):
                if is_deploy_excluded(name):
                    continue
                path = Path(dirpath) / name
                if not (path.is_file() or _is_reparse(path)):
                    raise SurfaceReadError(
                        f"unsupported file type under {root}: {path}"
                    )
                add_path(path)
    except SurfaceReadError:
        raise
    except OSError as exc:
        raise SurfaceReadError(
            f"cannot read surface {root}: {type(exc).__name__}"
        ) from exc

    if root_files:
        inventory[ROOT_ARTIFACT] = root_files
    return inventory


def names_only_inventory(names: list[str]) -> Inventory:
    """Build a name-only inventory when an offline manifest has no file bodies."""
    return {
        name: None
        for name in sorted(set(names))
        if name and not name.startswith(".") and "/" not in name and "\\" not in name
    }


def _fingerprint(files: FileMap) -> str:
    digest = hashlib.sha256()
    for rel, file_hash in sorted(files.items()):
        digest.update(rel.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _inventory_fingerprint(inventory: Inventory) -> str:
    """Stable token that ties a later safety check to this exact surface state."""
    digest = hashlib.sha256()
    for name, files in sorted(inventory.items()):
        digest.update(name.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        digest.update(
            b"unknown" if files is None else _fingerprint(files).encode("ascii")
        )
        digest.update(b"\0")
    return digest.hexdigest()


def _classify(inventories: Inventories) -> ClassifyResult:
    indexed = {
        surface: {
            identity: sorted(
                name
                for name in inventories.get(surface, {})
                if name.casefold() == identity
            )
            for identity in {name.casefold() for name in inventories.get(surface, {})}
        }
        for surface in SURFACE_ORDER
    }
    identities = sorted(
        set().union(*(set(indexed[surface]) for surface in SURFACE_ORDER))
    )
    records: list[SkillRecord] = []

    for identity in identities:
        kind = "root-artifacts" if identity == ROOT_ARTIFACT.casefold() else "skill"
        surface_names = {
            surface: indexed[surface][identity]
            for surface in SURFACE_ORDER
            if identity in indexed[surface]
        }
        sources = [surface for surface in SURFACE_ORDER if surface in surface_names]
        canonical_names = surface_names.get(REPO_CANONICAL, [])
        name = canonical_names[0] if canonical_names else surface_names[sources[0]][0]
        repo_present = any(surface in REPO_SURFACES for surface in sources)
        live_present = any(surface in LIVE_SURFACES for surface in sources)
        file_maps = {
            surface: (
                None
                if len(surface_names[surface]) != 1
                else inventories[surface][surface_names[surface][0]]
            )
            for surface in sources
        }
        fingerprints = {
            surface: None if files is None else _fingerprint(files)
            for surface, files in file_maps.items()
        }
        known_maps = {
            surface: files for surface, files in file_maps.items() if files is not None
        }
        all_paths = sorted(set().union(*(set(files) for files in known_maps.values())))
        differences: list[dict[str, object]] = [
            {
                "path": path,
                "hashes": {
                    surface: files.get(path) for surface, files in known_maps.items()
                },
            }
            for path in all_paths
            if len({files.get(path) for files in known_maps.values()}) > 1
        ]
        exact_names = {
            exact_name for names in surface_names.values() for exact_name in names
        }
        case_mismatch = len(exact_names) > 1 or any(
            len(names) > 1 for names in surface_names.values()
        )
        content_conflict = bool(differences)
        content_unverified = len(sources) > 1 and any(
            files is None for files in file_maps.values()
        )
        reparse_paths = sorted(
            {
                path
                for files in known_maps.values()
                for path, value in files.items()
                if value.startswith("symlink:")
            }
        )

        reasons: list[str] = []
        if live_present and not repo_present:
            reasons.append("live-only")
        if repo_present and not live_present:
            reasons.append("repo-only")
        if REPO_PROJECTION in surface_names and REPO_CANONICAL not in surface_names:
            reasons.append("projection-without-authority")
        if REPO_CANONICAL in surface_names and REPO_PROJECTION not in surface_names:
            reasons.append("canonical-not-projected")
        if case_mismatch:
            reasons.append("case-mismatch")
        if reparse_paths:
            reasons.append("reparse-point")
        if content_conflict:
            reasons.append("content-conflict")
        if content_unverified:
            reasons.append("content-unverified")

        route = None
        status = "ALIGNED"
        if reparse_paths:
            status = "CONFLICT"
            route = "materialize-review"
        elif content_conflict:
            status = "CONFLICT"
            route = "manual-merge"
        elif case_mismatch:
            status = "CONFLICT"
            route = "manual-rename"
        elif content_unverified:
            status = "CONFLICT"
            route = "content-compare-required"
        elif reasons:
            status = "ROUTE"
            route = "owner-review"

        records.append(
            {
                "skill": name,
                "identity": identity,
                "kind": kind,
                "status": status,
                "sources": sources,
                "surface_names": surface_names,
                "fingerprints": fingerprints,
                "differences": differences,
                "reparse_paths": reparse_paths,
                "reasons": reasons,
                "route": route,
            }
        )

    findings = [record for record in records if record["status"] != "ALIGNED"]
    skill_records = [record for record in records if record["kind"] == "skill"]
    counts: dict[str, object] = {
        "union": len(skill_records),
        "repo_only": sum("repo-only" in record["reasons"] for record in skill_records),
        "live_only": sum("live-only" in record["reasons"] for record in skill_records),
        "projection_without_authority": sum(
            "projection-without-authority" in record["reasons"] for record in records
        ),
        "canonical_not_projected": sum(
            "canonical-not-projected" in record["reasons"] for record in records
        ),
        "content_conflicts": sum(
            "content-conflict" in record["reasons"] for record in records
        ),
        "content_unverified": sum(
            "content-unverified" in record["reasons"] for record in records
        ),
        "case_mismatches": sum(
            "case-mismatch" in record["reasons"] for record in records
        ),
        "reparse_points": sum(
            "reparse-point" in record["reasons"] for record in records
        ),
        "root_artifact_findings": sum(
            record["kind"] == "root-artifacts" for record in findings
        ),
        "findings": len(findings),
        "surfaces": {
            surface: sum(name != ROOT_ARTIFACT for name in inventories.get(surface, {}))
            for surface in SURFACE_ORDER
        },
    }
    return {
        "all_names": [record["skill"] for record in skill_records],
        "counts": counts,
        "records": records,
        "findings": findings,
    }


def _detector_control() -> dict[str, object]:
    try:
        with tempfile.TemporaryDirectory(prefix="surface-reconcile-control-") as temp:
            base = Path(temp)
            roots = {surface: base / surface for surface in SURFACE_ORDER}
            for root in roots.values():
                root.mkdir()
            bodies = {
                REPO_CANONICAL: {
                    "__control_conflict__": "shared\n",
                    "__control_shared__": "shared\n",
                },
                REPO_PROJECTION: {
                    "__control_conflict__": "changed\n",
                    "__control_shared__": "shared\n",
                },
                LIVE_VAULT: {
                    "__control_live_only__": "shared\n",
                    "__control_shared__": "shared\n",
                },
            }
            for surface, skills in bodies.items():
                for name, body in skills.items():
                    skill_file = roots[surface] / name / "SKILL.md"
                    skill_file.parent.mkdir()
                    skill_file.write_text(body, encoding="utf-8")
            probe = _classify(
                {surface: scan_surface(root) for surface, root in roots.items()}
            )
    except (OSError, SurfaceReadError) as exc:
        return {
            "ok": False,
            "known_present": "__control_live_only__",
            "expected": "live-only",
            "problem": f"scan control raised {type(exc).__name__}",
        }
    by_name = {record["skill"]: record for record in probe["records"]}
    live_only = by_name.get("__control_live_only__")
    conflict = by_name.get("__control_conflict__")
    shared = by_name.get("__control_shared__")
    ok = (
        live_only is not None
        and live_only["reasons"] == ["live-only"]
        and conflict is not None
        and conflict["status"] == "CONFLICT"
        and shared is not None
        and shared["status"] == "ALIGNED"
    )
    return {
        "ok": ok,
        "engine": "scan_surface+classify",
        "known_present": "__control_live_only__",
        "expected": "live-only",
    }


def reconcile_inventories(
    inventories: Inventories, *, errors: list[dict[str, str]] | None = None
) -> dict[str, object]:
    """Classify a complete inventory without selecting or mutating a source."""
    missing = [surface for surface in SURFACE_ORDER if surface not in inventories]
    error_rows = list(errors or [])
    errored_surfaces = {row.get("surface") for row in error_rows}
    error_rows.extend(
        {"surface": surface, "problem": "inventory-missing"}
        for surface in missing
        if surface not in errored_surfaces
    )
    control = _detector_control()
    classified = _classify(inventories)
    if not classified["all_names"]:
        error_rows.append({"surface": "all", "problem": "unvalidated-empty-inventory"})
    else:
        observed = next(
            record for record in classified["records"] if record["kind"] == "skill"
        )
        control["observed"] = {
            "skill": observed["skill"],
            "sources": observed["sources"],
        }

    verdict = "FAILED" if error_rows or not control["ok"] else "CLEAN"
    if verdict == "CLEAN" and classified["findings"]:
        verdict = "ROUTE"
    return {
        "schema": SCHEMA,
        "verdict": verdict,
        "read_only": True,
        "authority": REPO_CANONICAL,
        "control": control,
        "errors": error_rows,
        "snapshots": {
            surface: (
                _inventory_fingerprint(inventories[surface])
                if surface in inventories
                else None
            )
            for surface in SURFACE_ORDER
        },
        "root_aliases": {surface: None for surface in SURFACE_ORDER},
        "root_resolutions": {surface: None for surface in SURFACE_ORDER},
        "policy": {
            "deletion_authorized": False,
            "overwrite_authorized": False,
            "winner_selected": False,
        },
        **classified,
    }


def reconcile_paths(roots: dict[str, Path]) -> dict[str, object]:
    """Scan required roots, then reconcile them through the shared classifier."""
    inventories: Inventories = {}
    errors: list[dict[str, str]] = []
    root_aliases: dict[str, str | None] = {}
    root_resolutions: dict[str, str | None] = {}
    for surface in SURFACE_ORDER:
        root = roots.get(surface)
        if root is None:
            errors.append({"surface": surface, "problem": "root-missing"})
            root_aliases[surface] = None
            root_resolutions[surface] = None
            continue
        try:
            is_alias = _is_reparse(root)
            alias_before = _hash_path(root) if is_alias else None
            resolution_before = _root_resolution_token(root)
            root_aliases[surface] = alias_before
            root_resolutions[surface] = resolution_before
            if is_alias and surface != LIVE_DAILY:
                errors.append(
                    {"surface": surface, "problem": "root-reparse-not-allowed"}
                )
                continue
            inventories[surface] = scan_surface(root)
            alias_after = _hash_path(root) if _is_reparse(root) else None
            resolution_after = _root_resolution_token(root)
            if alias_after != alias_before:
                errors.append(
                    {"surface": surface, "problem": "root-reparse-changed-during-scan"}
                )
            if resolution_after != resolution_before:
                errors.append(
                    {
                        "surface": surface,
                        "problem": "root-resolution-changed-during-scan",
                    }
                )
        except (OSError, RuntimeError, SurfaceReadError) as exc:
            errors.append({"surface": surface, "problem": str(exc)})
            root_aliases[surface] = None
            root_resolutions[surface] = None
    report = reconcile_inventories(inventories, errors=errors)
    report["root_aliases"] = root_aliases
    report["root_resolutions"] = root_resolutions
    return report
