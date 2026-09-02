#!/usr/bin/env python3
"""Contract checker for RES-0076 negative-result record.

Silent on a well-formed hunt; red on missing negative phrasings, missing
baseline-on-promoted-mechanism, collapsed reviewer partitions, or a
self-declared BLOCKED/FAILED state.
"""
from __future__ import annotations

import copy
from typing import Any

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SENTINEL = (
    "SUCCESS:RES-0076 in the receipt AND a negative-result register with the "
    "query set printed and the positive/negative retrieval ratio"
)
NEG_PHRASES = (
    "underperform",
    "does not outperform",
    "fail to outperform",
    "worse than",
    "no better than",
    "below a single",
    "premature consensus",
    "debate hacking",
)


def _err(msg: str) -> str:
    return msg


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.split("/")[0]) if value else None
        except ValueError:
            return None
    return None


def check_record(doc: Any) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, _err("record is not an object")
    if doc.get("unit_id") != "RES-0076":
        return False, _err(f"unit_id {doc.get('unit_id')}")
    text = str(doc.get("sentinel") or "")
    if SENTINEL not in text and SENTINEL not in str(doc):
        return False, _err("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return False, _err(f"self-declared:{st}")

    queries = doc.get("query_set")
    if not isinstance(queries, list) or len(queries) < 4:
        return False, _err("query_set missing or too small")
    neg_q = []
    for q in queries:
        if not isinstance(q, dict):
            return False, _err("query_set row not object")
        qtext = str(q.get("search_query") or "")
        if not qtext:
            return False, _err("query missing search_query")
        if q.get("negative_phrasing") is True or any(p in qtext.lower() for p in NEG_PHRASES):
            if not any(p in qtext.lower() for p in NEG_PHRASES):
                return False, _err(f"{q.get('id')} marked negative without negative phrasing")
            neg_q.append(q)
    if len(neg_q) < 2:
        return False, _err("query_set lacks explicitly negative phrasings")

    ratio = doc.get("retrieval_ratio")
    if not isinstance(ratio, dict):
        return False, _err("retrieval_ratio missing")
    pos_n = _num(ratio.get("positive_total_results"))
    neg_n = _num(ratio.get("negative_total_results"))
    if pos_n is None or neg_n is None or neg_n <= 0:
        return False, _err("retrieval_ratio missing counts")
    printed = str(ratio.get("positive_over_negative") or "")
    if f"{int(pos_n)}/{int(neg_n)}" not in printed and printed != f"{pos_n}/{neg_n}":
        return False, _err("retrieval_ratio positive/negative string missing")
    mixed_pos = ratio.get("mixed_query_positive_count")
    mixed_neg = ratio.get("mixed_query_negative_count")
    if not isinstance(mixed_pos, int) or not isinstance(mixed_neg, int):
        return False, _err("search-bias control missing mixed positive/negative counts")
    if mixed_pos <= mixed_neg:
        # Not a hard scientific law, but this hunt's live mixed set is
        # majority-positive; a flipped count without recomputation is a lie.
        return False, _err("search-bias control does not expose positive majority")

    register = doc.get("negative_result_register")
    if not isinstance(register, list) or len(register) < 3:
        return False, _err("negative_result_register missing or <3 rows")

    promoted = []
    at_or_below = 0
    for row in register:
        if not isinstance(row, dict):
            return False, _err("register row not object")
        ident = str(row.get("arxiv_id") or row.get("doi") or "")
        if not ident:
            return False, _err(f"{row.get('id')} missing arxiv_id/doi")
        anchor = str(row.get("section_or_figure") or "")
        if not anchor:
            return False, _err(f"{row.get('id')} missing section_or_figure")
        effect = row.get("effect_size")
        baseline = row.get("baseline")
        missing_baseline = baseline in (None, "", {})
        if missing_baseline:
            if row.get("evidence_tier") != "E3":
                return False, _err(f"{row.get('id')} headline without baseline is not E3")
            if row.get("promoted") is True:
                return False, _err(f"{row.get('id')} E3 headline promoted a mechanism")
            continue
        if effect in (None, "", {}):
            return False, _err(f"{row.get('id')} missing effect_size")
        if row.get("promoted") is True:
            promoted.append(row)
            ev = str(row.get("evidence_tier") or "")
            if ev not in {"E1", "E2"}:
                return False, _err(f"{row.get('id')} promoted without E1/E2")
            relation = str(row.get("relation_to_baseline") or "")
            if relation in {"at_or_below", "below", "equal"}:
                at_or_below += 1
            elif relation == "above":
                pass
            else:
                return False, _err(f"{row.get('id')} missing relation_to_baseline")
    if len(promoted) < 3:
        return False, _err("fewer than 3 promoted mechanisms with baseline")
    if at_or_below < 3:
        return False, _err("promoted register does not show at-or-below vs baseline")

    eco = doc.get("eco_reject")
    if not isinstance(eco, dict):
        return False, _err("eco_reject missing")
    if "multi-round free-form debate to consensus" not in str(eco.get("named_reject") or ""):
        return False, _err("eco_reject does not name the catalog reject")
    present = eco.get("source_present_on_this_worktree")
    if present is True:
        from pathlib import Path as _P

        sp = str(eco.get("source_path_checked") or "")
        if not sp or not _P(sp).is_file():
            return False, _err("eco source claimed present but file missing")
    elif present is not False:
        return False, _err("eco_reject.source_present_on_this_worktree not boolean")
    if str(eco.get("verdict") or "") not in {"PARTIAL-CORROBORATES", "CORROBORATES", "DOES-NOT-EXPLAIN"}:
        return False, _err("eco_reject verdict missing")
    if not str(eco.get("strongest_caveat") or ""):
        return False, _err("eco_reject missing strongest_caveat")

    reviewers = doc.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) < 2:
        return False, _err("need two partitioned reviewers")
    vendors = []
    paper_sets = []
    for rev in reviewers:
        if not isinstance(rev, dict):
            return False, _err("reviewer not object")
        vendor = str(rev.get("vendor") or "")
        if not vendor:
            return False, _err("reviewer missing vendor")
        vendors.append(vendor)
        papers = rev.get("paper_ids")
        if not isinstance(papers, list) or len(papers) < 1:
            return False, _err(f"{rev.get('reviewer_id')} empty partition")
        paper_sets.append(set(str(p) for p in papers))
        if not str(rev.get("verdict") or ""):
            return False, _err(f"{rev.get('reviewer_id')} missing verdict")
    if vendors[0] == vendors[1]:
        return False, _err("reviewers share vendor (05-ECO anti-adoption #2)")
    if paper_sets[0] & paper_sets[1]:
        return False, _err("reviewer partitions overlap")
    union = set().union(*paper_sets)
    promoted_ids = {str(r.get("arxiv_id") or "").split("v")[0] for r in promoted}
    promoted_ids = {p for p in promoted_ids if p}
    if not promoted_ids.issubset(union):
        missing = sorted(promoted_ids - union)
        return False, _err(f"promoted papers not covered by partitions: {missing}")

    return True, "ok"


