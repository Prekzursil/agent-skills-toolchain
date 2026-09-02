#!/usr/bin/env python3
"""Probe 1: registry indexes vs declared/reconstructed schema (evidence A).

Does not fetch pack trees or compare plugin.json receipts. Both-states: a
schema-broken index must go red; captured well-formed indexes must go green.
Prose in description must not become license.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0023-sweep-public-marketplaces.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0023-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact state {doc.get('state')}")
    if "SUCCESS:WFA-0023" not in text:
        return fail("sentinel-absent")

    broken = E.load_json(HERE / "fixtures" / "index_schema_broken.json")
    v_broken = E.validate_claude_marketplace(broken)
    if v_broken["ok"]:
        return fail("broken index validated green")

    prose = E.load_json(HERE / "fixtures" / "index_prose_only.json")
    v_prose = E.validate_claude_marketplace(prose)
    if not v_prose["ok"]:
        return fail(f"prose-only fixture should be schema-valid: {v_prose['errors']}")
    control = E.prose_must_not_fill(prose["plugins"][0])
    if not control["control_ok"]:
        return fail(f"prose leaked into license: {control}")

    official = E.load_official()
    v_off = E.validate_claude_marketplace(official)
    if not v_off["ok"]:
        return fail(f"official capture schema-red {v_off['errors']}")
    if v_off["plugin_count"] < 50:
        return fail(f"official plugin_count too small {v_off['plugin_count']}")

    community = E.load_community()
    v_com = E.validate_claude_marketplace(community)
    if not v_com["ok"]:
        return fail(f"community capture schema-red {v_com['errors']}")
    if v_com["plugin_count"] < 500:
        return fail(f"community plugin_count too small {v_com['plugin_count']}")

    schema_fetch = E.load_json(HERE / "captures" / "declared-schema-fetch.json")
    if schema_fetch.get("reachable") is True:
        return fail("declared schema URL recorded reachable; capture is 404")
    if schema_fetch.get("http_status") != 404:
        return fail(f"expected 404 for declared schema URL, got {schema_fetch}")

    packs = E.extract_claude_packs(official, "claude-plugins-official")
    licensed = [p for p in packs if p["license_from_index"] != E.UNDECLARED]
    if licensed:
        return fail(f"unexpected license fields on official index: {licensed[:3]}")

    cline = E.load_cline()
    v_cl = E.validate_cline_catalog(cline)
    if not v_cl["ok"]:
        return fail(f"cline catalog schema-red {v_cl['errors']}")
    cline_packs = E.extract_cline_packs(cline)
    cline_licensed = [p for p in cline_packs if p["license_from_index"] != E.UNDECLARED]
    if not cline_licensed:
        return fail("cline catalog expected per-entry license fields")

    mcp = E.load_mcp()
    v_mcp = E.validate_mcp_page(mcp)
    if not v_mcp["ok"]:
        return fail(f"mcp page schema-red {v_mcp['errors']}")

    ev = doc.get("evidence_a") or {}
    if not ev.get("validations", {}).get("claude-plugins-official", {}).get("ok"):
        return fail("artifact evidence_a missing official validation")

    out = {
        "probe": "probe1-index-schema",
        "unit_id": "WFA-0023",
        "broken_index_rejected": True,
        "official_ok": True,
        "community_ok": True,
        "official_plugin_count": v_off["plugin_count"],
        "community_plugin_count": v_com["plugin_count"],
        "official_license_fields": 0,
        "cline_license_fields": len(cline_licensed),
        "declared_schema_url_reachable": False,
        "prose_not_promoted_to_license": True,
        "independence": "index+schema only; no plugin.json receipts",
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:WFA-0023-probe1 index-schema both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
