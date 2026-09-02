#!/usr/bin/env python3
"""Launcher and schema freeze gate (TST-0026).

A freeze snapshot records path, sha256, and schema_version for every frozen
launcher and schema. A later edit of a frozen file is accepted only when BOTH:

  1. a migration entry matches path + from_sha256 + to_sha256
  2. schema_version on the candidate is strictly greater than the freeze version

Unchanged frozen files stay green. Paths outside the freeze set are ignored, so
a non-frozen edit cannot trip the gate (both-states control).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

UNIT = "TST-0026"

# Live freeze set: every JSON Schema the program validates against, plus the
# wave launchers that would otherwise be editable mid-run.
LIVE_SCHEMA_DIRS = (
    "command-center/schema",
    "tools/plugin/schema",
    "tools/marketplace/schema",
)
LIVE_LAUNCHERS = (
    "command-center/p2-wave/seed-stage/dispatch_cursor.py",
    "command-center/p2-wave/seed-stage/bringup_cursor_fleet.py",
)

FIXTURE_FROZEN = (
    "launchers/fanout.py",
    "schemas/unit.schema.json",
    "schemas/launcher.schema.json",
)

_PY_VER = re.compile(
    r"^(?:SCHEMA_VERSION|schema_version)\s*=\s*(\d+)\s*(?:#.*)?$",
    re.MULTILINE,
)
_SH_VER = re.compile(
    r"^(?:export\s+)?SCHEMA_VERSION\s*=\s*(\d+)\s*(?:#.*)?$",
    re.MULTILINE,
)


def posix(rel: str) -> str:
    return str(rel).replace("\\", "/").strip().lstrip("./")


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    normalized = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest(), len(normalized)


def extract_schema_version(path: Path, raw: bytes | None = None) -> tuple[int, str]:
    """Return (version, how-it-was-read). Default 1 when the file has no marker."""
    blob = path.read_bytes() if raw is None else raw
    text = blob.decode("utf-8", errors="replace")
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            return 1, "json-unparseable-defaulted"
        if isinstance(doc, dict):
            for key in ("schema_version", "x-schema-version"):
                val = doc.get(key)
                if isinstance(val, bool):
                    continue
                if isinstance(val, int) and val >= 1:
                    return val, f"json:{key}"
                if isinstance(val, str) and val.isdigit() and int(val) >= 1:
                    return int(val), f"json:{key}:str"
        return 1, "json-absent-defaulted"
    if suffix == ".py":
        m = _PY_VER.search(text)
        if m:
            return int(m.group(1)), "python-assignment"
        return 1, "python-absent-defaulted"
    if suffix in {".sh", ".bash"}:
        m = _SH_VER.search(text)
        if m:
            return int(m.group(1)), "shell-assignment"
        return 1, "shell-absent-defaulted"
    return 1, "unknown-type-defaulted"


def freeze_set_hash(entries: Sequence[Mapping[str, Any]]) -> str:
    """Single digest over the ordered (path, sha256) pairs. Not a concat of files."""
    h = hashlib.sha256()
    for entry in sorted(entries, key=lambda e: posix(str(e.get("path") or ""))):
        h.update(posix(str(entry.get("path") or "")).encode("utf-8"))
        h.update(b"\0")
        h.update(str(entry.get("sha256") or "").encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def snapshot_paths(root: Path, rels: Iterable[str]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    missing: list[str] = []
    for rel in sorted({posix(r) for r in rels}):
        path = root / rel
        if not path.is_file():
            missing.append(rel)
            continue
        sha, size = digest_file(path)
        ver, how = extract_schema_version(path)
        files.append(
            {
                "path": rel,
                "sha256": sha,
                "bytes": size,
                "schema_version": ver,
                "version_source": how,
            }
        )
    return {
        "files": files,
        "missing": missing,
        "freeze_set_hash": freeze_set_hash(files),
        "file_count": len(files),
    }


def live_freeze_rels(repo: Path) -> list[str]:
    rels: list[str] = []
    for drel in LIVE_SCHEMA_DIRS:
        d = repo / drel
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            if path.is_file():
                rels.append(path.relative_to(repo).as_posix())
    for rel in LIVE_LAUNCHERS:
        if (repo / rel).is_file():
            rels.append(posix(rel))
    return sorted(set(rels))


def live_snapshot(repo: Path) -> dict[str, Any]:
    snap = snapshot_paths(repo, live_freeze_rels(repo))
    snap["kind"] = "live-repo"
    snap["schema_dirs"] = list(LIVE_SCHEMA_DIRS)
    snap["launchers"] = [r for r in LIVE_LAUNCHERS if (repo / r).is_file()]
    return snap


def find_migration(
    migrations: Sequence[Mapping[str, Any]],
    *,
    path: str,
    from_sha256: str,
    to_sha256: str,
) -> Mapping[str, Any] | None:
    want = posix(path)
    for row in migrations:
        if not isinstance(row, Mapping):
            continue
        if posix(str(row.get("path") or "")) != want:
            continue
        if str(row.get("from_sha256") or "") != from_sha256:
            continue
        if str(row.get("to_sha256") or "") != to_sha256:
            continue
        return row
    return None


def evaluate(
    freeze: Mapping[str, Any],
    candidate_root: Path,
    migrations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare candidate_root against freeze. migrations may be empty."""
    rows: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    ledger = list(migrations or [])
    for entry in freeze.get("files") or []:
        rel = posix(str(entry.get("path") or ""))
        freeze_sha = str(entry.get("sha256") or "")
        freeze_ver = int(entry.get("schema_version") or 1)
        path = candidate_root / rel
        rec: dict[str, Any] = {
            "path": rel,
            "freeze_sha256": freeze_sha,
            "freeze_schema_version": freeze_ver,
        }
        if not path.is_file():
            rec["status"] = "MISSING"
            rec["reason"] = "frozen-file-absent"
            rows.append(rec)
            rejections.append(rec)
            continue
        live_sha, live_bytes = digest_file(path)
        live_ver, how = extract_schema_version(path)
        rec["live_sha256"] = live_sha
        rec["live_bytes"] = live_bytes
        rec["live_schema_version"] = live_ver
        rec["version_source"] = how
        if live_sha == freeze_sha:
            rec["status"] = "UNCHANGED"
            rec["reason"] = "hash-match"
            rows.append(rec)
            continue
        mig = find_migration(
            ledger, path=rel, from_sha256=freeze_sha, to_sha256=live_sha
        )
        bumped = live_ver > freeze_ver
        rec["migration_matched"] = mig is not None
        rec["schema_version_bumped"] = bumped
        if mig is None and not bumped:
            rec["status"] = "REJECTED"
            rec["reason"] = "unmigrated-no-version-bump"
        elif mig is None:
            rec["status"] = "REJECTED"
            rec["reason"] = "version-bump-without-migration"
        elif not bumped:
            rec["status"] = "REJECTED"
            rec["reason"] = "migration-without-version-bump"
        else:
            rec["status"] = "ACCEPTED"
            rec["reason"] = "migrated-with-version-bump"
            rec["migration_id"] = mig.get("id")
            rows.append(rec)
            accepted.append(rec)
            continue
        rows.append(rec)
        rejections.append(rec)
    return {
        "ok": not rejections,
        "rejected": bool(rejections),
        "rejections": rejections,
        "accepted": accepted,
        "rows": rows,
        "freeze_set_hash": freeze.get("freeze_set_hash"),
        "migration_count": len(ledger),
    }