def mutant_strip_negative_queries(doc: dict) -> dict:
    m = copy.deepcopy(doc)
    m["query_set"] = [
        q
        for q in (m.get("query_set") or [])
        if isinstance(q, dict) and not q.get("negative_phrasing")
    ]
    return m


def mutant_strip_baseline(doc: dict) -> dict:
    m = copy.deepcopy(doc)
    for row in m.get("negative_result_register") or []:
        if isinstance(row, dict) and row.get("promoted") is True:
            row.pop("baseline", None)
            row["evidence_tier"] = "E1"
            return m
    return m


def mutant_collapse_partitions(doc: dict) -> dict:
    m = copy.deepcopy(doc)
    revs = m.get("reviewers") or []
    if len(revs) >= 2 and isinstance(revs[0], dict) and isinstance(revs[1], dict):
        shared = list(revs[0].get("paper_ids") or []) + list(revs[1].get("paper_ids") or [])
        revs[0]["paper_ids"] = list(shared)
        revs[1]["paper_ids"] = list(shared)
        revs[1]["vendor"] = revs[0].get("vendor")
    return m


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "/opt/p2/ast-integrate/command-center/research/RES-0076.json"
    )
    doc = json.loads(path.read_text(encoding="utf-8"))
    ok, why = check_record(doc)
    print(f"ok={ok} {why}")
    raise SystemExit(0 if ok else 1)
