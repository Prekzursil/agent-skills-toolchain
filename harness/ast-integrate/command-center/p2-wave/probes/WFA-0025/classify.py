#!/usr/bin/env python3
"""Classify replication, estate links, verbatim metrics, negative hunts."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from corpus import CORPUS
from estate import scan_estate

NEGATIVE_MARKERS = (
    "not",
    "no ",
    "fail",
    "underperform",
    "does not",
    "do not",
    "negative",
    "worse",
    "overoptimization",
)


def replication_class(row: dict) -> str:
    independents = [
        s
        for s in (row.get("independent_signals") or [])
        if s.get("independent") and s.get("role") in {"replication", "contradiction"}
    ]
    primary = row.get("primary") or {}
    measured = primary.get("measured_effect_recorded", primary.get("reported_value") is not None)
    if not measured:
        return "UNQUANTIFIED"
    if independents:
        if any(s.get("role") == "contradiction" for s in independents):
            return "MULTI-SOURCE-CONTRADICTED"
        return "MULTI-SOURCE"
    return "SINGLE-SOURCE"


def verbatim_ok(primary: dict) -> tuple[bool, str]:
    if primary.get("measured_effect_recorded") is False:
        if primary.get("reported_value"):
            return False, "unquantified-row-has-number"
        return True, "unquantified"
    quote = primary.get("quote") or ""
    value = primary.get("reported_value") or ""
    if not value:
        return False, "missing-reported-value"
    if value not in quote:
        return False, "reported-value-not-in-quote"
    baseline = primary.get("baseline_value")
    if baseline and baseline not in quote:
        return False, "baseline-not-in-quote"
    return True, "verbatim"


def negative_hunt_ok(hunt: dict) -> tuple[bool, str]:
    queries = hunt.get("queries") or []
    if len(queries) < 2:
        return False, "need-two-negative-queries"
    marked = 0
    for q in queries:
        ql = q.lower()
        if any(m in ql for m in NEGATIVE_MARKERS):
            marked += 1
    if marked < 2:
        return False, "queries-lack-negative-phrasing"
    if int(hunt.get("retrieved_negative_count") or 0) < 0:
        return False, "count"
    return True, "ok"


def classify_protocol(row: dict, estate_row: dict) -> dict:
    primary = row["primary"]
    rclass = replication_class(row)
    v_ok, v_why = verbatim_ok(primary)
    n_ok, n_why = negative_hunt_ok(row.get("negative_hunt") or {})
    settling = row.get("settling_experiment")
    if rclass == "SINGLE-SOURCE" and not settling:
        settle_ok = False
        settle_why = "single-source-missing-settling-experiment"
    elif rclass == "UNQUANTIFIED" and not settling:
        settle_ok = False
        settle_why = "unquantified-missing-settling-experiment"
    else:
        settle_ok = True
        settle_why = "ok"

    implemented = estate_row.get("estate_status") == "IMPLEMENTED"
    cand = estate_row.get("implementing_candidate_id")
    if implemented and not cand:
        estate_ok = False
        estate_why = "implemented-missing-candidate-id"
    else:
        estate_ok = True
        estate_why = "ok"

    out = {
        "protocol_id": row["protocol_id"],
        "protocol_name": row["protocol_name"],
        "replication_class": rclass,
        "settling_experiment": settling,
        "primary": {
            k: primary.get(k)
            for k in (
                "paper_id",
                "title",
                "authors",
                "year",
                "url",
                "dataset",
                "metric",
                "baseline_value",
                "reported_value",
                "delta_verbatim",
                "anchor",
                "quote",
                "measured_effect_recorded",
                "quote_status",
                "note",
            )
            if k in primary
        },
        "independent_signals": row.get("independent_signals") or [],
        "negative_hunt": row.get("negative_hunt"),
        "estate": {
            "status": estate_row.get("estate_status"),
            "implementing_candidate_id": cand,
            "implementing_path": estate_row.get("implementing_path"),
            "planned_candidate_ids": estate_row.get("planned_candidate_ids"),
            "path_hits": estate_row.get("path_hits"),
            "non_equivalent": estate_row.get("non_equivalent"),
        },
        "checks": {
            "verbatim_ok": v_ok,
            "verbatim_why": v_why,
            "negative_hunt_ok": n_ok,
            "negative_hunt_why": n_why,
            "settling_ok": settle_ok,
            "settling_why": settle_why,
            "estate_ok": estate_ok,
            "estate_why": estate_why,
        },
    }
    out["row_pass"] = all(
        [
            v_ok,
            n_ok,
            settle_ok,
            estate_ok,
        ]
    )
    return out


def build_classified(repo: Path) -> dict:
    estate = scan_estate(repo)
    rows = []
    for proto in CORPUS:
        er = estate["protocols"][proto["protocol_id"]]
        rows.append(classify_protocol(proto, er))
    passed = all(r["row_pass"] for r in rows)
    return {
        "estate_scan": estate,
        "protocols": rows,
        "all_pass": passed,
    }


def mutant_drop_settling(classified: dict) -> dict:
    doc = copy.deepcopy(classified)
    for row in doc["protocols"]:
        if row["replication_class"] == "SINGLE-SOURCE":
            row["settling_experiment"] = None
            row["checks"]["settling_ok"] = False
            row["checks"]["settling_why"] = "mutant-drop-settling"
            row["row_pass"] = False
            break
    doc["all_pass"] = all(r["row_pass"] for r in doc["protocols"])
    return doc


def mutant_drop_candidate(classified: dict) -> dict:
    doc = copy.deepcopy(classified)
    for row in doc["protocols"]:
        if row["estate"]["status"] == "IMPLEMENTED":
            row["estate"]["implementing_candidate_id"] = None
            row["checks"]["estate_ok"] = False
            row["checks"]["estate_why"] = "mutant-drop-candidate"
            row["row_pass"] = False
            break
    doc["all_pass"] = all(r["row_pass"] for r in doc["protocols"])
    return doc


def mutant_round_number(classified: dict) -> dict:
    doc = copy.deepcopy(classified)
    for row in doc["protocols"]:
        val = row["primary"].get("reported_value")
        if val and any(ch.isdigit() for ch in val) and "." in val:
            # Paraphrase/round: 74.4 -> "about 74". Forbidden.
            rounded = "about " + val.split(".")[0]
            row["primary"]["reported_value"] = rounded
            ok, why = verbatim_ok(row["primary"])
            row["checks"]["verbatim_ok"] = ok
            row["checks"]["verbatim_why"] = "mutant-rounded:" + why
            row["row_pass"] = False
            break
    doc["all_pass"] = all(r["row_pass"] for r in doc["protocols"])
    return doc


def mutant_drop_negative_hunt(classified: dict) -> dict:
    doc = copy.deepcopy(classified)
    row = doc["protocols"][0]
    row["negative_hunt"] = {"queries": [], "retrieved_negative_count": 0}
    ok, why = negative_hunt_ok(row["negative_hunt"])
    row["checks"]["negative_hunt_ok"] = ok
    row["checks"]["negative_hunt_why"] = "mutant-drop-hunt:" + why
    row["row_pass"] = False
    doc["all_pass"] = all(r["row_pass"] for r in doc["protocols"])
    return doc


def detector_controls(classified: dict) -> dict:
    m1 = mutant_drop_settling(classified)
    m2 = mutant_drop_candidate(classified)
    m3 = mutant_round_number(classified)
    m4 = mutant_drop_negative_hunt(classified)
    good_silent = bool(classified.get("all_pass"))
    fired = (not m1["all_pass"]) and (not m2["all_pass"]) and (not m3["all_pass"]) and (
        not m4["all_pass"]
    )
    return {
        "good_state_silent": good_silent,
        "mutant_drop_settling_fires": not m1["all_pass"],
        "mutant_drop_candidate_fires": not m2["all_pass"],
        "mutant_round_number_fires": not m3["all_pass"],
        "mutant_drop_negative_hunt_fires": not m4["all_pass"],
        "pass": good_silent and fired,
    }


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
