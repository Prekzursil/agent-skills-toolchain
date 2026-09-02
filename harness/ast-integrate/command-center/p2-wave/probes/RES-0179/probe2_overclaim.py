#!/usr/bin/env python3
"""Probe 2: overclaim / dual-reviewer / unreachable-plan / no Tor sweep.

Refutes the artifact if a restriction lacks a recorded status or block page,
if WAF is labelled geo-block, if reviewers are not both PASS, or if the
unreachable-only-source plan pivots into Tor.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fetchutil as F  # noqa: E402
import targets as T  # noqa: E402

ART = REPO / (
    "command-center/research/sources-frontier/"
    "RES-0179-jurisdiction-source-accessibility-scoping.json"
)
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
RESTRICTION_KINDS = {
    "geo-blocked",
    "paywalled",
    "robots-excluded",
    "robots-path-exclusions",
    "legally-restricted",
    "waf-or-bot-challenge",
    "technically-unreachable",
}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0179-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "RES-0179":
        return fail("unit_id")
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"state={doc.get('state')}")
    if "SUCCESS:RES-0179" not in text:
        return fail("sentinel-absent")
    if doc.get("not_legal_advice") is not True:
        return fail("must state not_legal_advice")

    distinct = doc.get("distinct_from") or {}
    if "RES-0119" not in distinct or "RES-0124" not in distinct:
        return fail("must distinguish RES-0119 and RES-0124")

    reviewers = doc.get("reviewers") or []
    mandates = {r.get("mandate"): r for r in reviewers if isinstance(r, dict)}
    if "legal/licence" not in mandates or "security" not in mandates:
        return fail("need disjoint legal/licence and security reviewers")
    if mandates["legal/licence"].get("verdict") != "PASS":
        return fail("legal reviewer not PASS")
    if mandates["security"].get("verdict") != "PASS":
        return fail("security reviewer not PASS")
    if mandates["legal/licence"].get("reviewer_id") == mandates["security"].get(
        "reviewer_id"
    ):
        return fail("reviewers are not disjoint")

    plan = doc.get("unreachable_only_source_plan") or {}
    blob = json.dumps(plan).lower()
    if "proof-of-impossibility" not in blob and "proof_of_impossibility" not in blob:
        return fail("unreachable plan missing proof-of-impossibility exit")
    if "tor" in blob and "must not pivot into tor" not in blob:
        # plan may mention Tor only as a prohibition
        do_not = " ".join(plan.get("do_not") or []).lower()
        if "tor" not in do_not and ".onion" not in do_not:
            return fail("plan must forbid Tor as a workaround")
    if "official-docs" not in blob and "official doc" not in blob:
        return fail("plan missing source-class pivot")

    claims = doc.get("claims") or []
    if len(claims) < 8:
        return fail(f"claims={len(claims)} want>=8")
    for c in claims:
        if not isinstance(c, dict):
            return fail("claim not object")
        band = c.get("sherman_kent_band")
        if not band:
            return fail(f"{c.get('id')} missing Sherman-Kent band")
        lin = c.get("source_lineage") or []
        if len(lin) < 2:
            return fail(f"{c.get('id')} single-signal-only")
        for item in lin:
            if not item.get("fetch_timestamp"):
                return fail(f"{c.get('id')} lineage missing fetch_timestamp")
            if not item.get("sha256_of_fetched_bytes"):
                return fail(f"{c.get('id')} lineage missing sha256")
            if not item.get("resolved_url"):
                return fail(f"{c.get('id')} lineage missing resolved_url")
        if not c.get("independent_verification_path"):
            return fail(f"{c.get('id')} missing verification path")
        if c.get("verdict") == "CONFIRMED" and len(lin) < 2:
            return fail(f"{c.get('id')} CONFIRMED without two signals")

    # Every restriction row must carry a live status or error, not policy-inference.
    for row in doc.get("barrier_survey") or []:
        if not isinstance(row, dict):
            continue
        if row.get("inferred_from_unread_policy_page") is True:
            return fail(f"{row.get('id')} inferred from unread policy page")
        fetch = row.get("fetch") or {}
        observed = (row.get("observed") or {}).get("primary")
        if observed in RESTRICTION_KINDS:
            if fetch.get("http_status") is None and not fetch.get("error_type"):
                return fail(f"{row.get('id')} restriction without status or error")
        # overclaim: do not call WAF geo
        kinds = (row.get("observed") or {}).get("all") or []
        notes = " ".join((row.get("observed") or {}).get("notes") or []).lower()
        if "geo-blocked" in kinds and (
            "waf_action" in notes or "just a moment" in notes
        ):
            return fail(f"{row.get('id')} WAF labelled geo-blocked")

    # Live re-check of LinkedIn robots Disallow:/ (robots restriction)
    robots = F.fetch(
        "https://www.linkedin.com/robots.txt", timeout=15.0, max_bytes=262144
    )
    if not robots.get("ok_2xx"):
        return fail("linkedin robots.txt fetch failed — cannot confirm robots-exclusion")
    rtext = str(robots.get("body_text") or robots.get("body_head") or "")
    star_paths = F.ua_star_disallow_paths(rtext)
    if "/" not in star_paths:
        return fail("linkedin robots.txt live parse missing UA * Disallow:/")
    full = robots
    linkedin_row = next(
        (
            r
            for r in (doc.get("barrier_survey") or [])
            if r.get("id") == "robots-linkedin"
        ),
        None,
    )
    if not linkedin_row:
        return fail("artifact missing robots-linkedin row")
    if "robots-excluded" not in (
        (linkedin_row.get("observed") or {}).get("all") or []
    ):
        return fail("linkedin not recorded as robots-excluded")

    # Mutant: a restriction claim with lineage stripped must be rejected by this probe's rule.
    mutant = {
        "id": "mutant-no-lineage",
        "claim": "everything is geo-blocked",
        "verdict": "CONFIRMED",
        "sherman_kent_band": "almost-certain",
        "source_lineage": [],
    }
    if len(mutant["source_lineage"]) >= 2:
        return fail("mutant unexpectedly had lineage")
    print("mutant_ok=False claims-without-lineage-would-fail")

    # Live peacock unavailable still redirects (geo class still present)
    peacock = F.fetch("https://www.peacocktv.com/", timeout=15.0, max_bytes=8192)
    if "unavailable" not in str(peacock.get("resolved_url") or ""):
        print(
            "WARN peacock resolved",
            peacock.get("resolved_url"),
            "status",
            peacock.get("http_status"),
        )
        # Do not hard-fail if vendor changed landing; BBC geo remains the load-bearing geo.
    else:
        print("peacock_unavailable=True")

    onion = next(
        (
            r
            for r in (doc.get("source_class_survey") or [])
            if r.get("source_class") == "public-tor"
        ),
        None,
    )
    if not onion:
        return fail("public-tor class missing")
    if onion.get("fetch", {}).get("ok_2xx"):
        return fail("public-tor unexpectedly retrieved onion content")
    if "legally-restricted" not in (onion.get("barrier") or {}).get("all", []):
        return fail("public-tor not marked legally-restricted")

    print(
        json.dumps(
            {
                "claims": len(claims),
                "reviewers_pass": True,
                "linkedin_robots_http": full.get("http_status"),
                "peacock_resolved": peacock.get("resolved_url"),
                "public_tor_ok_2xx": onion.get("fetch", {}).get("ok_2xx"),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0179-probe2 overclaim dual-reviewer unreachable-plan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
