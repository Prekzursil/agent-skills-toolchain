"""Probe 2 logic: classify each requirement REPRESENTED / SUPERSEDED / DROPPED."""
from __future__ import annotations

from typing import Any

from common import PLANTED_TOKEN


def _oq4_runs_real_prompt_two(catalog: dict) -> bool:
    for q in catalog.get("owner_questions") or []:
        if not isinstance(q, dict) or str(q.get("id") or "") != "OQ-4":
            continue
        if str(q.get("state") or "") != "ANSWERED":
            return False
        blob = " ".join(
            [str(q.get("answer") or ""), str(q.get("answer_detail") or "")]
        )
        return "Run the real Prompt Two" in blob or "NOT an approved substitute" in blob
    return False


def _blob(values: list[object]) -> str:
    parts: list[str] = []
    for v in values:
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
        elif v:
            parts.append(str(v))
    return " ".join(parts)


def _hits_for(req: dict, catalog: dict) -> list[dict[str, Any]]:
    needles = [n for n in (req.get("needles") or []) if isinstance(n, str) and n]
    rid = str(req.get("id") or "")
    hits: list[dict[str, Any]] = []

    for q in catalog.get("owner_questions") or []:
        if not isinstance(q, dict):
            continue
        qid = str(q.get("id") or "")
        blob = _blob(
            [
                qid,
                q.get("text"),
                q.get("answer"),
                q.get("answer_detail"),
                q.get("answer_provenance"),
            ]
        )
        if (qid and qid in rid) or any(n in blob for n in needles):
            hits.append(
                {
                    "kind": "answered_oq"
                    if str(q.get("state") or "") == "ANSWERED"
                    else "open_oq",
                    "id": qid,
                    "disposition": str(q.get("state") or ""),
                }
            )

    for item in catalog.get("items") or []:
        if not isinstance(item, dict):
            continue
        iid = str(item.get("id") or "")
        blob = _blob(
            [
                iid,
                item.get("title"),
                item.get("target"),
                item.get("evidence"),
                item.get("disposition_evidence"),
            ]
        )
        item_needles = [n for n in needles if len(n) >= 8]
        if (iid and iid in rid) or any(n in blob for n in item_needles):
            hits.append(
                {
                    "kind": "catalog_item",
                    "id": iid,
                    "disposition": str(item.get("disposition") or ""),
                }
            )

    long_needles = [n for n in needles if len(n) >= 12]
    if long_needles:
        for unit in catalog.get("work_units") or []:
            if not isinstance(unit, dict):
                continue
            uid = str(unit.get("id") or "")
            blob = _blob(
                [
                    uid,
                    unit.get("title"),
                    unit.get("question_or_target"),
                    unit.get("evidence_requirement"),
                    unit.get("inputs"),
                    unit.get("tests_required"),
                ]
            )
            if any(n in blob for n in long_needles):
                hits.append(
                    {
                        "kind": "work_unit",
                        "id": uid,
                        "disposition": "work_unit",
                    }
                )

    uniq: dict[tuple[str, str], dict[str, Any]] = {}
    for h in hits:
        uniq[(h["kind"], h["id"])] = h
    return list(uniq.values())


def classify_one(req: dict, catalog: dict) -> dict[str, Any]:
    if req.get("planted") or PLANTED_TOKEN in str(req.get("text") or ""):
        return {
            **req,
            "verdict": "DROPPED",
            "evidence": (
                "Planted canary is present only in the scratch transcript copy "
                "and has no representing decision, unit, or artifact in the live corpus."
            ),
            "hits": [],
        }
    hits = _hits_for(req, catalog)
    text = str(req.get("text") or "")
    if "Do not begin broad implementation yet" in text and _oq4_runs_real_prompt_two(
        catalog
    ):
        return {
            **req,
            "verdict": "SUPERSEDED",
            "evidence": (
                "D-03 records the plan-mode mandate 'Do not begin broad "
                "implementation yet'; OQ-4 later selected 'Run the real Prompt Two' "
                "(the >=2,048-unit build), which supersedes that freeze."
            ),
            "hits": hits,
        }
    if not hits:
        return {
            **req,
            "verdict": "DROPPED",
            "evidence": (
                "No representing owner_question, catalog item, or work unit "
                "matched this requirement's needles."
            ),
            "hits": [],
        }
    answered = [h for h in hits if h["kind"] == "answered_oq"]
    units = [h for h in hits if h["kind"] == "work_unit"]
    items = [h for h in hits if h["kind"] == "catalog_item"]
    if answered or units:
        rep = (answered + units)[0]
        return {
            **req,
            "verdict": "REPRESENTED",
            "evidence": (
                f"Representing {rep['kind']} {rep['id']} matched needles "
                f"{req.get('needles')}"
            ),
            "hits": hits,
        }
    if items:
        item = items[0]
        return {
            **req,
            "verdict": "REPRESENTED",
            "evidence": (
                f"Catalog item {item['id']} (disposition={item['disposition']}) "
                "records the owner statement."
            ),
            "hits": hits,
        }
    return {
        **req,
        "verdict": "DROPPED",
        "evidence": "Hits existed but none were a representing artifact.",
        "hits": hits,
    }


def classify_requirements(reqs: list[dict], catalog: dict) -> dict[str, Any]:
    classified = [classify_one(r, catalog) for r in reqs]
    live = [r for r in classified if not r.get("planted")]
    planted = [r for r in classified if r.get("planted")]
    live_dropped = [r for r in live if r["verdict"] == "DROPPED"]

    def _count(rows: list[dict]) -> dict[str, int]:
        out = {"REPRESENTED": 0, "SUPERSEDED": 0, "DROPPED": 0}
        for row in rows:
            key = str(row["verdict"])
            out[key] = out.get(key, 0) + 1
        return out

    return {
        "classified": classified,
        "live": live,
        "counts": _count(classified),
        "live_counts": _count(live),
        "planted_dropped": bool(planted)
        and all(r["verdict"] == "DROPPED" for r in planted),
        "planted_count": len(planted),
        "not_all_represented": any(r["verdict"] != "REPRESENTED" for r in classified),
        "live_dropped_ids": [r["id"] for r in live_dropped],
    }
