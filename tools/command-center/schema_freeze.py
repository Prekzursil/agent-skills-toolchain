#!/usr/bin/env python3
"""CC-0012: freeze schemas/launchers; admit later changes only via versioned migration.

Gate rules:
  - Paths listed in SCHEMA-FREEZE.json are frozen once activation_commit is set.
  - An edit to a frozen path without a schema_version bump AND a migration record is RED.
  - A bump + migration with passing forward/back round-trip is GREEN.
  - Non-frozen paths are silent (gate does not freeze the whole repo).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_FREEZE = REPO / "command-center" / "SCHEMA-FREEZE.json"
DEFAULT_MIGRATIONS = REPO / "command-center" / "schema" / "migrations"


class FreezeGateError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_freeze(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or DEFAULT_FREEZE).read_text(encoding="utf-8"))


def is_frozen(freeze: dict[str, Any], rel_path: str) -> bool:
    if not freeze.get("activated"):
        return False
    frozen = set(freeze.get("frozen_paths") or [])
    return rel_path in frozen


def check_edit(
    freeze: dict[str, Any],
    *,
    rel_path: str,
    old_sha256: str | None,
    new_sha256: str,
    version_bumped: bool,
    migration_id: str | None,
    migration_roundtrip_ok: bool,
) -> dict[str, Any]:
    """Evaluate one proposed edit. Returns a gate result dict."""
    if not is_frozen(freeze, rel_path):
        return {
            "path": rel_path,
            "frozen": False,
            "verdict": "SILENT",
            "reason": "path not in freeze set (or freeze not activated)",
        }
    if old_sha256 == new_sha256:
        return {
            "path": rel_path,
            "frozen": True,
            "verdict": "SILENT",
            "reason": "bytes unchanged",
        }
    if not version_bumped or not migration_id or not migration_roundtrip_ok:
        return {
            "path": rel_path,
            "frozen": True,
            "verdict": "RED",
            "reason": (
                "frozen path changed without version bump + migration with "
                f"passing round-trip (bumped={version_bumped}, "
                f"migration_id={migration_id!r}, roundtrip_ok={migration_roundtrip_ok})"
            ),
        }
    return {
        "path": rel_path,
        "frozen": True,
        "verdict": "GREEN",
        "reason": f"version bump + migration {migration_id} round-trip ok",
        "migration_id": migration_id,
    }


def migrate_forward(doc: dict[str, Any], migration: dict[str, Any]) -> dict[str, Any]:
    """Apply a declarative migration: rename keys and/or set schema_version."""
    out = deepcopy(doc)
    for rename in migration.get("renames") or []:
        src, dst = rename["from"], rename["to"]
        if src in out:
            out[dst] = out.pop(src)
    if "target_schema_version" in migration:
        out["schema_version"] = migration["target_schema_version"]
    for key, value in (migration.get("set") or {}).items():
        out[key] = value
    return out


def migrate_back(doc: dict[str, Any], migration: dict[str, Any]) -> dict[str, Any]:
    """Inverse of migrate_forward for rename/set/version migrations."""
    out = deepcopy(doc)
    for rename in reversed(migration.get("renames") or []):
        src, dst = rename["from"], rename["to"]
        if dst in out:
            out[src] = out.pop(dst)
    if "source_schema_version" in migration:
        out["schema_version"] = migration["source_schema_version"]
    for key in (migration.get("set") or {}):
        # Best-effort: drop keys introduced by set unless listed as sticky.
        if key not in (migration.get("sticky_keys") or []):
            out.pop(key, None)
    return out


def roundtrip_ok(sample: dict[str, Any], migration: dict[str, Any]) -> bool:
    forward = migrate_forward(sample, migration)
    back = migrate_back(forward, migration)
    return json.dumps(back, sort_keys=True) == json.dumps(sample, sort_keys=True)


def load_migration(migrations_dir: Path, migration_id: str) -> dict[str, Any]:
    path = migrations_dir / f"{migration_id}.json"
    if not path.is_file():
        raise FreezeGateError(f"migration not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def activate_freeze(
    freeze: dict[str, Any],
    *,
    commit_sha: str,
    timestamp: str,
) -> dict[str, Any]:
    out = deepcopy(freeze)
    out["activated"] = True
    out["activation_commit"] = commit_sha
    out["activation_timestamp"] = timestamp
    # Snapshot current hashes for frozen paths that exist.
    snapshots = {}
    for rel in out.get("frozen_paths") or []:
        p = REPO / rel
        if p.is_file():
            snapshots[rel] = {
                "sha256": sha256_file(p),
                "schema_version_field": out.get("schema_version_field", "schema_version"),
            }
    out["snapshots"] = snapshots
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument(
        "--check",
        nargs=5,
        metavar=(
            "REL_PATH",
            "OLD_SHA",
            "NEW_SHA",
            "VERSION_BUMPED",
            "MIGRATION_ID_OR_NONE",
        ),
        help="Evaluate one edit against the freeze gate.",
    )
    parser.add_argument(
        "--roundtrip",
        nargs=2,
        metavar=("MIGRATION_ID", "SAMPLE_JSON"),
        help="Run forward/back round-trip on SAMPLE_JSON with migration.",
    )
    parser.add_argument("--migrations-dir", type=Path, default=DEFAULT_MIGRATIONS)
    args = parser.parse_args(argv)

    freeze = load_freeze(args.freeze)

    if args.roundtrip:
        mid, sample_path = args.roundtrip
        migration = load_migration(args.migrations_dir, mid)
        sample = json.loads(Path(sample_path).read_text(encoding="utf-8"))
        ok = roundtrip_ok(sample, migration)
        print(json.dumps({"migration_id": mid, "roundtrip_ok": ok}, indent=2))
        return 0 if ok else 1

    if args.check:
        rel, old_sha, new_sha, bumped_s, mid = args.check
        bumped = bumped_s.lower() in {"1", "true", "yes"}
        migration_id = None if mid in {"NONE", "none", "-"} else mid
        rt_ok = False
        if migration_id:
            # Round-trip against a tiny synthetic sample unless caller uses --roundtrip.
            migration = load_migration(args.migrations_dir, migration_id)
            sample = {"schema_version": migration.get("source_schema_version", 1), "x": 1}
            if migration.get("renames"):
                sample[migration["renames"][0]["from"]] = "v"
            rt_ok = roundtrip_ok(sample, migration)
        result = check_edit(
            freeze,
            rel_path=rel,
            old_sha256=old_sha,
            new_sha256=new_sha,
            version_bumped=bumped,
            migration_id=migration_id,
            migration_roundtrip_ok=rt_ok,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["verdict"] != "RED" else 1

    print(
        json.dumps(
            {
                "activated": freeze.get("activated"),
                "activation_commit": freeze.get("activation_commit"),
                "frozen_path_count": len(freeze.get("frozen_paths") or []),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
