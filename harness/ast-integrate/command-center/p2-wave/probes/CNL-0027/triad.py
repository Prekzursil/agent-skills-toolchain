#!/usr/bin/env python3
"""Closed-world triad mandate checker for CNL-0027.

A synthesiser may cite filed option_ids and objection_ids. Minting a new
option_id is second-proposer drift. Minting a new objection_id is
third-critic drift. Prompt labels are not the enforcement mechanism.
"""
from __future__ import annotations

from typing import Any, Iterable

FORBIDDEN_MINT_KEYS = frozenset(
    {
        "new_proposal",
        "new_option",
        "minted_option",
        "fresh_proposal",
        "alternative_option",
        "new_critique",
        "new_objection",
        "minted_objection",
        "fresh_objection",
    }
)
OPTION_LIST_KEYS = frozenset(
    {"selects", "selects_from", "ranked_option_ids", "adopted_options"}
)
OBJECTION_LIST_KEYS = frozenset(
    {"addresses", "unresolved", "preserves_dissent", "objection_ids"}
)


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item:
                out.append(item)
            elif isinstance(item, dict):
                oid = item.get("option_id") or item.get("objection_id")
                if isinstance(oid, str) and oid:
                    out.append(oid)
        return out
    return []


def filed_option_ids(round_doc: dict[str, Any]) -> set[str]:
    return {
        str(p["option_id"])
        for p in (round_doc.get("proposals") or [])
        if isinstance(p, dict) and p.get("option_id")
    }


def filed_objection_ids(round_doc: dict[str, Any]) -> set[str]:
    return {
        str(c["objection_id"])
        for c in (round_doc.get("critiques") or [])
        if isinstance(c, dict) and c.get("objection_id")
    }


def harvest_synthesis(synth: Any) -> dict[str, Any]:
    """Walk the synthesis object. Distinct from probe2's top-level-only read."""
    cited_options: set[str] = set()
    cited_objections: set[str] = set()
    forbidden_hits: list[str] = []
    inline_mints: list[str] = []

    def walk(node: Any, key: str | None = None) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in FORBIDDEN_MINT_KEYS and v not in (None, "", [], {}):
                    forbidden_hits.append(k)
                    if isinstance(v, dict) and v.get("option_id"):
                        inline_mints.append(str(v["option_id"]))
                    elif isinstance(v, dict) and v.get("objection_id"):
                        inline_mints.append(str(v["objection_id"]))
                    elif isinstance(v, str):
                        inline_mints.append(v)
                if k == "option_id" and isinstance(v, str) and v:
                    cited_options.add(v)
                if k == "objection_id" and isinstance(v, str) and v:
                    cited_objections.add(v)
                if k in OPTION_LIST_KEYS:
                    cited_options.update(_as_str_list(v))
                if k in OBJECTION_LIST_KEYS:
                    cited_objections.update(_as_str_list(v))
                if k == "recommendations" and isinstance(v, list):
                    for rec in v:
                        if not isinstance(rec, dict):
                            continue
                        if rec.get("option_id"):
                            cited_options.add(str(rec["option_id"]))
                        if rec.get("proposal_text") and not rec.get("option_id"):
                            inline_mints.append("recommendation-without-option-id")
                walk(v, k)
        elif isinstance(node, list):
            for item in node:
                walk(item, key)

    walk(synth)
    return {
        "cited_options": cited_options,
        "cited_objections": cited_objections,
        "forbidden_hits": forbidden_hits,
        "inline_mints": inline_mints,
    }


def critic_minted_options(round_doc: dict[str, Any], filed_opt: set[str]) -> set[str]:
    minted: set[str] = set()
    for c in round_doc.get("critiques") or []:
        if not isinstance(c, dict):
            continue
        extra = c.get("option_id")
        if isinstance(extra, str) and extra and extra not in filed_opt:
            minted.add(extra)
        proposal = c.get("new_proposal") or c.get("counter_proposal")
        if isinstance(proposal, dict) and proposal.get("option_id"):
            oid = str(proposal["option_id"])
            if oid not in filed_opt:
                minted.add(oid)
        elif isinstance(proposal, str) and proposal and proposal not in filed_opt:
            minted.add(proposal)
    return minted


