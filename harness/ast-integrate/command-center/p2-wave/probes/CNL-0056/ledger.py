#!/usr/bin/env python3
"""Idea ledger v1: provenance fields and the two-signal disappearance check.

Identity is idea_id. Dedup identity is canonical_mechanism (CNL-0051). Surface
statement text is never the identity. Originator is immutable. Duplicates and
supporters are append-only edges. Fate is a closed vocabulary plus synthesis
node ids. A canonical idea (duplicate_of is null) silently disappears when
synthesis cites neither its idea_id nor its canonical_mechanism.
"""
from __future__ import annotations

from typing import Any

FATE_VOCAB = frozenset(
    {"ADOPTED", "MERGED", "REJECTED", "DEFERRED", "DISSENTED", "UNRESOLVED"}
)
STANCE_VOCAB = frozenset({"endorse", "second", "qualify", "oppose"})
REQUIRED_IDEA_KEYS = (
    "idea_id",
    "canonical_mechanism",
    "statement",
    "originator",
    "duplicate_of",
    "duplicates",
    "supporters",
    "fate",
)
REQUIRED_ORIGINATOR_KEYS = (
    "participant_id",
    "seat",
    "round",
    "seq",
    "recorded_at",
)


def is_canonical(row: dict) -> bool:
    dup = row.get("duplicate_of")
    return dup in (None, "", [])


def canonical_rows(ideas: list[dict]) -> list[dict]:
    return [row for row in ideas if is_canonical(row)]


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item:
            out.append(item)
    return out


def signal_a_missing_idea_ids(
    required: list[dict], nodes: list[dict]
) -> tuple[list[str], list[str], list[str]]:
    """Signal A: set difference on idea_id vs synthesis.cites_idea_ids."""
    required_ids = {str(row["idea_id"]) for row in required if row.get("idea_id")}
    cited: set[str] = set()
    for node in nodes:
        cited.update(_as_str_list(node.get("cites_idea_ids")))
    missing = sorted(required_ids - cited)
    return missing, sorted(required_ids), sorted(cited)


def signal_b_missing_mechanisms(
    required: list[dict], nodes: list[dict]
) -> tuple[list[str], list[str], list[str]]:
    """Signal B: set difference on canonical_mechanism vs covers_mechanisms.

    Different field from Signal A. A dummy cites_idea_ids dump cannot satisfy B.
    """
    required_mechs = {
        str(row["canonical_mechanism"])
        for row in required
        if row.get("canonical_mechanism")
    }
    covered: set[str] = set()
    for node in nodes:
        covered.update(_as_str_list(node.get("covers_mechanisms")))
    missing = sorted(required_mechs - covered)
    return missing, sorted(required_mechs), sorted(covered)


def validate_ledger(ideas: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    ids = {str(r.get("idea_id") or "") for r in ideas}
    for i, row in enumerate(ideas):
        if not isinstance(row, dict):
            errors.append(f"ideas[{i}] not an object")
            continue
        for key in REQUIRED_IDEA_KEYS:
            if key not in row:
                errors.append(f"ideas[{i}] missing {key}")
        iid = str(row.get("idea_id") or "")
        if not iid:
            errors.append(f"ideas[{i}] empty idea_id")
        elif iid in seen:
            errors.append(f"duplicate idea_id {iid}")
        else:
            seen.add(iid)
        origin = row.get("originator")
        if not isinstance(origin, dict):
            errors.append(f"{iid or i} originator not an object")
        else:
            for key in REQUIRED_ORIGINATOR_KEYS:
                if key not in origin or origin.get(key) in (None, ""):
                    errors.append(f"{iid} originator missing {key}")
        dup = row.get("duplicate_of")
        if dup not in (None, "", []) and str(dup) not in ids:
            errors.append(f"{iid} duplicate_of {dup} not in ledger")
        if dup not in (None, "", []) and str(dup) == iid:
            errors.append(f"{iid} duplicate_of self")
        fate = row.get("fate")
        if not isinstance(fate, dict):
            errors.append(f"{iid} fate not an object")
        else:
            status = str(fate.get("status") or "")
            if status not in FATE_VOCAB:
                errors.append(f"{iid} fate.status {status!r} not in vocabulary")
        for j, sup in enumerate(row.get("supporters") or []):
            if not isinstance(sup, dict) or not sup.get("participant_id"):
                errors.append(f"{iid} supporters[{j}] missing participant_id")
            stance = str((sup or {}).get("stance") or "")
            if stance and stance not in STANCE_VOCAB:
                errors.append(f"{iid} supporters[{j}] stance {stance!r}")
    return errors


def check_disappearance(doc: dict) -> dict:
    """FIRE if any canonical idea is absent from synthesis on either signal.

    SILENT only when both missing sets are empty. Duplicate rows are traced via
    duplicate_of and are not themselves required citations.
    """
    ledger = doc.get("ledger") or {}
    synthesis = doc.get("synthesis") or {}
    ideas = list(ledger.get("ideas") or [])
    nodes = list(synthesis.get("nodes") or [])
    schema_errors = validate_ledger(ideas)
    required = canonical_rows(ideas)
    missing_ids, required_ids, cited_ids = signal_a_missing_idea_ids(required, nodes)
    missing_mechs, required_mechs, covered = signal_b_missing_mechanisms(
        required, nodes
    )
    a_fires = len(missing_ids) > 0
    b_fires = len(missing_mechs) > 0
    fired = a_fires or b_fires
    return {
        "schema_errors": schema_errors,
        "n_ideas": len(ideas),
        "n_canonical": len(required),
        "n_duplicates": len(ideas) - len(required),
        "n_synthesis_nodes": len(nodes),
        "signal_a": {
            "field": "idea_id vs cites_idea_ids",
            "required": required_ids,
            "cited": cited_ids,
            "missing": missing_ids,
            "n_required": len(required_ids),
            "n_cited": len(cited_ids),
            "n_missing": len(missing_ids),
            "fires": a_fires,
        },
        "signal_b": {
            "field": "canonical_mechanism vs covers_mechanisms",
            "required": required_mechs,
            "covered": covered,
            "missing": missing_mechs,
            "n_required": len(required_mechs),
            "n_cited": len(covered),
            "n_missing": len(missing_mechs),
            "fires": b_fires,
        },
        "signals_disagree": a_fires != b_fires,
        "fired": fired,
        "silent": (not fired) and not schema_errors,
        "negative_control_reject_state": (
            "a synthesis that omits a canonical ledger idea_id or its "
            "canonical_mechanism; the check must FIRE, not stay silent"
        ),
    }


def drop_idea_from_synthesis(doc: dict, idea_id: str) -> dict:
    """Plant a disappearance: strip one idea_id and its mechanism from nodes."""
    import copy

    planted = copy.deepcopy(doc)
    ideas = list((planted.get("ledger") or {}).get("ideas") or [])
    mech = None
    for row in ideas:
        if row.get("idea_id") == idea_id:
            mech = row.get("canonical_mechanism")
            break
    nodes = list((planted.get("synthesis") or {}).get("nodes") or [])
    kept: list[dict] = []
    for node in nodes:
        cites = [x for x in _as_str_list(node.get("cites_idea_ids")) if x != idea_id]
        covers = [
            x for x in _as_str_list(node.get("covers_mechanisms")) if x != mech
        ]
        if not cites and not covers:
            continue
        node = dict(node)
        node["cites_idea_ids"] = cites
        node["covers_mechanisms"] = covers
        kept.append(node)
    planted.setdefault("synthesis", {})["nodes"] = kept
    planted["fixture_id"] = f"runtime-drop:{idea_id}"
    return planted
