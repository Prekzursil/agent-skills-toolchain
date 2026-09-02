"""Typed argument graph extracted from a council transcript (IMP-0313).

Claims are introduced by turns of the form ``CLAIM-<id>: <text>``. Relations
between two *identified* claims are extracted from the turn text with one of
three legal edge types — ``SUPPORTS``, ``ATTACKS``, ``REBUTS`` — and every edge
carries the ``turn_id`` of the turn that asserted it. Ordinary language that
uses support/attack/rebut without claim identifiers is not an edge.

The extractor reads only ``turn_id``, ``speaker`` and ``text``; any other field
on a turn (labels, annotations) is never extraction input.

``validate_graph`` fails closed: an edge whose ``turn_id`` does not resolve to
a turn of the transcript (including an empty id) raises
``UnresolvableTurnId``; illegal relation types, unknown claim ids and
self-loops raise ``InvalidEdge``. Precision and recall against a gold key are
reported separately — there is no single accuracy figure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

SUPPORTS = "SUPPORTS"
ATTACKS = "ATTACKS"
REBUTS = "REBUTS"
EDGE_TYPES = (SUPPORTS, ATTACKS, REBUTS)

_CLAIM_ID = r"CLAIM-(c\d+)"
_CLAIM_INTRO_RE = re.compile(rf"^\s*{_CLAIM_ID}\s*:\s*(?P<body>.*?)\s*$", re.DOTALL)

# cue phrase (as written in the transcript) -> edge type
_CUES: dict[str, str] = {
    "SUPPORTS": SUPPORTS,
    "supports": SUPPORTS,
    "in support of": SUPPORTS,
    "ATTACKS": ATTACKS,
    "attacks": ATTACKS,
    "is incompatible with": ATTACKS,
    "undermines": ATTACKS,
    "REBUTS": REBUTS,
    "rebuts": REBUTS,
    "rebuts the attack in": REBUTS,
}
_CUE_ALTERNATION = "|".join(
    re.escape(c) for c in sorted(_CUES, key=len, reverse=True)
)
_RELATION_RE = re.compile(
    rf"{_CLAIM_ID}\s+(?P<cue>{_CUE_ALTERNATION})\s+{_CLAIM_ID}"
)


class ArgumentGraphError(ValueError):
    """Base class for graph validation failures."""


class UnresolvableTurnId(ArgumentGraphError):
    """An edge cites a turn id that is not in the transcript."""

    def __init__(self, unresolvable_turn_ids: list[str]) -> None:
        self.unresolvable_turn_ids = list(unresolvable_turn_ids)
        shown = ", ".join(repr(t) for t in self.unresolvable_turn_ids[:8])
        super().__init__(
            f"{len(self.unresolvable_turn_ids)} edge turn id(s) do not resolve "
            f"to a transcript turn: {shown}"
        )


class InvalidEdge(ArgumentGraphError):
    """An edge is malformed: illegal type, unknown claim, or self-loop."""


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    turn_id: str
    speaker: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "turn_id": self.turn_id,
            "speaker": self.speaker,
        }


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    relation: str
    turn_id: str
    speaker: str = ""
    evidence_span: str = ""

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.source, self.target, self.relation, self.turn_id)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "edge_type": self.relation,
            "turn_id": self.turn_id,
            "speaker": self.speaker,
            "evidence_span": self.evidence_span,
        }


@dataclass
class ArgumentGraph:
    claims: dict[str, Claim] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "claims": {cid: c.as_dict() if isinstance(c, Claim) else c for cid, c in self.claims.items()},
            "edges": [e.as_dict() for e in self.edges],
            "n_claims": len(self.claims),
            "n_edges": len(self.edges),
        }


def _turn_fields(turn: Any) -> tuple[str, str, str]:
    if isinstance(turn, dict):
        return (
            str(turn.get("turn_id") or ""),
            str(turn.get("speaker") or ""),
            str(turn.get("text") or ""),
        )
    return (
        str(getattr(turn, "turn_id", "") or ""),
        str(getattr(turn, "speaker", "") or ""),
        str(getattr(turn, "text", "") or ""),
    )


def extract_claim(turn: Any) -> Claim | None:
    turn_id, speaker, text = _turn_fields(turn)
    m = _CLAIM_INTRO_RE.match(text)
    if not m:
        return None
    # a turn that introduces a claim AND relates it in the same breath is a
    # relation turn, not an introduction ("CLAIM-c1 SUPPORTS CLAIM-c2: why")
    if _RELATION_RE.search(text[: m.start("body")]):
        return None
    return Claim(claim_id=m.group(1), text=m.group("body"), turn_id=turn_id, speaker=speaker)


def extract_edges(turn: Any) -> list[Edge]:
    turn_id, speaker, text = _turn_fields(turn)
    out: list[Edge] = []
    for m in _RELATION_RE.finditer(text):
        source, target = m.group(1), m.group(3)
        if source == target:
            continue
        out.append(
            Edge(
                source=source,
                target=target,
                relation=_CUES[m.group("cue")],
                turn_id=turn_id,
                speaker=speaker,
                evidence_span=m.group(0),
            )
        )
    return out


def build_argument_graph(turns: Iterable[Any]) -> ArgumentGraph:
    """Extract typed claims and edges from transcript turns (text only)."""
    claims: dict[str, Claim] = {}
    edges: list[Edge] = []
    seen: set[tuple[str, str, str, str]] = set()
    for turn in turns:
        claim = extract_claim(turn)
        if claim is not None and claim.claim_id not in claims:
            # claim identity is fixed at introduction; later mentions do not rewrite it
            claims[claim.claim_id] = claim
        for edge in extract_edges(turn):
            if edge.key in seen:
                continue
            seen.add(edge.key)
            edges.append(edge)
    return ArgumentGraph(claims=claims, edges=edges)


def validate_graph(graph: ArgumentGraph, turns: Iterable[Any]) -> dict[str, Any]:
    """Every edge must cite a real turn, a legal type, known claims, no self-loop."""
    turn_ids = {_turn_fields(t)[0] for t in turns}
    turn_ids.discard("")
    unresolved = [e.turn_id for e in graph.edges if not e.turn_id or e.turn_id not in turn_ids]
    if unresolved:
        raise UnresolvableTurnId(unresolved)
    problems: list[str] = []
    for e in graph.edges:
        if e.relation not in EDGE_TYPES:
            problems.append(f"{e.source}->{e.target}@{e.turn_id}: illegal relation {e.relation!r}")
        if e.source == e.target:
            problems.append(f"{e.source}->{e.target}@{e.turn_id}: self-loop")
        for end in (e.source, e.target):
            if end not in graph.claims:
                problems.append(f"{e.source}->{e.target}@{e.turn_id}: unknown claim {end!r}")
    if problems:
        raise InvalidEdge("; ".join(problems[:8]))
    return {
        "ok": True,
        "n_claims": len(graph.claims),
        "n_edges": len(graph.edges),
        "n_turns": len(turn_ids),
    }


def edge_key(edge: Any) -> str:
    if isinstance(edge, Edge):
        s, t, r, tid = edge.key
    else:
        s = str(edge.get("source"))
        t = str(edge.get("target"))
        r = str(edge.get("relation") or edge.get("edge_type"))
        tid = str(edge.get("turn_id"))
    return f"{s}->{t}:{r}@{tid}"


def precision_recall(predicted: Iterable[Any], gold: Iterable[Any]) -> dict[str, Any]:
    """Precision and recall over (source, target, relation, turn_id) keys — separately."""
    pred_keys = {edge_key(e) for e in predicted}
    gold_keys = {edge_key(e) for e in gold}
    tp = pred_keys & gold_keys
    fp = pred_keys - gold_keys
    fn = gold_keys - pred_keys
    precision = len(tp) / len(pred_keys) if pred_keys else (1.0 if not gold_keys else 0.0)
    recall = len(tp) / len(gold_keys) if gold_keys else (1.0 if not pred_keys else 0.0)
    return {
        "precision": precision,
        "recall": recall,
        "true_positives": len(tp),
        "false_positives": len(fp),
        "false_negatives": len(fn),
        "n_predicted": len(pred_keys),
        "n_gold": len(gold_keys),
        "false_positive_keys": sorted(fp),
        "false_negative_keys": sorted(fn),
        "metric_note": "precision and recall reported separately; no single accuracy",
    }


__all__ = [
    "ATTACKS",
    "REBUTS",
    "SUPPORTS",
    "EDGE_TYPES",
    "ArgumentGraph",
    "ArgumentGraphError",
    "Claim",
    "Edge",
    "InvalidEdge",
    "UnresolvableTurnId",
    "build_argument_graph",
    "edge_key",
    "extract_claim",
    "extract_edges",
    "precision_recall",
    "validate_graph",
]
