#!/usr/bin/env python3
"""Plugin-conformance blueprint implementation (B07 phase-5/6 linter).

Rejects: install-time scripts, excessive permissions, platform-field shadowing,
path escape from package root, declared-vs-actual contents mismatch.
A benign package must pass (reject-everything is not conformance).
"""
from __future__ import annotations

import json
import posixpath
import zipfile
from pathlib import Path
from typing import Any

PLATFORM_SHADOW_KEYS = frozenset(
    {"env", "PATH", "HOME", "commands", "runtime", "platform", "CLAUDE_CONFIG"}
)
EXCESSIVE_PERMS = frozenset({"*", "all", "unrestricted", "filesystem:write-any", "root"})
INSTALL_HOOK_KEYS = frozenset({"install", "postinstall", "preinstall", "install_script"})
REQUIRED_MANIFEST = ("name", "version", "description")


def _fail(rule: str, detail: str) -> dict[str, Any]:
    return {"ok": False, "rule_id": rule, "detail": detail}


def _zip_names(package: Path) -> list[str]:
    with zipfile.ZipFile(package) as zf:
        return [n for n in zf.namelist() if not n.endswith("/")]


def _read_manifest(package: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    with zipfile.ZipFile(package) as zf:
        names = zf.namelist()
        cand = None
        for n in names:
            base = posixpath.basename(n)
            if base == "plugin.json" and not n.endswith("/"):
                cand = n
                break
        if cand is None:
            return None, _fail("PLUGIN-MANIFEST-ABSENT", "plugin.json missing from package")
        raw = zf.read(cand)
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, _fail("PLUGIN-MANIFEST-UNPARSEABLE", type(exc).__name__)
    if not isinstance(doc, dict):
        return None, _fail("PLUGIN-MANIFEST-NOT-OBJECT", "plugin.json root is not an object")
    return doc, None


def lint_package(package: Path) -> dict[str, Any]:
    """Lint a packaged plugin artifact. Never inspects the live plugin tree."""
    if not package.is_file():
        return _fail("PLUGIN-PACKAGE-ABSENT", package.as_posix())
    names = _zip_names(package)
    for n in names:
        norm = posixpath.normpath(n)
        if n.startswith("/") or norm.startswith("..") or "/../" in f"/{n}/":
            return _fail("PLUGIN-PATH-ESCAPE", n)
    manifest, err = _read_manifest(package)
    if err:
        return err
    assert manifest is not None
    for key in REQUIRED_MANIFEST:
        if not str(manifest.get(key) or "").strip():
            return _fail("PLUGIN-FIELD-MISSING", key)
    extra_top = set(manifest) & PLATFORM_SHADOW_KEYS
    if extra_top:
        return _fail("PLUGIN-PLATFORM-SHADOW", ",".join(sorted(extra_top)))
    scripts = manifest.get("scripts")
    if isinstance(scripts, dict) and (set(scripts) & INSTALL_HOOK_KEYS):
        return _fail("PLUGIN-INSTALL-SCRIPT", "scripts contains an install-time hook")
    if any(k in manifest for k in INSTALL_HOOK_KEYS):
        return _fail("PLUGIN-INSTALL-SCRIPT", "top-level install-time hook")
    perms = manifest.get("permissions") or []
    if isinstance(perms, str):
        perms = [perms]
    if isinstance(perms, list):
        for p in perms:
            if str(p) in EXCESSIVE_PERMS:
                return _fail("PLUGIN-EXCESSIVE-PERMISSION", str(p))
    declared = manifest.get("files")
    if isinstance(declared, list):
        actual = set(names)
        missing = [d for d in declared if isinstance(d, str) and d not in actual]
        extra_required = [d for d in declared if isinstance(d, str)]
        if missing:
            return _fail("PLUGIN-DECLARED-ACTUAL-MISMATCH", f"declared-missing:{missing}")
        undeclared = sorted(actual - set(extra_required) - {"plugin.json"})
        # mismatch is declared-vs-actual when the declared list is the contract
        if set(extra_required) != actual and "plugin.json" in actual:
            if set(extra_required) | {"plugin.json"} != actual and set(extra_required) != actual:
                return _fail(
                    "PLUGIN-DECLARED-ACTUAL-MISMATCH",
                    f"undeclared:{undeclared} missing:{missing}",
                )
    return {
        "ok": True,
        "rule_id": None,
        "detail": "benign-plugin-accepted",
        "name": manifest.get("name"),
        "version": manifest.get("version"),
        "files": names,
    }


def smoke() -> dict[str, Any]:
    return {"ok": True, "blueprint": "plugin-conformance"}
