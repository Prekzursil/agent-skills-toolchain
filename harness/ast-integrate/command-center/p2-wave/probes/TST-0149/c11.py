#!/usr/bin/env python3
"""Condition 11: registration must be read from a manifest FILE on disk.

Live matching rule is the G-1 per-unit row check in
command-center/p2-wave/_measure_one_delivered.py (path + sha256 + present=True).
unit_manifest.derive() is the writer's in-memory index: trusting it without a
persisted manifest is the negative control this unit must reject.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_unit_manifest_mod():
    path = REPO / "tools" / "command-center" / "unit_manifest.py"
    spec = importlib.util.spec_from_file_location("unit_manifest_tst0149", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def shared_predicate_path() -> Path:
    return REPO / "platform" / "lib" / "completion_predicate.py"


def artifact_preconditions(path: Path, sentinel: str) -> dict[str, Any]:
    exists = path.is_file() and path.stat().st_size > 0
    parses = False
    sentinel_present = False
    detail: dict[str, Any] = {"path": str(path), "bytes": 0}
    if exists:
        raw = path.read_bytes()
        detail["bytes"] = len(raw)
        try:
            text = raw.decode("utf-8")
            json.loads(text)
            parses = True
            sentinel_present = sentinel in text
        except (UnicodeDecodeError, json.JSONDecodeError):
            parses = False
    return {
        "exists": exists,
        "parses": parses,
        "sentinel_present": sentinel_present,
        "detail": detail,
    }


def c11_from_disk_manifest(
    manifest_path: Path,
    *,
    unit_id: str,
    artifact_rel: str,
    live_sha256: str,
) -> dict[str, Any]:
    """Read the manifest FILE. Never consult a writer return value."""
    out_rel = artifact_rel.replace("\\", "/")
    basis = {
        "manifest_path": str(manifest_path),
        "manifest_exists": manifest_path.is_file(),
        "unit_id": unit_id,
        "artifact_rel": out_rel,
        "live_sha256": live_sha256,
        "matching_rows": 0,
        "unit_rows": 0,
    }
    if not manifest_path.is_file():
        return {
            "outcome": "UNSATISFIED",
            "basis": "manifest file absent on disk",
            "detail": basis,
        }
    try:
        doc = load_json(manifest_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "outcome": "UNSATISFIED",
            "basis": f"manifest unparseable:{type(exc).__name__}",
            "detail": basis,
        }
    artifacts = doc.get("artifacts") if isinstance(doc, dict) else None
    if not isinstance(artifacts, list):
        return {
            "outcome": "UNSATISFIED",
            "basis": "manifest has no artifacts list",
            "detail": basis,
        }
    rows = [
        a
        for a in artifacts
        if isinstance(a, dict) and a.get("unit_id") == unit_id
    ]
    basis["unit_rows"] = len(rows)
    matching = [
        a
        for a in rows
        if str(a.get("path") or "").replace("\\", "/") == out_rel
        and str(a.get("sha256") or "") == live_sha256
        and a.get("present") is True
    ]
    basis["matching_rows"] = len(matching)
    if matching:
        return {
            "outcome": "SATISFIED",
            "basis": "disk manifest row matches path+sha256+present",
            "detail": basis,
        }
    return {
        "outcome": "UNSATISFIED",
        "basis": (
            "artifact exists on disk but is not registered in the "
            "on-disk manifest (condition 11)"
        ),
        "detail": basis,
    }


def c11_trust_writer(writer_return: dict[str, Any]) -> dict[str, Any]:
    """Negative control: trust the writer's in-memory registered flag."""
    claimed = bool(writer_return.get("registered"))
    return {
        "outcome": "SATISFIED" if claimed else "UNSATISFIED",
        "basis": "writer_return.registered (in-memory; not a disk read)",
        "detail": {
            "registered": writer_return.get("registered"),
            "source": "writer_return",
        },
    }


