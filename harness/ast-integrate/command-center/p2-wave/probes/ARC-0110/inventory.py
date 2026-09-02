#!/usr/bin/env python3
"""Census of frozen schemas/launchers vs published not-frozen scope.

The freeze is a closed set: production JSON Schema files the program validates
against, plus named program launchers. Probe fixtures, receipts, the catalog,
design-note schemas, implementation modules that are not launchers, and
conformance reports are published as NOT frozen so the freeze cannot be
over-read as 'the whole repo'.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from hashutil import digest_bytes, digest_file

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SCHEMA_ROOTS = (
    "command-center/schema",
    "tools/plugin/schema",
    "tools/bench",
)

# Live launchers on this Linux worktree. The Windows Launch-Adapter pair and
# tools/plugin/__main__.py are absent here; substituting those missing paths
# would make the freeze set empty of launchers and the ceremony vacuous.
LAUNCHERS = (
    "tools/command-center/seed.py",
    "command-center/p2-wave/seed-stage/dispatch_cursor.py",
    "command-center/p2-wave/seed-stage/bringup_cursor_fleet.py",
)

# Published not-frozen examples. Each path must exist. Probe 2 edits these
# in a scratch overlay and requires the gate to stay silent.
NOT_FROZEN_EXAMPLES = (
    "command-center/WORK-UNIT-CATALOG.json",
    "command-center/audit/AUD-0095-freeze-inventory.json",
    "command-center/phase3/RUBRIC.json",
    "command-center/p2-wave/probes/ARC-0101/fixtures/planted-case-collision.schema.json",
    "command-center/design/council/CNL-0076-stopping-expression-runtime-evaluation-semantics.schema.json",
    "tools/command-center/close.py",
    ".claude-plugin/plugin.json",
    "command-center/receipts/BLD-0015.json",
)

NOT_FROZEN_CLASSES = (
    {
        "id": "catalog-and-receipts",
        "why": "Work-unit bookkeeping is not a schema the program validates against, nor a launcher.",
    },
    {
        "id": "conformance-reports",
        "why": "Phase-4 reports record measurements; freezing them would freeze the evidence of the freeze.",
    },
    {
        "id": "probe-fixtures",
        "why": "Planted schemas exist to test detectors; they are not production contracts.",
    },
    {
        "id": "design-note-schemas",
        "why": "Council design-note companions are documentation contracts, not the program validation surface.",
    },
    {
        "id": "operator-tools",
        "why": "close.py and other command-center CLIs are operator tools, not program launchers.",
    },
    {
        "id": "plugin-marketplace-manifest",
        "why": ".claude-plugin/plugin.json is marketplace metadata, not a spawn path.",
    },
    {
        "id": "implementation-modules",
        "why": "Python/PowerShell that is not a named launcher remains editable after the freeze.",
    },
    {
        "id": "migration-records",
        "why": "New versioned migration records are the admitted change path; they cannot be frozen.",
    },
)


def rel_of(path: Path) -> str:
    return path.resolve().relative_to(REPO.resolve()).as_posix()


def is_schema_file(path: Path) -> bool:
    name = path.name.lower()
    return path.is_file() and name.endswith(".json")


def iter_schema_paths() -> list[Path]:
    found: list[Path] = []
    for root_rel in SCHEMA_ROOTS:
        root = REPO / root_rel
        if not root.is_dir():
            continue
        if root_rel == "tools/bench":
            candidates = list(root.glob("*.schema.json"))
        else:
            candidates = [p for p in root.iterdir() if is_schema_file(p)]
        for path in candidates:
            found.append(path)
    return sorted(found, key=lambda p: rel_of(p))


def iter_launcher_paths() -> list[Path]:
    missing = [rel for rel in LAUNCHERS if not (REPO / rel).is_file()]
    if missing:
        raise FileNotFoundError(f"named launchers missing: {missing}")
    return [REPO / rel for rel in LAUNCHERS]


def classify(rel: str) -> str:
    rel = rel.replace("\\", "/")
    if rel in LAUNCHERS:
        return "frozen-launcher"
    schema_rels = {rel_of(p) for p in iter_schema_paths()}
    if rel in schema_rels:
        return "frozen-schema"
    return "not-frozen"


def entry(path: Path, kind: str) -> dict[str, Any]:
    sha, size = digest_file(path)
    return {
        "path": rel_of(path),
        "kind": kind,
        "sha256": sha,
        "bytes": size,
        "content_version": 1,
        "present": True,
    }


def frozen_entries() -> list[dict[str, Any]]:
    rows = [entry(p, "schema") for p in iter_schema_paths()]
    rows.extend(entry(p, "launcher") for p in iter_launcher_paths())
    return rows


def set_fingerprint(rows: list[dict[str, Any]]) -> str:
    lines = "\n".join(f"{r['path']} {r['sha256']}" for r in rows) + "\n"
    return digest_bytes(lines.encode("utf-8"))[0]


def not_frozen_publication() -> dict[str, Any]:
    examples = []
    for rel in NOT_FROZEN_EXAMPLES:
        path = REPO / rel
        examples.append(
            {
                "path": rel,
                "present": path.is_file(),
                "class": classify(rel),
            }
        )
    return {
        "classes": list(NOT_FROZEN_CLASSES),
        "examples": examples,
        "rule": (
            "A path is frozen only if it is a production schema under "
            "SCHEMA_ROOTS or a named launcher in LAUNCHERS. Every other path "
            "remains editable. The freeze is not the whole repository."
        ),
    }


def census() -> dict[str, Any]:
    rows = frozen_entries()
    schemas = [r for r in rows if r["kind"] == "schema"]
    launchers = [r for r in rows if r["kind"] == "launcher"]
    scope = not_frozen_publication()
    missing_examples = [e["path"] for e in scope["examples"] if not e["present"]]
    overclassed = [e["path"] for e in scope["examples"] if e["class"] != "not-frozen"]
    return {
        "frozen": rows,
        "frozen_count": len(rows),
        "schema_count": len(schemas),
        "launcher_count": len(launchers),
        "schema_roots": list(SCHEMA_ROOTS),
        "launchers": list(LAUNCHERS),
        "set_sha256": set_fingerprint(rows),
        "not_frozen": scope,
        "not_frozen_examples_missing": missing_examples,
        "not_frozen_examples_overclassed": overclassed,
        "canonicalization": "sha256 of file bytes with CRLF normalized to LF",
    }
