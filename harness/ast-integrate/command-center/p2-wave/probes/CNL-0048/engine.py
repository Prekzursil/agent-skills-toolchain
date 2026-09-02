"""CNL-0048 response-obligation and rebuttal-depth primitive.

A seat is obliged to answer only when a named addressee is recorded on an
accepted node whose reply hop still fits the depth budget.
NAMED_ADDRESSEE_REQUIRED

Discharge requires kind in {rebuttal, concession, explicit_pass} that
addresses the obligated claim_id. topic_change / acknowledgement / utterance
do not discharge. NON_ANSWER_DOES_NOT_DISCHARGE

Synthesis keeps remaining OPEN obligations on the argument graph as IGNORED.
Dropping them is the silent-loss failure the ignored-argument fixture exists
to catch. IGNORED_SURVIVES_SYNTHESIS

Rebuttal depth is hop-count from the root (parent walk). Exhaustion
HARD-STOPS the next hop: the would-be node is refused and the would-be
obligation is CUT_BY_DEPTH. A cut is not consensus and is not an ignore.
DEPTH_HARD_STOP_NOT_CONSENSUS
"""
from __future__ import annotations

from typing import Any

DISCHARGE_KINDS = frozenset({"rebuttal", "concession", "explicit_pass"})


def hop_depth(nodes: dict[str, dict], parent_id: str | None) -> int:
    """Depth of a new node under parent_id. Independent of any stored depth field."""
    if not parent_id:
        return 0
    depth = 1
    seen: set[str] = set()
    cur: str | None = parent_id
    while cur:
        if cur in seen:
            raise ValueError(f"cycle in parent chain at {cur}")
        seen.add(cur)
        node = nodes.get(cur)
        if not node:
            raise ValueError(f"missing parent {cur}")
        nxt = node.get("parent_id")
        if not nxt:
            return depth
        depth += 1
        cur = str(nxt)
    return depth


def _obl_id(source_node_id: str) -> str:
    return f"obl:{source_node_id}"


def apply_turns(
    turns: list[dict],
    budget: int,
    *,
    drop_ignored: bool = False,
) -> dict[str, Any]:
    """Accept turns in order, enforce depth, create/discharge obligations.

    drop_ignored=True is the silent-drop mutant used as a negative control.
    The real engine never sets that flag.
    """
    nodes: dict[str, dict] = {}
    obligations: dict[str, dict] = {}
    cuts: list[dict] = []
    rejected: list[dict] = []

    for raw in turns:
        turn = dict(raw)
        nid = str(turn["id"])
        parent_id = turn.get("parent_id")
        parent_id = str(parent_id) if parent_id else None
        try:
            depth = hop_depth(nodes, parent_id)
        except ValueError as exc:
            rejected.append({"id": nid, "reason": str(exc)})
            continue
        if depth > budget:
            cuts.append(
                {
                    "id": f"cut:{nid}",
                    "would_be_node": nid,
                    "author": turn.get("author"),
                    "depth": depth,
                    "budget": budget,
                    "status": "CUT_BY_DEPTH",
                }
            )
            rejected.append({"id": nid, "reason": f"depth {depth} > budget {budget}"})
            continue

        node = {
            "id": nid,
            "author": str(turn.get("author") or ""),
            "kind": str(turn.get("kind") or "utterance"),
            "parent_id": parent_id,
            "claim_id": str(turn.get("claim_id") or turn.get("addresses_claim_id") or ""),
            "addresses_claim_id": str(
                turn.get("addresses_claim_id") or turn.get("claim_id") or ""
            ),
            "requires_response": bool(turn.get("requires_response")),
            "addressee": str(turn.get("addressee") or ""),
            "depth": depth,
        }
        nodes[nid] = node

        if node["kind"] in DISCHARGE_KINDS:
            for obl in obligations.values():
                if obl["status"] != "OPEN":
                    continue
                if obl["addressee"] != node["author"]:
                    continue
                if obl["claim_id"] != node["addresses_claim_id"]:
                    continue
                obl["status"] = "ANSWERED"
                obl["discharged_by"] = nid

        if node["requires_response"]:
            if not node["addressee"]:
                cuts.append(
                    {
                        "id": f"cut-unnamed:{nid}",
                        "would_be_node": nid,
                        "reason": "requires_response without named addressee creates no obligation",
                        "status": "NO_OBLIGATION",
                    }
                )
            elif depth + 1 > budget:
                oid = _obl_id(nid)
                obligations[oid] = {
                    "id": oid,
                    "source_node_id": nid,
                    "claim_id": node["claim_id"],
                    "addressee": node["addressee"],
                    "author": node["author"],
                    "reply_depth": depth + 1,
                    "budget": budget,
                    "status": "CUT_BY_DEPTH",
                }
            else:
                oid = _obl_id(nid)
                obligations[oid] = {
                    "id": oid,
                    "source_node_id": nid,
                    "claim_id": node["claim_id"],
                    "addressee": node["addressee"],
                    "author": node["author"],
                    "reply_depth": depth + 1,
                    "budget": budget,
                    "status": "OPEN",
                }

    graph_nodes: list[dict] = []
    for node in nodes.values():
        graph_nodes.append(dict(node, record="turn"))
    synthesized_obl: list[dict] = []
    ignored_ids: list[str] = []
    for obl in obligations.values():
        row = dict(obl)
        if row["status"] == "OPEN":
            row["status"] = "IGNORED"
            ignored_ids.append(row["id"])
        if drop_ignored and row["status"] == "IGNORED":
            continue
        synthesized_obl.append(row)
        graph_nodes.append(
            {
                "id": row["id"],
                "record": "obligation",
                "status": row["status"],
                "claim_id": row["claim_id"],
                "addressee": row["addressee"],
                "source_node_id": row["source_node_id"],
            }
        )
    for cut in cuts:
        graph_nodes.append(dict(cut, record="cut"))

    synthesized_ignored = [o["id"] for o in synthesized_obl if o["status"] == "IGNORED"]
    unanswered_fires = bool(synthesized_ignored)
    pre_ids = set(obligations)
    post_ids = {o["id"] for o in synthesized_obl}
    silent_drop_ids = sorted(pre_ids - post_ids)

    ignored_visible = (not drop_ignored) and all(
        any(n.get("id") == oid and n.get("status") == "IGNORED" for n in graph_nodes)
        for oid in ignored_ids
    )

    return {
        "nodes": nodes,
        "obligations_pre_synthesis": obligations,
        "obligations": synthesized_obl,
        "graph": {"nodes": graph_nodes},
        "cuts": cuts,
        "rejected": rejected,
        "ignored_ids": ignored_ids,
        "synthesized_ignored_ids": synthesized_ignored,
        "unanswered_fires": unanswered_fires,
        "silent_drop_ids": silent_drop_ids,
        "silent_drop_fires": bool(silent_drop_ids),
        "ignored_visible": ignored_visible,
        "drop_ignored": drop_ignored,
        "budget": budget,
    }