def proposer_minted_objections(
    round_doc: dict[str, Any], filed_obj: set[str]
) -> set[str]:
    minted: set[str] = set()
    for p in round_doc.get("proposals") or []:
        if not isinstance(p, dict):
            continue
        extra = p.get("objection_id")
        if isinstance(extra, str) and extra and extra not in filed_obj:
            minted.add(extra)
    return minted


def check(round_doc: dict[str, Any]) -> dict[str, Any]:
    """FIRES when a seat exceeds its mandate. SILENT on a closed-world round."""
    reasons: list[str] = []
    filed_opt = filed_option_ids(round_doc)
    filed_obj = filed_objection_ids(round_doc)
    proposals = round_doc.get("proposals") or []
    critiques = round_doc.get("critiques") or []
    synth = round_doc.get("synthesis")

    if not proposals:
        reasons.append("unmet-proposer-obligation")
    if not critiques:
        reasons.append("unmet-critic-obligation")
    if not isinstance(synth, dict) or not synth:
        reasons.append("unmet-synthesiser-obligation")
        harvest = {
            "cited_options": set(),
            "cited_objections": set(),
            "forbidden_hits": [],
            "inline_mints": [],
        }
    else:
        harvest = harvest_synthesis(synth)

    critic_opts = critic_minted_options(round_doc, filed_opt)
    if critic_opts:
        reasons.append("critic-as-proposer:" + ",".join(sorted(critic_opts)))
    proposer_objs = proposer_minted_objections(round_doc, filed_obj)
    if proposer_objs:
        reasons.append("proposer-as-critic:" + ",".join(sorted(proposer_objs)))

    cited_opt = set(harvest["cited_options"])
    cited_obj = set(harvest["cited_objections"])
    minted_opt = (cited_opt - filed_opt) | set(harvest["inline_mints"])
    minted_opt = {m for m in minted_opt if m not in filed_opt}
    minted_obj = cited_obj - filed_obj

    if harvest["forbidden_hits"]:
        reasons.append(
            "forbidden-mint-key:" + ",".join(sorted(set(harvest["forbidden_hits"])))
        )
    if minted_opt:
        reasons.append("synthesiser-as-proposer:" + ",".join(sorted(minted_opt)))
    if minted_obj:
        reasons.append("synthesiser-as-critic:" + ",".join(sorted(minted_obj)))

    if isinstance(synth, dict) and synth:
        selects = set(_as_str_list(synth.get("selects")))
        if not selects:
            reasons.append("unmet-synthesiser-selects")
        unknown_selects = selects - filed_opt
        if unknown_selects:
            # already covered by minted_opt; keep a dedicated reason
            if "synthesiser-as-proposer:" + ",".join(sorted(unknown_selects)) not in reasons:
                reasons.append(
                    "synthesiser-as-proposer:" + ",".join(sorted(unknown_selects))
                )

    filed = filed_opt | filed_obj
    cited_in = (cited_opt | cited_obj) & filed
    coverage = (len(cited_in) / float(len(filed))) if filed else 0.0
    fires = bool(reasons)
    joint = 0.0 if fires else 1.0
    return {
        "fires": fires,
        "silent": not fires,
        "reasons": reasons,
        "filed_option_ids": sorted(filed_opt),
        "filed_objection_ids": sorted(filed_obj),
        "cited_option_ids": sorted(cited_opt),
        "cited_objection_ids": sorted(cited_obj),
        "minted_option_ids": sorted(minted_opt),
        "minted_objection_ids": sorted(minted_obj),
        "forbidden_hits": list(harvest["forbidden_hits"]),
        "coverage": coverage,
        "joint": joint,
        "reason": reasons[0] if reasons else "closed-world-ok",
    }


def fmt(row: dict[str, Any]) -> str:
    return (
        f"fires={row['fires']} silent={row['silent']} "
        f"coverage={row['coverage']:.12f} joint={row['joint']:.12f} "
        f"reason={row['reason']} minted_opt={row['minted_option_ids']} "
        f"minted_obj={row['minted_objection_ids']}"
    )


def iter_rounds(rounds: Iterable[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    out = []
    for name, doc in rounds:
        row = check(doc)
        row["name"] = name
        out.append(row)
    return out
