"""Pre-ship output-fingerprint gate for A2 generator templates.

The gate compares generate() bytes to a dual-reviewed pin. It is NOT a
hash of generator.py source (whitespace-only edits would be too noisy).
Missing pin, missing authorizers, or missing provenance fail CLOSED.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fingerprint import fingerprint
from ownership import REQUIRED_AUTHORIZERS

PROVENANCE_KEYS = ("registry_id", "generator_version")


def load_pin(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file() or path.stat().st_size <= 0:
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _provenance_missing(files: dict[str, bytes], parse_provenance) -> list[str]:
    missing: list[str] = []
    for rel, raw in sorted(files.items()):
        prov = parse_provenance(raw)
        if not isinstance(prov, dict):
            missing.append(rel)
            continue
        for key in PROVENANCE_KEYS:
            if not str(prov.get(key) or "").strip():
                missing.append(rel)
                break
    return missing


def check(
    files: dict[str, bytes],
    pin: dict[str, Any] | None,
    parse_provenance,
) -> dict[str, Any]:
    """Return a gate verdict. tripped means do-not-ship."""
    fp = fingerprint(files)
    if pin is None:
        return {
            "tripped": True,
            "fail_closed": True,
            "reason": "pin-absent",
            "tree_sha256": fp["tree_sha256"],
            "pin_tree_sha256": None,
            "files_changed": sorted(files),
            "missing_provenance": _provenance_missing(files, parse_provenance),
            "authorizers_ok": False,
            "file_count": fp["file_count"],
        }

    authorizers = pin.get("authorized_by") or []
    if not isinstance(authorizers, list):
        authorizers = []
    have = {str(x) for x in authorizers}
    authorizers_ok = all(a in have for a in REQUIRED_AUTHORIZERS)
    missing_prov = _provenance_missing(files, parse_provenance)
    pin_tree = str(pin.get("tree_sha256") or "")
    pin_files = {
        str(row.get("path")): str(row.get("sha256"))
        for row in (pin.get("files") or [])
        if isinstance(row, dict)
    }
    live_files = {row["path"]: row["sha256"] for row in fp["files"]}
    changed = sorted(
        p
        for p in sorted(set(pin_files) | set(live_files))
        if pin_files.get(p) != live_files.get(p)
    )

    if not authorizers_ok:
        return {
            "tripped": True,
            "fail_closed": True,
            "reason": "authorizers-missing",
            "tree_sha256": fp["tree_sha256"],
            "pin_tree_sha256": pin_tree or None,
            "files_changed": changed,
            "missing_provenance": missing_prov,
            "authorizers_ok": False,
            "file_count": fp["file_count"],
        }
    if missing_prov:
        return {
            "tripped": True,
            "fail_closed": True,
            "reason": "provenance-missing",
            "tree_sha256": fp["tree_sha256"],
            "pin_tree_sha256": pin_tree or None,
            "files_changed": changed,
            "missing_provenance": missing_prov,
            "authorizers_ok": True,
            "file_count": fp["file_count"],
        }
    if not pin_tree or pin_tree != fp["tree_sha256"]:
        return {
            "tripped": True,
            "fail_closed": True,
            "reason": "output-fingerprint-mismatch",
            "tree_sha256": fp["tree_sha256"],
            "pin_tree_sha256": pin_tree or None,
            "files_changed": changed,
            "missing_provenance": [],
            "authorizers_ok": True,
            "file_count": fp["file_count"],
        }
    return {
        "tripped": False,
        "fail_closed": True,
        "reason": "match",
        "tree_sha256": fp["tree_sha256"],
        "pin_tree_sha256": pin_tree,
        "files_changed": [],
        "missing_provenance": [],
        "authorizers_ok": True,
        "file_count": fp["file_count"],
    }


def check_pin_file(
    files: dict[str, bytes], pin_path: Path | None, parse_provenance
) -> dict[str, Any]:
    return check(files, load_pin(pin_path), parse_provenance)
