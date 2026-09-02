#!/usr/bin/env python3
"""Probe 2: two-signal lineage, policy-only cannot be OBSERVED, reviewer pair, mutants fail."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lineage as L  # noqa: E402

ART = L.REPO / L.ARTIFACT_REL
SCHEMA = L.REPO / L.SCHEMA_REL
LOAD_BEARING = {"CONFIRMED", "REFUTED", "PARTIAL", "INFERRED"}


def check(doc: dict) -> tuple[bool, str]:
    if str(doc.get("unit_id")) != "RES-0178":
        return False, "unit_id"
    if "SUCCESS:RES-0178" not in json.dumps(doc):
        return False, "sentinel"
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        return False, f"schema:{exc.message}"

    claims = doc.get("claims") or []
    if len(claims) < 6:
        return False, "claims-short"
    for row in claims:
        if row.get("verdict") not in LOAD_BEARING:
            return False, f"verdict-{row.get('id')}"
        if not row.get("independent_verification_path"):
            return False, f"verification-path-{row.get('id')}"
        sigs = row.get("signals") or []
        if len(sigs) < 2:
            return False, f"single-signal-{row.get('id')}"
        urls = {s.get("url") for s in sigs}
        caps = {s.get("capture_id") for s in sigs}
        if len(urls) < 2 and len(caps) < 2:
            return False, f"dependent-signals-{row.get('id')}"
        for s in sigs:
            cid = s.get("capture_id")
            snip = s.get("snippet")
            sha = s.get("sha256")
            if not cid or not snip or not sha:
                return False, f"incomplete-signal-{row.get('id')}"
            try:
                cap = L.assert_snippet(cid, snip)
            except Exception as exc:
                return False, f"snippet:{row.get('id')}:{exc}"
            if cap["sha256"] != sha:
                return False, f"sha-drift-{cid}"

    for hub in doc.get("hubs") or []:
        basis = hub.get("review_basis")
        depth = hub.get("review_depth")
        if basis == "policy-page-only" and depth != "INFERRED":
            return False, f"policy-only-overclaim-{hub.get('id')}"
        if basis == "absent" and depth != "NONE":
            return False, f"absent-overclaim-{hub.get('id')}"
        if hub.get("auto_install_eligible") is True:
            return False, f"auto-install-overclaim-{hub.get('id')}"

    revs = doc.get("reviewers") or []
    mandates = {r.get("mandate") for r in revs}
    if mandates != {"security", "supply-chain"}:
        return False, f"reviewer-mandates:{mandates}"
    for r in revs:
        if r.get("independent") is not True or r.get("default_to_refuted") is not True:
            return False, "reviewer-not-default-refuted"

    if (doc.get("auto_install_bar") or {}).get("any_sampled_listing_meets_bar") is not False:
        return False, "bar-green"
    if not (doc.get("negative_controls") or []):
        return False, "no-negative-control"
    return True, "ok"


def main() -> int:
    if not ART.is_file() or not SCHEMA.is_file():
        print("FAILED:RES-0178-probe2 artifact or schema missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = check(doc)
    print(f"lineage_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0178-probe2 live artifact failed lineage/review-depth")
        return 1

    mutant = copy.deepcopy(doc)
    mutant["claims"][0]["signals"][0].pop("sha256", None)
    mok, mwhy = check(mutant)
    print(f"mutant_drop_sha ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0178-probe2 mutant missing sha256 was accepted")
        return 1

    mutant2 = copy.deepcopy(doc)
    for hub in mutant2["hubs"]:
        if hub.get("review_basis") == "policy-page-only":
            hub["review_depth"] = "OBSERVED"
            break
    else:
        print("FAILED:RES-0178-probe2 no policy-page-only hub to mutate")
        return 1
    m2ok, m2why = check(mutant2)
    print(f"mutant_policy_as_observed ok={m2ok} {m2why}")
    if m2ok:
        print("FAILED:RES-0178-probe2 policy-only OBSERVED mutant was accepted")
        return 1

    mutant3 = copy.deepcopy(doc)
    mutant3["claims"] = mutant3["claims"][:1]
    mutant3["claims"][0]["signals"] = mutant3["claims"][0]["signals"][:1]
    m3ok, m3why = check(mutant3)
    print(f"mutant_single_signal ok={m3ok} {m3why}")
    if m3ok:
        print("FAILED:RES-0178-probe2 single-signal mutant was accepted")
        return 1

    print("SUCCESS:RES-0178-probe2 lineage review-depth reviewer-pair mutants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
