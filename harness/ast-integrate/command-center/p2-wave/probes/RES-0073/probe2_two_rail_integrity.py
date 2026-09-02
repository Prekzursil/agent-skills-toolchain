#!/usr/bin/env python3
"""Probe 2: adversarial two-rail integrity refuter.

Defaults to REFUTED for single-rail claims and vendor-marketing-as-use.
Re-hashes stored capture bytes. Re-parses the GHA YAML census and the n8n
issue-search total_count from frozen API bodies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

OUT = C.REPO / C.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0073-probe2 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    claims = doc.get("claims") or []
    if len(claims) < 6:
        return fail(f"too few claims: {len(claims)}")

    planted = set((doc.get("controls") or {}).get("planted_claim_ids") or [])
    if "C-E3-SINGLE-RAIL-PLANTED" not in planted:
        return fail("planted single-rail control missing")
    if "C-MKT-N8N-SOURCE-CONTROL-NOT-USE" not in planted:
        return fail("planted vendor-marketing control missing")

    surviving = 0
    refuted = 0
    for claim in claims:
        cid = str(claim.get("claim_id") or "")
        rails = claim.get("rails") or []
        cited = bool(claim.get("cited_as_measured_fact"))
        verdict = str(claim.get("verdict") or "")
        classes = set(claim.get("source_classes") or [])
        kinds = set(claim.get("rail_kinds") or [])

        for rail in rails:
            cap = str(rail.get("capture_id") or "")
            sha, n = C.digest_raw(cap)
            if int(rail.get("http_status") or 0) != 200:
                return fail(f"{cid} rail {cap} http_status not 200")
            if not rail.get("permalink"):
                return fail(f"{cid} rail {cap} missing permalink")
            if not rail.get("fetch_timestamp"):
                return fail(f"{cid} rail {cap} missing fetch_timestamp")
            if str(rail.get("sha256") or "") != sha:
                return fail(f"{cid} rail {cap} sha256 mismatch live={sha}")
            if int(rail.get("bytes") or 0) != n:
                return fail(f"{cid} rail {cap} bytes mismatch live={n}")
            quote = str(rail.get("quote") or "")
            if not quote or not C.quote_in_capture(cap, quote):
                return fail(f"{cid} rail {cap} quote not in captured bytes")

        if cited:
            surviving += 1
            if verdict != "SURVIVING":
                return fail(f"{cid} cited as fact but verdict={verdict}")
            if len(rails) < 2:
                return fail(f"{cid} cited as fact with <2 rails")
            if "structured-api" not in kinds or "prose-source" not in kinds:
                return fail(f"{cid} cited as fact without both rail kinds: {kinds}")
            if "vendor-marketing" in classes:
                return fail(f"{cid} cites vendor-marketing as measured fact")
            caveat = str(claim.get("strongest_caveat") or "")
            if len(caveat) < 24:
                return fail(f"{cid} surviving claim missing strongest caveat")
            if str(claim.get("evidence_tier") or "") == "E3":
                return fail(f"{cid} E3 cited as measured fact")
        else:
            refuted += 1
            if verdict != "REFUTED":
                return fail(f"{cid} not-cited must be REFUTED, got {verdict}")
            if str(claim.get("evidence_tier") or "") != "E3":
                return fail(f"{cid} control is not E3")

    planted_row = next(c for c in claims if c.get("claim_id") == "C-E3-SINGLE-RAIL-PLANTED")
    if len(planted_row.get("rails") or []) != 1:
        return fail("planted single-rail control does not have exactly one rail")
    mkt = next(c for c in claims if c.get("claim_id") == "C-MKT-N8N-SOURCE-CONTROL-NOT-USE")
    if "vendor-marketing" not in set(mkt.get("source_classes") or []):
        return fail("marketing control missing vendor-marketing class")

    live_census = C.gha_workflow_file_census()
    art_census = (doc.get("measurements") or {}).get("gha_workflow_file_census") or {}
    print(
        "gha_yaml="
        f"{live_census['n_yaml']} non_yaml={live_census['n_non_yaml']}"
    )
    if live_census["n_yaml"] < 1:
        return fail("GHA yaml census empty")
    if live_census["n_non_yaml"] != 0:
        return fail(f"GHA non-yaml files present: {live_census['non_yaml_names']}")
    if art_census.get("n_yaml") != live_census["n_yaml"]:
        return fail("artifact GHA n_yaml drifted from live reparse")
    if art_census.get("n_non_yaml") != 0:
        return fail("artifact GHA n_non_yaml not 0")

    live_search = C.n8n_source_control_issue_search()
    art_search = (doc.get("measurements") or {}).get(
        "n8n_source_control_issue_search"
    ) or {}
    print(f"n8n_source_control_issues total_count={live_search['total_count']}")
    if live_search["total_count"] < 1:
        return fail("n8n issue search total_count < 1")
    if art_search.get("total_count") != live_search["total_count"]:
        return fail("artifact n8n total_count drifted from live reparse")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        return fail("reviewer verdict not independent PASS")
    if reviewer.get("default", "").find("REFUTED") < 0:
        return fail("reviewer did not default to REFUTED")

    print(
        f"surviving={surviving} refuted_controls={refuted} "
        "two_rail_ok=True marketing_not_use=True"
    )
    print("SUCCESS:RES-0073-probe2 two-rail integrity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
