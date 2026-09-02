#!/usr/bin/env python3
"""Marketplace-conformance blueprint (B07 phase-6 listing linter).

Version on the listing must match plugin.json (silent plugin.json-wins is
the ship-nothing trap). Evidence must be a ledger reference, not free text,
and must resolve in the results ledger.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVIDENCE_KEYS = ("run_id", "case_set_id", "harness_version", "commit_sha")


def _fail(rule: str, detail: str) -> dict[str, Any]:
    return {"ok": False, "rule_id": rule, "detail": detail}


def lint_listing(
    listing: dict[str, Any],
    plugin_manifest: dict[str, Any],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(listing, dict):
        return _fail("MKT-LISTING-NOT-OBJECT", "listing is not an object")
    for key in ("plugin_id", "name", "version", "category"):
        if not str(listing.get(key) or "").strip():
            return _fail("MKT-FIELD-MISSING", key)
    plugin_id = listing.get("plugin_id")
    if plugin_manifest.get("name") and plugin_id not in {
        plugin_manifest.get("name"),
        plugin_manifest.get("id"),
        f"plugin.{plugin_manifest.get('name')}",
    }:
        # allow either bare name or plugin.<name>
        if plugin_id != plugin_manifest.get("id"):
            return _fail(
                "MKT-PLUGIN-ID-MISMATCH",
                f"listing.plugin_id={plugin_id} plugin.id={plugin_manifest.get('id')}",
            )
    lv = str(listing.get("version") or "")
    pv = str(plugin_manifest.get("version") or "")
    if lv != pv:
        return _fail("MKT-VERSION-DISAGREE", f"listing={lv} plugin={pv}")
    evidence = listing.get("evidence")
    if isinstance(evidence, str):
        return _fail("MKT-EVIDENCE-FREE-TEXT", "evidence must be a ledger reference object")
    if not isinstance(evidence, dict):
        return _fail("MKT-EVIDENCE-MISSING", "evidence object required")
    missing = [k for k in EVIDENCE_KEYS if not str(evidence.get(k) or "").strip()]
    if missing:
        return _fail("MKT-EVIDENCE-INCOMPLETE", ",".join(missing))
    runs = ledger.get("runs") if isinstance(ledger, dict) else None
    if not isinstance(runs, dict):
        return _fail("MKT-LEDGER-ABSENT", "results ledger has no runs map")
    rec = runs.get(evidence["run_id"])
    if not isinstance(rec, dict):
        return _fail("MKT-EVIDENCE-UNRESOLVED", evidence["run_id"])
    if rec.get("case_set_id") != evidence["case_set_id"]:
        return _fail("MKT-EVIDENCE-UNRESOLVED", "case_set_id does not resolve")
    if rec.get("harness_version") != evidence["harness_version"]:
        return _fail("MKT-EVIDENCE-UNSUPPORTED-HARNESS", str(evidence["harness_version"]))
    if rec.get("commit_sha") != evidence["commit_sha"]:
        return _fail("MKT-EVIDENCE-UNRESOLVED", "commit_sha does not resolve")
    return {
        "ok": True,
        "rule_id": None,
        "detail": "listing-accepted",
        "plugin_id": listing.get("plugin_id"),
        "version": lv,
        "evidence_run_id": evidence["run_id"],
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def smoke() -> dict[str, Any]:
    return {"ok": True, "blueprint": "marketplace-conformance"}
