#!/usr/bin/env python3
"""In-place schema_version migrator for the TST-0047 conformance suite.

Written as the executable contract (tests before a production plugin migrator).
Apply is measured on a disposable tree: the engine writes the target file, and
the suite copies artifacts into tempfile first so repo bytes never move.

Idempotence rule: if the artifact already satisfies the migration's
postconditions, do not rewrite. A second apply must leave bytes unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TRANSFORMED = "TRANSFORMED"
NOOP = "NOOP"
QUARANTINED = "QUARANTINED"
DROPPED = "DROPPED"

FORMAT_FAMILY = "ast-integrate-json-v2"
EPOCH_V3 = "v3"
CANONICAL_ENCODING = "canonical-json-v1"


def canonical_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def consecutive_transitions(versions: list[int]) -> list[tuple[int, int]]:
    vs = sorted(set(int(v) for v in versions))
    return [(vs[i], vs[i + 1]) for i in range(len(vs) - 1)]


def postconditions_hold(obj: dict[str, Any], migration: dict[str, Any]) -> bool:
    wanted = migration.get("postconditions") or {
        "schema_version": migration["to_version"]
    }
    for key, value in wanted.items():
        if obj.get(key) != value:
            return False
    return True


def still_validates(obj: Any, version: int) -> bool:
    if not isinstance(obj, dict):
        return False
    if obj.get("schema_version") != version:
        return False
    if version == 2:
        return obj.get("format_family") == FORMAT_FAMILY
    if version == 3:
        return obj.get("format_family") == FORMAT_FAMILY and obj.get("epoch") == EPOCH_V3
    return True


def _apply_steps(obj: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any] | str:
    out = copy.deepcopy(obj)
    for i, step in enumerate(steps):
        op = step.get("op")
        path = step.get("path")
        if not isinstance(op, str) or not isinstance(path, str) or not path:
            return f"malformed-step:{i}"
        if "/" in path or path.startswith("#"):
            return f"nested-path-unsupported:{path}"
        if op == "set":
            if path not in out:
                return f"set-missing:{path}"
            out[path] = copy.deepcopy(step.get("value"))
        elif op == "add":
            if path in out:
                return f"add-exists:{path}"
            out[path] = copy.deepcopy(step.get("value"))
        elif op == "remove":
            if path not in out:
                return f"remove-missing:{path}"
            del out[path]
        else:
            return f"unknown-op:{op}"
    return out


def _is_done(obj: dict[str, Any], migration: dict[str, Any]) -> bool:
    if obj.get("schema_version") != migration["to_version"]:
        return False
    if migration.get("done_when") == "schema_version":
        return True
    return postconditions_hold(obj, migration)


@dataclass
class Outcome:
    status: str
    path: str
    reason: str | None = None
    sha_before: str | None = None
    sha_after: str | None = None
    wrote: bool = False
    report: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "path": self.path,
            "reason": self.reason,
            "sha_before": self.sha_before,
            "sha_after": self.sha_after,
            "wrote": self.wrote,
            "bytes_changed": (
                self.sha_before is not None
                and self.sha_after is not None
                and self.sha_before != self.sha_after
            ),
            "report": self.report,
        }


def _quarantine_dir(path: Path) -> Path:
    q = path.parent / "quarantine"
    q.mkdir(parents=True, exist_ok=True)
    return q


def _write_quarantine(path: Path, raw: bytes, reason: str) -> None:
    meta = {
        "action": "QUARANTINE",
        "path": path.name,
        "reason": reason,
        "silent_drop": False,
        "original_sha256": sha256_bytes(raw),
        "original_bytes": len(raw),
    }
    dest = _quarantine_dir(path) / f"{path.name}.reason.json"
    dest.write_bytes(canonical_bytes(meta))
    blob = _quarantine_dir(path) / f"{path.name}.original"
    blob.write_bytes(raw)


def apply_file(path: Path, migration: dict[str, Any]) -> Outcome:
    """Apply one migration to one file. Mutates `path` in place when transforming."""
    policy = str(
        (migration.get("untransformable_policy") or "QUARANTINE")
    ).upper()
    apply_mode = str(migration.get("apply_mode") or "idempotent")
    raw = path.read_bytes()
    sha_before = sha256_bytes(raw)

    def finish(
        status: str,
        *,
        reason: str | None = None,
        wrote: bool = False,
        sha_after: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Outcome:
        after = sha_after if sha_after is not None else sha256_bytes(path.read_bytes())
        return Outcome(
            status=status,
            path=path.name,
            reason=reason,
            sha_before=sha_before,
            sha_after=after,
            wrote=wrote,
            report={
                "action": status,
                "migration_id": migration.get("id"),
                "silent_drop": status == DROPPED,
                **(extra or {}),
            },
        )

    def refuse(reason: str) -> Outcome:
        if policy == "DROP":
            path.unlink()
            return finish(
                DROPPED,
                reason=reason,
                wrote=True,
                sha_after=sha_before,
                extra={"silent_drop": True},
            )
        _write_quarantine(path, raw, reason)
        return finish(QUARANTINED, reason=reason, wrote=False)

    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return refuse(f"unparseable:{type(exc).__name__}")
    if not isinstance(obj, dict):
        return refuse("not-an-object")
    if "schema_version" not in obj:
        return refuse("schema_version-absent")

    from_v = int(migration["from_version"])
    to_v = int(migration["to_version"])
    ver = obj.get("schema_version")

    if apply_mode == "always-mutate" and _is_done(obj, migration):
        stamped = copy.deepcopy(obj)
        stamped["_apply_n"] = int(stamped.get("_apply_n") or 0) + 1
        path.write_bytes(canonical_bytes(stamped))
        return finish(TRANSFORMED, wrote=True, extra={"apply_mode": apply_mode})

    if _is_done(obj, migration):
        return finish(NOOP, wrote=False)

    if apply_mode == "always-noop":
        return finish(NOOP, wrote=False, extra={"apply_mode": apply_mode})

    if ver != from_v:
        return refuse(f"schema_version-mismatch:have={ver}:want={from_v}")

    applied = _apply_steps(obj, list(migration.get("steps") or []))
    if isinstance(applied, str):
        return refuse(f"transform-failed:{applied}")
    if apply_mode == "always-mutate":
        applied["_apply_n"] = int(applied.get("_apply_n") or 0) + 1
    path.write_bytes(canonical_bytes(applied))
    return finish(
        TRANSFORMED,
        wrote=True,
        extra={"from_version": from_v, "to_version": applied.get("schema_version")},
    )


def good_migrations() -> list[dict[str, Any]]:
    return [
        {
            "id": "schema_version-1-to-2",
            "from_version": 1,
            "to_version": 2,
            "apply_mode": "idempotent",
            "untransformable_policy": "QUARANTINE",
            "done_when": "postconditions",
            "postconditions": {
                "schema_version": 2,
                "format_family": FORMAT_FAMILY,
            },
            "steps": [
                {"op": "set", "path": "schema_version", "value": 2},
                {"op": "add", "path": "format_family", "value": FORMAT_FAMILY},
            ],
        },
        {
            "id": "schema_version-2-to-3",
            "from_version": 2,
            "to_version": 3,
            "apply_mode": "idempotent",
            "untransformable_policy": "QUARANTINE",
            "done_when": "postconditions",
            "postconditions": {
                "schema_version": 3,
                "format_family": FORMAT_FAMILY,
                "epoch": EPOCH_V3,
            },
            "steps": [
                {"op": "set", "path": "schema_version", "value": 3},
                {"op": "add", "path": "epoch", "value": EPOCH_V3},
            ],
        },
    ]


def good_registry() -> dict[str, Any]:
    return {
        "id": "good",
        "schema_versions": [1, 2, 3],
        "migrations": good_migrations(),
    }