def independent_recount(turns: list[dict], budget: int) -> dict[str, Any]:
    """Set-algebra recount: created − discharged − cut. Does not read status labels."""
    nodes: dict[str, dict] = {}
    created: set[str] = set()
    cut: set[str] = set()
    discharged: set[str] = set()
    addressee_of: dict[str, str] = {}
    claim_of: dict[str, str] = {}

    for raw in turns:
        nid = str(raw["id"])
        parent_id = raw.get("parent_id")
        parent_id = str(parent_id) if parent_id else None
        try:
            depth = hop_depth(nodes, parent_id)
        except ValueError:
            continue
        if depth > budget:
            continue
        node = {
            "parent_id": parent_id,
            "author": str(raw.get("author") or ""),
            "kind": str(raw.get("kind") or ""),
            "claim_id": str(raw.get("claim_id") or raw.get("addresses_claim_id") or ""),
            "addresses_claim_id": str(
                raw.get("addresses_claim_id") or raw.get("claim_id") or ""
            ),
            "requires_response": bool(raw.get("requires_response")),
            "addressee": str(raw.get("addressee") or ""),
        }
        nodes[nid] = node
        if node["kind"] in DISCHARGE_KINDS:
            for other_oid in list(created):
                if other_oid in discharged or other_oid in cut:
                    continue
                if addressee_of[other_oid] != node["author"]:
                    continue
                if claim_of[other_oid] != node["addresses_claim_id"]:
                    continue
                discharged.add(other_oid)
        if node["requires_response"] and node["addressee"]:
            oid = _obl_id(nid)
            if depth + 1 > budget:
                cut.add(oid)
                addressee_of[oid] = node["addressee"]
                claim_of[oid] = node["claim_id"]
            else:
                created.add(oid)
                addressee_of[oid] = node["addressee"]
                claim_of[oid] = node["claim_id"]

    ignored = created - discharged - cut
    return {
        "created": sorted(created),
        "discharged": sorted(discharged),
        "cut": sorted(cut),
        "ignored": sorted(ignored),
        "unanswered_fires": bool(ignored),
        "mechanism": "set-algebra created-minus-discharged-minus-cut",
    }


def verbatim_check(label: str, result: dict[str, Any]) -> str:
    ignored = result.get("synthesized_ignored_ids")
    if ignored is None:
        ignored = result.get("ignored_ids")
    return (
        f"{label} unanswered_fires={result['unanswered_fires']} "
        f"ignored={ignored} "
        f"silent_drop={result.get('silent_drop_ids', [])} "
        f"ignored_visible={result.get('ignored_visible')} "
        f"cuts={[c.get('id') for c in result.get('cuts') or []]}"
    )
