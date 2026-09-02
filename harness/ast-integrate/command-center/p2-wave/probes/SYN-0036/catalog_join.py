#!/usr/bin/env python3
"""Census catalog producer triples. Live claim/refuter joins are classified."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _present(rel):
    path = REPO / rel
    return {
        "bytes": path.stat().st_size if path.is_file() else 0,
        "path": rel,
        "present": path.is_file(),
    }


def _claim_registry_shape():
    rel = "command-center/CLAIM-REGISTRY.json"
    info = _present(rel)
    info["usable_as_producer_refutation_join"] = False
    if not info["present"]:
        info["reason"] = "file absent"
        info["n_claims"] = 0
        return info
    try:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        info["reason"] = "unparseable:%s" % type(exc).__name__
        info["n_claims"] = 0
        return info
    claims = doc.get("claims") if isinstance(doc, dict) else None
    if not isinstance(claims, list):
        info["reason"] = "no claims[] array"
        info["n_claims"] = 0
        return info
    info["n_claims"] = len(claims)
    has_producer = any(
        isinstance(c, dict) and ("producer_id" in c or "assigned_model_vendor_role" in c)
        for c in claims
    )
    has_phase12 = any(
        isinstance(c, dict) and str(c.get("verdict") or "").upper() in {"SURVIVED", "REFUTED"}
        for c in claims
    )
    if has_producer and has_phase12:
        info["usable_as_producer_refutation_join"] = True
        info["reason"] = "claims carry producer_id and SURVIVED|REFUTED"
        return info
    info["reason"] = (
        "present (n=%s) but not a Phase-12 authorship join: no producer_id "
        "and verdicts are CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED, not "
        "SURVIVED|REFUTED. Not rebuilt." % info["n_claims"]
    )
    return info


def _events_shape():
    rel = "command-center/events/EVENTS.jsonl"
    info = _present(rel)
    info["usable_as_authorship_ledger"] = False
    if not info["present"]:
        info["reason"] = "file absent"
        info["n_records"] = 0
        return info
    n = 0
    verbs = set()
    try:
        for line in (REPO / rel).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            n += 1
            rec = json.loads(line)
            if isinstance(rec, dict) and rec.get("verb"):
                verbs.add(str(rec["verb"]))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        info["reason"] = "unparseable:%s" % type(exc).__name__
        info["n_records"] = n
        return info
    info["n_records"] = n
    info["verbs"] = sorted(verbs)
    if "dispatch" in verbs or "assigned_model_vendor_role" in verbs:
        info["usable_as_authorship_ledger"] = True
        info["reason"] = "contains dispatch/authorship records"
        return info
    info["reason"] = (
        "present (n=%s verbs=%s) but not an authorship ledger for "
        "role/vendor/substrate producers. Not rebuilt." % (n, sorted(verbs))
    )
    return info


def _syn0035_shape():
    catalog_rel = "command-center/WORK-UNIT-CATALOG.json"
    declared = "command-center/receipts/SYN-0035.json"
    cat_path = REPO / catalog_rel
    if cat_path.is_file():
        doc = json.loads(cat_path.read_text(encoding="utf-8"))
        for u in doc.get("work_units") or []:
            if isinstance(u, dict) and u.get("id") == "SYN-0035":
                declared = str(u.get("output_path") or declared).replace("\\", "/")
                break
    info = _present(declared)
    info["usable"] = False
    if not info["present"]:
        info["reason"] = "catalog output_path absent"
        return info
    info["reason"] = "present"
    info["usable"] = True
    return info


def catalog_producer_census():
    catalog_rel = "command-center/WORK-UNIT-CATALOG.json"
    path = REPO / catalog_rel
    roles = set()
    n_units = 0
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
        units = doc.get("work_units") or []
        n_units = len(units)
        for u in units:
            if not isinstance(u, dict):
                continue
            amvr = u.get("assigned_model_vendor_role") or {}
            role = str(amvr.get("role") or "")
            vendor = str(amvr.get("vendor") or "")
            substrate = str(u.get("execution_substrate") or "")
            if role and vendor and substrate:
                roles.add((role, vendor, substrate))
    return {
        "catalog": _present(catalog_rel),
        "n_producer_triples": len(roles),
        "n_units": n_units,
        "sample_triples": [
            {"role": r, "substrate": s, "vendor": v}
            for r, v, s in sorted(roles)[:8]
        ],
    }


def live_inputs():
    return {
        "B10_adversarial_dir": {
            "path": "command-center/adversarial",
            "present": (REPO / "command-center/adversarial").is_dir(),
            "usable_as_phase12_refuter_corpus": False,
            "reason": (
                "command-center/adversarial is not a Phase-12 claim-authorship "
                "join; ADV rebuild of that corpus is out of scope for SYN-0036."
            ),
        },
        "CLAIM-REGISTRY.json": _claim_registry_shape(),
        "EVENTS.jsonl": _events_shape(),
        "SYN-0035": _syn0035_shape(),
        "catalog": catalog_producer_census(),
    }
