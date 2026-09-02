#!/usr/bin/env python3
"""Mechanical unanswered-rebuttal / unsupported-claim checkers for RES-0085.

Formats:
  ibis     — Issue / Position / Argument with supports + objects-to
  toulmin  — Claim / Data / Warrant / Backing / Qualifier / Rebuttal
  dung_af  — Dung argumentation framework (AR, attacks)

A check is "written" only if it names a field and returns a concrete id list.
Uncheckable checks raise Uncheckable (they must not be silent-green).
"""
from __future__ import annotations

from typing import Any, Iterable

UNCHECKABLE = "uncheckable"
TOO_COSTLY = "too_costly_to_emit"
CHECKABLE = "checkable"


class Uncheckable(Exception):
    """Named hole: the format has no field the check can read."""

    def __init__(self, format_id: str, check_id: str, reason: str):
        super().__init__(reason)
        self.format_id = format_id
        self.format_id = format_id
        self.check_id = check_id
        self.reason = reason


def _ids(items: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for x in items:
        if isinstance(x, dict) and x.get("id"):
            out.append(str(x["id"]))
        elif isinstance(x, (list, tuple)) and len(x) >= 2:
            out.append(f"{x[0]}->{x[1]}")
        else:
            out.append(str(x))
    return out


# --- IBIS -----------------------------------------------------------------

IBIS_UNANSWERED_REBUTTAL_PSEUDOCODE = """
# named fields: nodes[].type in {issue, position, argument}
#               edges[].rel in {responds-to, supports, objects-to}
#               edges[].src, edges[].dst
def ibis_unanswered_rebuttals(graph):
    nodes = {n.id: n for n in graph.nodes}
    incoming_objects = {}
    for e in graph.edges:
        if e.rel == "objects-to":
            incoming_objects.setdefault(e.dst, []).append(e.src)
    unanswered = []
    for e in graph.edges:
        if e.rel != "objects-to":
            continue
        target = nodes.get(e.dst)
        # only cons against positions (a reply to a con is not itself a
        # position-level unanswered rebuttal; finite reply chains must terminate)
        if not target or target.type != "position":
            continue
        attacker = e.src
        if not incoming_objects.get(attacker):
            unanswered.append(e)
    return unanswered
""".strip()

IBIS_UNSUPPORTED_PSEUDOCODE = """
def ibis_unsupported_positions(graph):
    positions = [n.id for n in graph.nodes if n.type == "position"]
    supported = {e.dst for e in graph.edges if e.rel == "supports"}
    return [p for p in positions if p not in supported]
""".strip()


def ibis_unanswered_rebuttals(graph: dict) -> list[dict]:
    nodes = {
        str(n.get("id") or ""): n
        for n in (graph.get("nodes") or [])
        if n.get("id")
    }
    incoming: dict[str, list[str]] = {}
    for e in graph.get("edges") or []:
        if str(e.get("rel") or "") == "objects-to":
            incoming.setdefault(str(e.get("dst") or ""), []).append(str(e.get("src") or ""))
    hits = []
    for e in graph.get("edges") or []:
        if str(e.get("rel") or "") != "objects-to":
            continue
        dst = str(e.get("dst") or "")
        target = nodes.get(dst) or {}
        if str(target.get("type") or "") != "position":
            continue
        attacker = str(e.get("src") or "")
        if not incoming.get(attacker):
            hits.append(
                {
                    "id": f"{attacker}->{dst}",
                    "attacker": attacker,
                    "target": dst,
                    "rel": "objects-to",
                }
            )
    return hits


def ibis_unsupported_positions(graph: dict) -> list[str]:
    positions = [
        str(n.get("id") or "")
        for n in (graph.get("nodes") or [])
        if str(n.get("type") or "") == "position" and n.get("id")
    ]
    supported = {
        str(e.get("dst") or "")
        for e in (graph.get("edges") or [])
        if str(e.get("rel") or "") == "supports"
    }
    return [p for p in positions if p not in supported]


def check_ibis(graph: dict) -> dict:
    unanswered = ibis_unanswered_rebuttals(graph)
    unsupported = ibis_unsupported_positions(graph)
    return {
        "format": "ibis",
        "checkable": True,
        "unanswered_rebuttals": unanswered,
        "unsupported_claims": unsupported,
        "fires": bool(unanswered or unsupported),
    }


# --- Toulmin --------------------------------------------------------------

TOULMIN_UNSUPPORTED_PSEUDOCODE = """
# named fields: claim.data (grounds). Empty/missing data => unsupported claim.
def toulmin_unsupported(record):
    data = (record.data or "").strip()
    if not data:
        return [record.id]
    return []
""".strip()

TOULMIN_UNANSWERED_REBUTTAL_NOTE = (
    "UNCHECKABLE on classic six-element Toulmin: Rebuttal is an 'unless' "
    "circumstance attached to the warrant, not a node that can be answered. "
    "There is no named field for a reply-to-rebuttal. A check that looked at "
    "record.rebuttal being non-empty would only detect presence of a caveat, "
    "not whether it was answered. Marked uncheckable rather than faked."
)


def toulmin_unsupported(record: dict) -> list[str]:
    data = str(record.get("data") or record.get("grounds") or "").strip()
    if not data:
        return [str(record.get("id") or "claim")]
    return []


def toulmin_unanswered_rebuttals(record: dict) -> list[dict]:
    raise Uncheckable(
        "toulmin",
        "unanswered_rebuttal",
        TOULMIN_UNANSWERED_REBUTTAL_NOTE,
    )


def check_toulmin(record: dict) -> dict:
    unsupported = toulmin_unsupported(record)
    unanswered_status = UNCHECKABLE
    unanswered: list[dict] = []
    try:
        toulmin_unanswered_rebuttals(record)
    except Uncheckable:
        pass
    return {
        "format": "toulmin",
        "checkable_unsupported": True,
        "checkable_unanswered_rebuttal": False,
        "unanswered_rebuttal_status": unanswered_status,
        "unanswered_rebuttals": unanswered,
        "unsupported_claims": unsupported,
        "fires": bool(unsupported),
    }


# --- Dung AF --------------------------------------------------------------

DUNG_UNANSWERED_REBUTTAL_PSEUDOCODE = """
# named fields: arguments[] (AR), attacks[] as (B, A) meaning B attacks A
# Unanswered rebuttal := attack (B, A) whose attacker B has no attacker
# (B is not acceptable-defeated; cf. Dung 1995 Def. 6 acceptability).
def dung_unanswered_rebuttals(af):
    attacked_by = {}
    for (b, a) in af.attacks:
        attacked_by.setdefault(a, []).append(b)
    unanswered = []
    for (b, a) in af.attacks:
        if not attacked_by.get(b):
            unanswered.append((b, a))
    return unanswered
""".strip()

DUNG_UNSUPPORTED_NOTE = (
    "UNCHECKABLE natively: a Dung AF has only an attack relation. There is no "
    "support/grounds field, so 'unsupported claim' has no named field to read. "
    "Bipolar AFs add support; that is a different format."
)

DUNG_EMIT_COST_NOTE = (
    "TOO COSTLY for an agent to emit reliably: the agent must segment natural "
    "language into atomic arguments and a binary attack relation (argument "
    "mining). Computing grounded/admissible semantics is cheap once the graph "
    "exists; emitting the graph from council turns is the expensive, lossy step. "
    "Council IMP-0313 already asks for SUPPORTS/ATTACKS/REBUTS on turns — that "
    "is IBIS-shaped, not a Dung AF."
)


def dung_unanswered_rebuttals(af: dict) -> list[dict]:
    attacks = [tuple(x) for x in (af.get("attacks") or [])]
    attacked_by: dict[str, list[str]] = {}
    for pair in attacks:
        if len(pair) < 2:
            continue
        b, a = str(pair[0]), str(pair[1])
        attacked_by.setdefault(a, []).append(b)
    hits = []
    for pair in attacks:
        if len(pair) < 2:
            continue
        b, a = str(pair[0]), str(pair[1])
        if not attacked_by.get(b):
            hits.append({"id": f"{b}->{a}", "attacker": b, "target": a})
    return hits


def dung_unsupported(af: dict) -> list[str]:
    raise Uncheckable("dung_af", "unsupported_claim", DUNG_UNSUPPORTED_NOTE)


def check_dung(af: dict) -> dict:
    unanswered = dung_unanswered_rebuttals(af)
    unsupported_status = UNCHECKABLE
    try:
        dung_unsupported(af)
    except Uncheckable:
        pass
    return {
        "format": "dung_af",
        "checkable_unanswered_rebuttal": True,
        "checkable_unsupported": False,
        "unsupported_status": unsupported_status,
        "emit_cost": TOO_COSTLY,
        "unanswered_rebuttals": unanswered,
        "unsupported_claims": [],
        "fires": bool(unanswered),
    }


FORMAT_ROWS = [
    {
        "id": "ibis",
        "name": "IBIS / gIBIS (Issue, Position, Argument)",
        "checkability_unanswered_rebuttal": CHECKABLE,
        "checkability_unsupported_claim": CHECKABLE,
        "emit_cost": "cheap",
        "emit_cost_reason": (
            "Three node types and two edge types (supports, objects-to). "
            "Agents already emit issue/position/pro/con trees."
        ),
        "unanswered_rebuttal_check": IBIS_UNANSWERED_REBUTTAL_PSEUDOCODE,
        "unsupported_claim_check": IBIS_UNSUPPORTED_PSEUDOCODE,
        "recommended_for_council": True,
    },
    {
        "id": "toulmin",
        "name": "Toulmin six-element layout",
        "checkability_unanswered_rebuttal": UNCHECKABLE,
        "checkability_unsupported_claim": CHECKABLE,
        "emit_cost": "medium",
        "emit_cost_reason": (
            "Six named slots; agents typically fill Claim+Data and skip "
            "Warrant/Backing. Rebuttal slot exists but is not a reply graph."
        ),
        "unanswered_rebuttal_check": TOULMIN_UNANSWERED_REBUTTAL_NOTE,
        "unsupported_claim_check": TOULMIN_UNSUPPORTED_PSEUDOCODE,
        "recommended_for_council": False,
    },
    {
        "id": "dung_af",
        "name": "Dung abstract argumentation framework",
        "checkability_unanswered_rebuttal": CHECKABLE,
        "checkability_unsupported_claim": UNCHECKABLE,
        "emit_cost": TOO_COSTLY,
        "emit_cost_reason": DUNG_EMIT_COST_NOTE,
        "unanswered_rebuttal_check": DUNG_UNANSWERED_REBUTTAL_PSEUDOCODE,
        "unsupported_claim_check": DUNG_UNSUPPORTED_NOTE,
        "recommended_for_council": False,
    },
]


def format_comparison() -> list[dict]:
    return list(FORMAT_ROWS)


format_comparison = format_comparison


def evaluate_all(ibis: dict, toulmin: dict, dung: dict) -> dict:
    return {
        "ibis": check_ibis(ibis),
        "toulmin": check_toulmin(toulmin),
        "dung_af": check_dung(dung),
    }


format_comparison = format_comparison
