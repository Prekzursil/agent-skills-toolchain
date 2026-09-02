#!/usr/bin/env python3
"""Probe 1: every capability has a pinned factual basis; quotes exist in FR captures.

Recomputes inventory hashes. Does not assign ECCNs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from inventory import detect  # noqa: E402
from lib import (  # noqa: E402
    ART,
    CLASSES,
    DISPOSITIONS,
    NO_LEGAL,
    OVERCLAIM,
    SENTINEL,
    UNIT_ID,
    load_json,
    sha256_path,
)
from sources import QUOTES, assert_quotes_in_captures  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe1 {msg}")
    return 1


def main() -> int:
    missing = assert_quotes_in_captures()
    if missing:
        return fail(f"quote-span-absent:{missing}")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    doc = load_json(ART)
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if NO_LEGAL not in text:
        return fail("no-legal-conclusion-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    caps = doc.get("capabilities") or []
    if not isinstance(caps, list) or len(caps) < 6:
        return fail("capabilities-too-few")
    inv = detect()
    live_sha = {
        inv["aud_graph"]["path"]: inv["aud_graph"]["sha256"],
        inv["catalog"]["path"]: inv["catalog"]["sha256"],
        inv["taxonomy"]["path"]: inv["taxonomy"]["sha256"],
    }
    for lock in inv["hacktricks"]["lockfiles"]:
        live_sha[lock["path"]] = lock["sha256"]
    packages = ((inv.get("live_mcp") or {}).get("packages") or {})
    for pkg in packages.values():
        for row in pkg.get("files") or []:
            live_sha[row["path"]] = row["sha256"]
    classes_seen = set()
    ids = []
    for cap in caps:
        cid = cap.get("id")
        ids.append(cid)
        cls = cap.get("class")
        disp = cap.get("disposition")
        basis = cap.get("factual_basis") or ""
        classes_seen.add(cls)
        if cls not in CLASSES:
            return fail(f"bad-class:{cid}:{cls}")
        if disp not in DISPOSITIONS:
            return fail(f"bad-disposition:{cid}:{disp}")
        if len(basis) < 80:
            return fail(f"thin-basis:{cid}")
        if OVERCLAIM.search(basis):
            return fail(f"legal-overclaim-in-basis:{cid}")
        klass = cap.get("classification") or {}
        if klass.get("legal_conclusion") is not False:
            return fail(f"legal_conclusion-not-false:{cid}")
        if klass.get("eccn") is not None or klass.get("license_required") is not None or klass.get("itar") is not None:
            return fail(f"classification-assigned:{cid}")
        lineage = cap.get("source_lineage") or []
        if not lineage:
            return fail(f"lineage-absent:{cid}")
        for row in lineage:
            path = row.get("path")
            sha = row.get("sha256")
            pin = row.get("version_pin") or row.get("citation")
            ts = row.get("fetch_timestamp")
            if not path or not sha or not pin or not ts:
                return fail(f"unversioned-lineage:{cid}:{path}")
            p = HERE.parents[3] / path
            if p.is_file():
                got, _ = sha256_path(p)
                if got != sha:
                    return fail(f"lineage-sha-mismatch:{cid}:{path}")
                if path in live_sha and live_sha[path] != sha:
                    return fail(f"inventory-sha-mismatch:{cid}:{path}")
        quotes = cap.get("quoted_clauses") or []
        if not quotes:
            return fail(f"quoted-clauses-absent:{cid}")
        for span in quotes:
            if not any(span == q["span"] for q in QUOTES.values()):
                return fail(f"quote-not-in-pin-table:{cid}")
    if "reverse-engineering" not in classes_seen:
        return fail("class-reverse-engineering-absent")
    if "security-scanning" not in classes_seen:
        return fail("class-security-scanning-absent")
    if "automation" not in classes_seen:
        return fail("class-automation-absent")
    by_id = {c["id"]: c for c in caps}
    if not inv["aud_graph"]["has_reverse_engineering_bundle"]:
        return fail("inventory-missed-re-bundle")
    if by_id.get("CAP-RE-BUNDLE", {}).get("disposition") != "FLAGGED":
        return fail("re-bundle-not-flagged")
    if by_id.get("CAP-HEXSTRIKE-AI", {}).get("disposition") != "FLAGGED":
        return fail("hexstrike-not-flagged")
    if inv["hacktricks"]["present"] and by_id.get("CAP-HACKTRICKS-MCP", {}).get("disposition") != "FLAGGED":
        return fail("hacktricks-not-flagged")
    if str(doc.get("no_legal_conclusion_statement") or "") != NO_LEGAL:
        return fail("no-legal-field-mismatch")
    if doc.get("downstream_action_authorized") is not False:
        return fail("downstream-action-must-be-false")
    out = {
        "capabilities": len(caps),
        "classes": sorted(classes_seen),
        "ids": ids,
        "inventory_re_bundle": inv["aud_graph"]["has_reverse_engineering_bundle"],
        "inventory_hexstrike": inv["aud_graph"]["has_hexstrike_ai"],
        "live_tools_mcp": inv["live"]["tools_mcp_present"],
        "pass": True,
        "probe": "probe1-capability-basis",
        "quotes_ok": True,
        "unit_id": UNIT_ID,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print(f"SUCCESS:{UNIT_ID}-probe1 capability-by-capability factual basis; quotes pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
