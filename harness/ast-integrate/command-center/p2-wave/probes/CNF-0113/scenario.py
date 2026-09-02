#!/usr/bin/env python3
"""Shared fixture list and expected verdicts for CNF-0113."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGES = HERE / "fixtures" / "packages"

FIXTURES: list[dict[str, str | None]] = [
    {
        "id": "excessive-permissions",
        "dir": "excessive-permissions",
        "kind": "hostile",
        "expected_disposition": "reject",
        "expected_rule": "MP-PERM-EXCESSIVE",
    },
    {
        "id": "postinstall-network",
        "dir": "postinstall-network",
        "kind": "hostile",
        "expected_disposition": "reject",
        "expected_rule": "MP-POSTINSTALL-NETWORK",
    },
    {
        "id": "path-traversal",
        "dir": "path-traversal",
        "kind": "hostile",
        "expected_disposition": "reject",
        "expected_rule": "MP-PATH-TRAVERSAL",
    },
    {
        "id": "typosquat-harness",
        "dir": "typosquat-harness",
        "kind": "hostile",
        "expected_disposition": "reject",
        "expected_rule": "MP-TYPOSQUAT",
    },
    {
        "id": "unsigned-publisher",
        "dir": "unsigned-publisher",
        "kind": "hostile",
        "expected_disposition": "warn",
        "expected_rule": "MP-UNSIGNED-PUBLISHER",
    },
    {
        "id": "benign-control",
        "dir": "benign-control",
        "kind": "control",
        "expected_disposition": "pass",
        "expected_rule": None,
    },
]


def package_dir(fx: dict) -> Path:
    return PACKAGES / str(fx["dir"])


def domain_get(doc: dict, key: str, default=None):
    """Read a domain field from a receipt (top-level, report, or extensions)."""
    if not isinstance(doc, dict):
        return default
    if key in doc:
        return doc[key]
    report = doc.get("report")
    if isinstance(report, dict) and key in report:
        return report[key]
    ext = doc.get("extensions")
    if isinstance(ext, dict) and key in ext:
        return ext[key]
    return default
