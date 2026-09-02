#!/usr/bin/env python3
"""Honesty checks: NOT-CHECKED discipline, version sources, silent-not-pass."""
from __future__ import annotations

from typing import Any

import adapters as A
import clients as C

PASS_LIKE = frozenset({A.VERDICT_REPRODUCES})
LIVE_ALLOWED_WHEN_MISSING = frozenset({"NOT-CHECKED"})


def honesty_errors(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["artifact-not-object"]
    sentinel = str(doc.get("sentinel") or "")
    if "SUCCESS:CNF-0157" not in sentinel and "SUCCESS:CNF-0157" not in str(
        doc.get("answer") or ""
    ):
        errors.append("sentinel-absent")
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errors.append(f"self-declared:{state}")

    cells = doc.get("cells") or []
    if not isinstance(cells, list) or len(cells) < 32:
        errors.append(f"cell-count:{len(cells) if isinstance(cells, list) else 'n/a'}")
        return errors

    live = [c for c in cells if isinstance(c, dict) and c.get("surface") == "live-client"]
    fixture = [
        c for c in cells if isinstance(c, dict) and c.get("surface") == "adapter-fixture"
    ]
    if len(live) != 16 or len(fixture) != 16:
        errors.append(f"surface-split live={len(live)} fixture={len(fixture)}")

    for cell in live:
        cid = cell.get("id")
        vs = cell.get("version_source")
        if vs in C.FORBIDDEN_VERSION_SOURCES:
            errors.append(f"doc-version:{cid}")
        if vs == "not-installed":
            if cell.get("verdict") not in LIVE_ALLOWED_WHEN_MISSING:
                errors.append(f"uninstalled-folded-pass:{cid}:{cell.get('verdict')}")
            if cell.get("client_version"):
                errors.append(f"uninstalled-has-version:{cid}")
            if not str(cell.get("prerequisite") or "").strip():
                errors.append(f"uninstalled-prerequisite-missing:{cid}")
        if cell.get("verdict") in PASS_LIKE:
            errors.append(f"live-reproduces-without-in-client-proof:{cid}")

    for cell in fixture:
        if cell.get("version_source") != "adapter-fixture":
            errors.append(f"fixture-version-source:{cell.get('id')}")
        ver = str(cell.get("client_version") or "")
        if not ver.startswith("adapter-fixture/"):
            errors.append(f"fixture-version-string:{cell.get('id')}")

    silent_hook = [
        c
        for c in fixture
        if c.get("client_id") == "codex-cli"
        and c.get("claim_id") == "hook"
        and c.get("verdict") == A.VERDICT_SILENT
    ]
    if not silent_hook:
        errors.append("codex-hook-silent-not-recorded")

    loud_plugin = [
        c
        for c in fixture
        if c.get("client_id") == "mcp-generic"
        and c.get("claim_id") == "plugin"
        and c.get("verdict") == A.VERDICT_LOUD
    ]
    if not loud_plugin:
        errors.append("mcp-generic-plugin-not-loud")

    ix = doc.get("interchangeability") or {}
    if ix.get("verdict") != "REFUTED":
        errors.append("interchangeability-not-refuted")

    tests = doc.get("tests") or {}
    for key in (
        "known_broken",
        "loud_degradation",
        "both_states",
        "version_capture",
        "skill_router_11330",
    ):
        row = tests.get(key) or {}
        if row.get("pass") is not True:
            errors.append(f"test-failed:{key}")

    extra = (doc.get("discovery") or {}).get("extra_runtimes") or []
    for row in extra:
        if row.get("folded_into_matrix_pass") is True:
            errors.append("extra-runtime-folded-into-pass")
        if row.get("declared_supported_client") is True:
            errors.append("extra-runtime-declared")

    pkg = (doc.get("discovery") or {}).get("plugin_package") or {}
    present = list(pkg.get("production_paths_present") or [])
    absent = list(pkg.get("production_paths_absent") or [])
    adj = pkg.get("adjacent_tools_plugin") or {}
    if not isinstance(adj, dict) or "exists" not in adj:
        errors.append("adjacent-tools-plugin-unrecorded")
    if pkg.get("production_present") is True and not present:
        errors.append("production-present-without-paths")
    if pkg.get("production_present") is not True and present:
        errors.append("production-absent-with-present-paths")
    if "tools/plugin" in absent and "tools/plugin" in present:
        errors.append("tools-plugin-both-present-and-absent")
    if adj.get("exists") is True and "tools/plugin" in absent:
        errors.append("tools-plugin-listed-absent-while-adjacent-exists")
    if adj.get("is_loadable_plugin_package") is True and "tools/plugin" not in present:
        errors.append("loadable-tools-plugin-not-in-production-present")
    if (
        adj.get("exists") is True
        and adj.get("is_loadable_plugin_package") is not True
        and "tools/plugin" in present
    ):
        errors.append("toolkit-folded-into-production-plugin")

    return errors


def check(doc: dict[str, Any]) -> tuple[bool, str]:
    errs = honesty_errors(doc)
    if errs:
        return False, ";".join(errs)
    return True, "ok"
