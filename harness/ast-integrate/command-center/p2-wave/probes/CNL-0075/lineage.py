#!/usr/bin/env python3
"""Decision-lineage decomposition: recommendation sentences -> idea ledger.

Chain (forward): idea -> option_card -> claim -> argument -> vote -> decision
-> action_plan. Recommendation sentences may cite only decision or action_plan
ids; walking parent pointers must reach at least one idea. An orphan sentence
(empty cites, dangling cite, or a walk that never hits an idea) FAILS.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

HOPS: tuple[dict[str, Any], ...] = (
    {
        "from_kind": "idea",
        "to_kind": "option_card",
        "collection": "option_cards",
        "parent_field": "promoted_from_idea_ids",
        "catalog_needles": ("idea", "option card"),
    },
    {
        "from_kind": "option_card",
        "to_kind": "claim",
        "collection": "claims",
        "parent_field": "about_option_card_ids",
        "catalog_needles": ("option card", "claim"),
    },
    {
        "from_kind": "claim",
        "to_kind": "argument",
        "collection": "arguments",
        "parent_field": "cites_claim_ids",
        "catalog_needles": ("claim", "argument"),
    },
    {
        "from_kind": "argument",
        "to_kind": "vote",
        "collection": "votes",
        "parent_field": "rests_on_argument_ids",
        "catalog_needles": ("argument", "vote"),
    },
    {
        "from_kind": "vote",
        "to_kind": "decision",
        "collection": "decisions",
        "parent_field": "tally_of_vote_ids",
        "catalog_needles": ("vote", "decision"),
    },
    {
        "from_kind": "decision",
        "to_kind": "action_plan",
        "collection": "action_plan",
        "parent_field": "implements_decision_ids",
        "catalog_needles": ("action", "decision"),
    },
)

KIND_OF_COLLECTION = {h["collection"]: h["to_kind"] for h in HOPS}
KIND_OF_COLLECTION["ideas"] = "idea"
SENTENCE_CITE_KINDS = frozenset({"decision", "action_plan"})
SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def load_council(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path} is not an object")
    return doc


def split_sentences(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [p.strip() for p in SPLIT_RE.split(text) if p.strip()]


def index_nodes(council: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}

    def add(kind: str, record: dict[str, Any], parents: list[str]) -> None:
        nid = record.get("id")
        if not isinstance(nid, str) or not nid:
            raise ValueError(f"{kind} record missing id")
        if nid in nodes:
            raise ValueError(f"duplicate id {nid}")
        nodes[nid] = {
            "id": nid,
            "kind": kind,
            "parents": list(parents),
            "record": record,
        }

    for rec in council.get("ideas") or []:
        add("idea", rec, [])
    for hop in HOPS:
        for rec in council.get(hop["collection"]) or []:
            parents = rec.get(hop["parent_field"]) or []
            if not isinstance(parents, list) or not all(isinstance(x, str) for x in parents):
                raise ValueError(
                    f"{rec.get('id')} field {hop['parent_field']} must be a string list"
                )
            add(hop["to_kind"], rec, parents)
    return nodes


def listed_sentences(council: dict[str, Any]) -> list[dict[str, Any]]:
    rec = council.get("recommendation") or {}
    listed = rec.get("sentences") or []
    if not isinstance(listed, list) or not listed:
        raise ValueError("recommendation.sentences must be a non-empty list")
    prose = split_sentences(str(rec.get("text") or ""))
    texts = [str(s.get("text") or "").strip() for s in listed]
    if texts != prose:
        raise ValueError(
            f"recommendation.sentences do not match split(text): listed={texts!r} split={prose!r}"
        )
    return listed


def _parents_of(nodes: dict[str, dict[str, Any]], nid: str) -> list[str]:
    row = nodes.get(nid)
    if row is None:
        return []
    return list(row["parents"])


def chase_ideas(nodes: dict[str, dict[str, Any]], start_id: str) -> set[str]:
    """Signal 1: recursive parent chase. Ideas are terminals (empty parents)."""
    found: set[str] = set()
    seen: set[str] = set()
    stack = [start_id]
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        row = nodes.get(nid)
        if row is None:
            continue
        if row["kind"] == "idea":
            found.add(nid)
            continue
        stack.extend(row["parents"])
    return found


def join_ideas(nodes: dict[str, dict[str, Any]], start_id: str) -> set[str]:
    """Signal 2: relational join expanding (id -> parent) until kind==idea.

    Different mechanism from chase_ideas: iterative frontier + parent relation
    as a set of tuples, not a stack walk of node records.
    """
    relation = {(nid, p) for nid, row in nodes.items() for p in row["parents"]}
    kind_of = {nid: row["kind"] for nid, row in nodes.items()}
    frontier = {start_id}
    seen: set[str] = set()
    ideas: set[str] = set()
    while frontier:
        nxt: set[str] = set()
        for nid in frontier:
            if nid in seen:
                continue
            seen.add(nid)
            if kind_of.get(nid) == "idea":
                ideas.add(nid)
                continue
            nxt.update(p for (a, p) in relation if a == nid)
        frontier = nxt
    return ideas


def sentence_report(
    council: dict[str, Any],
    *,
    walker: str = "chase",
) -> dict[str, Any]:
    nodes = index_nodes(council)
    walk = chase_ideas if walker == "chase" else join_ideas
    rows = []
    for sent in listed_sentences(council):
        sid = str(sent.get("id") or "")
        cites = sent.get("cites") or []
        if not isinstance(cites, list) or not all(isinstance(x, str) for x in cites):
            raise ValueError(f"{sid} cites must be a string list")
        illegal = []
        dangling = []
        ideas: set[str] = set()
        for cid in cites:
            row = nodes.get(cid)
            if row is None:
                dangling.append(cid)
                continue
            if row["kind"] not in SENTENCE_CITE_KINDS:
                illegal.append({"id": cid, "kind": row["kind"]})
                continue
            ideas.update(walk(nodes, cid))
        orphan_reasons = []
        if not cites:
            orphan_reasons.append("empty-cites")
        if dangling:
            orphan_reasons.append("dangling-cite")
        if illegal:
            orphan_reasons.append("illegal-cite-kind")
        if not ideas:
            orphan_reasons.append("no-idea-reached")
        rows.append(
            {
                "id": sid,
                "text": sent.get("text"),
                "cites": cites,
                "ideas": sorted(ideas),
                "dangling": dangling,
                "illegal": illegal,
                "orphan": bool(orphan_reasons),
                "orphan_reasons": orphan_reasons,
            }
        )
    orphans = [r["id"] for r in rows if r["orphan"]]
    return {
        "walker": walker,
        "sentence_count": len(rows),
        "resolved_count": sum(1 for r in rows if not r["orphan"]),
        "orphan_ids": orphans,
        "pass": len(orphans) == 0,
        "sentences": rows,
    }


def both_walkers_agree(council: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    a = sentence_report(council, walker="chase")
    b = sentence_report(council, walker="join")
    if a["orphan_ids"] != b["orphan_ids"] or a["pass"] != b["pass"]:
        raise ValueError(
            f"walker disagreement chase={a['orphan_ids']} join={b['orphan_ids']}"
        )
    for ra, rb in zip(a["sentences"], b["sentences"]):
        if ra["ideas"] != rb["ideas"]:
            raise ValueError(
                f"walker disagreement on {ra['id']}: chase={ra['ideas']} join={rb['ideas']}"
            )
    return a, b


def hop_parent_field(from_kind: str, to_kind: str) -> str:
    for hop in HOPS:
        if hop["from_kind"] == from_kind and hop["to_kind"] == to_kind:
            return hop["parent_field"]
    raise KeyError((from_kind, to_kind))


def iter_hops() -> Iterable[dict[str, Any]]:
    return HOPS