def bump_json_schema_version(path: Path, new_version: int) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path} is not a JSON object")
    doc["schema_version"] = new_version
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bump_python_schema_version(path: Path, new_version: int) -> None:
    text = path.read_text(encoding="utf-8")
    new, n = _PY_VER.subn(f"SCHEMA_VERSION = {new_version}", text, count=1)
    if n != 1:
        raise ValueError(f"{path} has no SCHEMA_VERSION assignment")
    path.write_text(new, encoding="utf-8")


def mutate_json_add_property(path: Path, name: str = "x_unmigrated") -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path} is not a JSON object")
    props = doc.setdefault("properties", {})
    if not isinstance(props, dict):
        raise ValueError(f"{path} properties is not an object")
    props[name] = {"type": "string"}
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def receipt_freeze_hash(doc: Mapping[str, Any]) -> str:
    """Live freeze-set hash from a schema-valid or legacy receipt."""
    fs = doc.get("frozen_set")
    if not isinstance(fs, dict):
        fs = _as_dict(doc.get("extensions")).get("frozen_set")
    if not isinstance(fs, dict):
        return ""
    return str(fs.get("hash") or "")


def receipt_check_verdict(doc: Mapping[str, Any], check_id: str) -> str | None:
    rows: list[Any] = []
    for blob in (
        doc.get("checks"),
        _as_dict(doc.get("extensions")).get("checks"),
        doc.get("tests"),
    ):
        if isinstance(blob, list):
            rows.extend(blob)
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("id") != check_id:
            continue
        verdict = row.get("verdict") or row.get("result")
        if verdict is None:
            return None
        return str(verdict)
    return None


def receipt_both_states(doc: Mapping[str, Any]) -> bool:
    ev = doc.get("evidence")
    if isinstance(ev, dict) and ev.get("unmigrated_rejected") and ev.get("migrated_accepted"):
        return True
    ext = _as_dict(doc.get("extensions"))
    for blob in (
        ext.get("evidence_flags"),
        ext.get("fixture_demonstration"),
        doc.get("fixture_demonstration"),
    ):
        if isinstance(blob, dict) and blob.get("unmigrated_rejected") and blob.get(
            "migrated_accepted"
        ):
            return True
    unmigrated = receipt_check_verdict(doc, "test_unmigrated_schema_change_is_rejected")
    migrated = receipt_check_verdict(
        doc, "test_migrated_change_with_version_bump_is_accepted"
    )
    return unmigrated == "PASS" and migrated == "PASS"
