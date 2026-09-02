#!/usr/bin/env python3
"""Conformance suite for the schema_version migration-rules contract.

Rules (one negative plant each in probe 2):
  coverage                  — every consecutive declared pair has a migration
  first-apply-progress      — a from_version artifact actually changes on first apply
  idempotence               — second apply leaves bytes unchanged
  quarantine-no-drop        — untransformable records are quarantined, never deleted
  transformation-obligation — after N->N+1, the file validates as N+1 or is quarantined
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from engine import (
    DROPPED,
    NOOP,
    QUARANTINED,
    TRANSFORMED,
    apply_file,
    consecutive_transitions,
    sha256_bytes,
    still_validates,
)


def _index_migrations(registry: dict[str, Any]) -> dict[tuple[int, int], dict[str, Any]]:
    out: dict[tuple[int, int], dict[str, Any]] = {}
    for mig in registry.get("migrations") or []:
        if not isinstance(mig, dict):
            continue
        key = (int(mig["from_version"]), int(mig["to_version"]))
        out[key] = mig
    return out


def evaluate(
    registry: dict[str, Any],
    sources: list[tuple[Path, str]],
    *,
    include_unparseable: Path | None = None,
) -> dict[str, Any]:
    """Run the suite on a disposable copy of `sources`. Never writes into `sources`."""
    indexed = _index_migrations(registry)
    versions = [int(v) for v in (registry.get("schema_versions") or [])]
    declared = consecutive_transitions(versions)
    missing = [f"{a}->{b}" for a, b in declared if (a, b) not in indexed]
    coverage_ok = bool(declared) and not missing

    file_count_start = 0
    double_apply: list[dict[str, Any]] = []
    progress_failures: list[str] = []
    idem_failures: list[str] = []
    obligation_failures: list[str] = []
    dropped: list[str] = []
    quarantined: list[str] = []
    transformed_first: int = 0

    with tempfile.TemporaryDirectory(prefix="TST-0047-") as tmp:
        root = Path(tmp)
        live: list[Path] = []
        for src, dest_name in sources:
            target = root / dest_name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            live.append(target)
        if include_unparseable is not None:
            garbage = root / "garbage.unparseable"
            shutil.copy2(include_unparseable, garbage)
            live.append(garbage)
        file_count_start = sum(1 for p in root.rglob("*") if p.is_file())

        ordered = [indexed[pair] for pair in declared if pair in indexed]
        for mig in ordered:
            to_v = int(mig["to_version"])
            from_v = int(mig["from_version"])
            # Snapshot current files (skip quarantine sidecars).
            current = [
                p
                for p in root.iterdir()
                if p.is_file() and p.name != "quarantine"
            ]
            for path in current:
                before = path.read_bytes()
                sha0 = sha256_bytes(before)
                try:
                    obj0 = json.loads(before.decode("utf-8"))
                    was_from = (
                        isinstance(obj0, dict) and obj0.get("schema_version") == from_v
                    )
                except (UnicodeDecodeError, ValueError):
                    obj0 = None
                    was_from = False

                r1 = apply_file(path, mig)
                if r1.status == DROPPED or not path.exists():
                    dropped.append(f"{mig['id']}:{path.name}:{r1.reason}")
                    double_apply.append(
                        {
                            "migration_id": mig["id"],
                            "artifact": path.name,
                            "sha_before": sha0,
                            "sha_after_first": None,
                            "sha_after_second": None,
                            "status_first": r1.status,
                            "status_second": None,
                            "second_run_unchanged": False,
                            "first_run_mutated": True,
                            "dropped": True,
                        }
                    )
                    continue
                if r1.status == QUARANTINED:
                    quarantined.append(f"{mig['id']}:{path.name}:{r1.reason}")
                if r1.status == TRANSFORMED:
                    transformed_first += 1

                sha1 = sha256_bytes(path.read_bytes())
                r2 = apply_file(path, mig)
                if r2.status == DROPPED or not path.exists():
                    dropped.append(f"{mig['id']}:{path.name}:second:{r2.reason}")
                    sha2 = None
                    unchanged = False
                else:
                    sha2 = sha256_bytes(path.read_bytes())
                    unchanged = sha1 == sha2
                    if r2.status == QUARANTINED:
                        quarantined.append(f"{mig['id']}:{path.name}:second:{r2.reason}")

                if was_from and r1.status == TRANSFORMED and sha0 == sha1:
                    progress_failures.append(f"{mig['id']}:{path.name}")
                if was_from and r1.status == NOOP:
                    progress_failures.append(f"{mig['id']}:{path.name}:noop-on-from-version")
                if sha2 is not None and not unchanged:
                    idem_failures.append(f"{mig['id']}:{path.name}")

                if (
                    was_from
                    and r1.status == TRANSFORMED
                    and path.exists()
                ):
                    try:
                        obj1 = json.loads(path.read_bytes().decode("utf-8"))
                    except (UnicodeDecodeError, ValueError):
                        obj1 = None
                    if obj1 is not None and not still_validates(obj1, to_v):
                        obligation_failures.append(
                            f"{mig['id']}:{path.name}:not-valid-as-{to_v}"
                        )

                double_apply.append(
                    {
                        "migration_id": mig["id"],
                        "artifact": path.name,
                        "from_version": from_v,
                        "to_version": to_v,
                        "was_from_version": was_from,
                        "sha_before": sha0,
                        "sha_after_first": sha1,
                        "sha_after_second": sha2,
                        "status_first": r1.status,
                        "status_second": r2.status,
                        "second_run_unchanged": unchanged,
                        "first_run_mutated": sha0 != sha1,
                        "dropped": False,
                    }
                )

        file_count_end = sum(1 for p in root.rglob("*") if p.is_file())

    rules = {
        "coverage": {
            "ok": coverage_ok,
            "declared_transitions": [f"{a}->{b}" for a, b in declared],
            "missing": missing,
        },
        "first-apply-progress": {
            "ok": not progress_failures,
            "failures": progress_failures,
        },
        "idempotence": {
            "ok": not idem_failures,
            "failures": idem_failures,
        },
        "quarantine-no-drop": {
            "ok": not dropped,
            "dropped": dropped,
            "quarantined": quarantined,
        },
        "transformation-obligation": {
            "ok": not obligation_failures,
            "failures": obligation_failures,
        },
    }
    ok = all(r["ok"] for r in rules.values())
    return {
        "ok": ok,
        "registry_id": registry.get("id"),
        "scratch_prefix": "TST-0047-",
        "file_count_start": file_count_start,
        "file_count_end": file_count_end,
        "migrations_run": [m["id"] for m in ordered],
        "transformed_first": transformed_first,
        "double_apply": double_apply,
        "rules": rules,
        "sources": [dest for _, dest in sources],
    }