def c11_from_in_memory_derive(
    derived: dict[str, Any],
    *,
    unit_id: str,
    artifact_rel: str,
    live_sha256: str,
) -> dict[str, Any]:
    """Treat derive() output as the writer's in-memory claim."""
    fake = {
        "schema_version": 1,
        "artifacts": list(derived.get("artifacts") or []),
    }
    tmp_parent = Path(sys.modules[__name__].__file__).resolve().parent
    # Evaluate against the in-memory object without a file: reuse matching.
    out_rel = artifact_rel.replace("\\", "/")
    rows = [
        a
        for a in fake["artifacts"]
        if isinstance(a, dict) and a.get("unit_id") == unit_id
    ]
    matching = [
        a
        for a in rows
        if str(a.get("path") or "").replace("\\", "/") == out_rel
        and str(a.get("sha256") or "") == live_sha256
        and a.get("present") is True
    ]
    _ = tmp_parent
    if matching:
        return {
            "outcome": "SATISFIED",
            "basis": "in-memory unit_manifest.derive() claim (not a disk read)",
            "detail": {"matching_rows": len(matching), "unit_rows": len(rows)},
        }
    return {
        "outcome": "UNSATISFIED",
        "basis": "in-memory derive() has no matching row",
        "detail": {"matching_rows": 0, "unit_rows": len(rows)},
    }


def condition_vector(
    *,
    pre: dict[str, Any],
    c11: dict[str, Any],
) -> list[dict[str, Any]]:
    def flag(ok: bool, n: int, name: str, basis: str) -> dict[str, Any]:
        return {
            "n": n,
            "name": name,
            "outcome": "SATISFIED" if ok else "UNSATISFIED",
            "basis": basis,
        }

    return [
        flag(True, 1, "terminal-state", "fixture constructed as SUCCESS"),
        flag(pre["exists"], 2, "artifact-exists", "stat() of fixture artifact"),
        flag(
            pre["exists"] and pre["detail"]["bytes"] > 0,
            3,
            "non-empty",
            f"bytes={pre['detail']['bytes']}",
        ),
        flag(pre["parses"], 4, "parses", "json.loads of fixture artifact"),
        flag(pre["sentinel_present"], 5, "sentinel", "verbatim sentinel membership"),
        flag(True, 6, "evidence-anchors", "N/A-for-this-condition-11-unit"),
        flag(True, 7, "tests-ran", "N/A-for-this-condition-11-unit"),
        flag(True, 8, "negative-controls", "N/A-for-this-condition-11-unit"),
        flag(True, 9, "reviewer", "N/A-for-this-condition-11-unit"),
        flag(True, 10, "no-p0-p1", "N/A-for-this-condition-11-unit"),
        {
            "n": 11,
            "name": "manifest-registration",
            "outcome": c11["outcome"],
            "basis": c11["basis"],
            "detail": c11.get("detail"),
        },
        flag(True, 12, "downstream-read", "N/A-for-this-condition-11-unit"),
    ]


def live_evaluate(receipt: dict[str, Any], root: Path, output_schema: str | None = None) -> dict[str, Any]:
    unit_id = str(receipt.get("unit_id") or "")
    arts = receipt.get("artifacts") or []
    art_rel = str((arts[0] or {}).get("path") or "") if arts else ""
    art_path = root / art_rel
    sentinel = str(receipt.get("sentinel") or receipt.get("completion_sentinel") or "")
    pre = artifact_preconditions(art_path, sentinel)
    live_sha = ""
    if art_path.is_file():
        live_sha, _n = digest_file(art_path)
    c11 = c11_from_disk_manifest(
        root / "command-center/ARTIFACT-MANIFEST.json",
        unit_id=unit_id,
        artifact_rel=art_rel,
        live_sha256=live_sha,
    )
    vector = condition_vector(pre=pre, c11=c11)
    by_n = {row["n"]: row for row in vector}
    return {
        "reducer_id": "c11-disk-manifest",
        "c2": by_n[2],
        "c4": by_n[4],
        "c5": by_n[5],
        "c11": c11,
        "conditions": vector,
        "preconditions": pre,
        "output_schema": output_schema,
    }
