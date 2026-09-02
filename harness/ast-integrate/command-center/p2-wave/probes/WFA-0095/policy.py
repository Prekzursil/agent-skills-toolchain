"""WFA-0095 duplicate collapse policy.

Collapsing two records that a prior scan called duplicates is not a
simplification privilege. The merge must keep the union of four attribute
sets and write a duplicate-of edge so the absorbed row can be restored.

Preserved sets:
  mechanisms, provenance_anchors, licence_obligations, stop_rules

Licence: the stricter SPDX of the two sources governs the survivor.
A collapse that drops a unique mechanism, weakens the licence, drops a
stop rule, drops a provenance anchor, or omits the duplicate-of edge is
rejected. A policy that has never rejected is not a constraint.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

UNIT_ID = "WFA-0095"
SENTINEL = "SUCCESS:WFA-0095"

MECHANISMS = "mechanisms"
PROVENANCE = "provenance_anchors"
LICENCE_OBLIGATIONS = "licence_obligations"
STOP_RULES = "stop_rules"
PRESERVED_SETS = (MECHANISMS, PROVENANCE, LICENCE_OBLIGATIONS, STOP_RULES)

CAPABILITY_LOSS = "CAPABILITY_LOSS"
PROVENANCE_LOSS = "PROVENANCE_LOSS"
LICENCE_WEAKENED = "LICENCE_WEAKENED"
LICENCE_UNKNOWN = "LICENCE_UNKNOWN"
STOP_RULE_LOSS = "STOP_RULE_LOSS"
MISSING_DUPLICATE_OF = "MISSING_DUPLICATE_OF"
SURVIVOR_NOT_IN_PAIR = "SURVIVOR_NOT_IN_PAIR"

CLASS_CAPABILITY_LOSS = "capability-loss"
CLASS_DUPLICATE_COLLAPSE = "duplicate-collapse-error"
CLASS_LICENSE_BLOCKED = "license-blocked"

# Higher rank = stricter copyleft / heavier obligation. Join is max rank.
LICENCE_RANK: dict[str, int] = {
    "CC0-1.0": 0,
    "Unlicense": 0,
    "0BSD": 0,
    "MIT": 10,
    "BSD-2-Clause": 10,
    "BSD-3-Clause": 10,
    "ISC": 10,
    "Apache-2.0": 20,
    "MPL-2.0": 30,
    "LGPL-2.1-only": 40,
    "LGPL-3.0-only": 40,
    "GPL-2.0-only": 50,
    "GPL-3.0-only": 60,
    "AGPL-3.0-only": 70,
    "UNKNOWN": 100,
    "UNLICENSED": 100,
    "ALL-RIGHTS-RESERVED": 100,
}

NEGATIVE_CONTROL_VERBATIM = (
    "On fixture planted-lossy-mechanism (record wf-scan-beta unique mechanism "
    "'embedding-cosine-rewrite' dropped from the proposed survivor), "
    "union-preservation fails on mechanisms and evaluate_collapse returns "
    "accepted=False with codes=['CAPABILITY_LOSS']. The policy REJECTS the "
    "lossy collapse. On fixture union-preserving (same pair, merged = "
    "set-union of mechanisms, provenance_anchors, licence_obligations and "
    "stop_rules, governing SPDX=AGPL-3.0-only, duplicate-of edge written), "
    "evaluate_collapse returns accepted=True with codes=[]. The policy "
    "ACCEPTS the union-preserving collapse."
)

POLICY_TEXT = (
    "A collapse of two duplicate workflow records is admitted only when the "
    "survivor carries the set-union of both records' mechanisms, provenance "
    "anchors, licence obligations and stop rules; the stricter SPDX identifier "
    "governs the merged record; and the operation writes a duplicate-of edge "
    "from the absorbed id to the survivor that snapshots both preimages so "
    "the pair is reconstructible. A collapse that loses a capability is "
    "rejected rather than accepted as simplification. FAILURE CLASS "
    "'workflow fusion loses a source capability' (FC-11332) applies to a "
    "lossy collapse."
)


def _as_set(values: Any) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, (set, frozenset, list, tuple)):
        return {str(v) for v in values}
    return {str(values)}


def _sorted(values: Iterable[str]) -> list[str]:
    return sorted(_as_set(values))


def licence_rank(spdx: str | None) -> int | None:
    if not spdx or not str(spdx).strip():
        return None
    return LICENCE_RANK.get(str(spdx).strip())


def licence_join(left_spdx: str, right_spdx: str) -> tuple[str | None, str | None]:
    """Return (governing_spdx, error_code)."""
    ra = licence_rank(left_spdx)
    rb = licence_rank(right_spdx)
    if ra is None or rb is None:
        return None, LICENCE_UNKNOWN
    if ra > rb:
        return left_spdx, None
    if rb > ra:
        return right_spdx, None
    if left_spdx == right_spdx:
        return left_spdx, None
    return None, LICENCE_UNKNOWN


def union_sets(left: dict, right: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for field in PRESERVED_SETS:
        out[field] = _sorted(_as_set(left.get(field)) | _as_set(right.get(field)))
    return out


def missing_from_union(left: dict, right: dict, merged: dict) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    required = union_sets(left, right)
    for field in PRESERVED_SETS:
        lost = sorted(set(required[field]) - _as_set(merged.get(field)))
        if lost:
            missing[field] = lost
    return missing


def codes_for_missing(missing: dict[str, list[str]]) -> list[str]:
    codes: list[str] = []
    if missing.get(MECHANISMS):
        codes.append(CAPABILITY_LOSS)
    if missing.get(PROVENANCE):
        codes.append(PROVENANCE_LOSS)
    if missing.get(LICENCE_OBLIGATIONS):
        codes.append(LICENCE_WEAKENED)
    if missing.get(STOP_RULES):
        codes.append(STOP_RULE_LOSS)
    return codes


def classify(codes: list[str]) -> list[str]:
    classes: list[str] = []
    if CAPABILITY_LOSS in codes or STOP_RULE_LOSS in codes:
        classes.append(CLASS_CAPABILITY_LOSS)
    if (
        PROVENANCE_LOSS in codes
        or MISSING_DUPLICATE_OF in codes
        or SURVIVOR_NOT_IN_PAIR in codes
    ):
        classes.append(CLASS_DUPLICATE_COLLAPSE)
    if LICENCE_WEAKENED in codes or LICENCE_UNKNOWN in codes:
        classes.append(CLASS_LICENSE_BLOCKED)
    return classes


def make_duplicate_of_edge(
    left: dict,
    right: dict,
    survivor_id: str,
    merged: dict,
) -> dict:
    ids = {left["id"], right["id"]}
    if survivor_id not in ids:
        raise ValueError(f"survivor_id {survivor_id!r} not in pair {ids}")
    absorbed_id = left["id"] if survivor_id == right["id"] else right["id"]
    absorbed = left if absorbed_id == left["id"] else right
    survivor_pre = left if survivor_id == left["id"] else right
    return {
        "edge_type": "duplicate-of",
        "from": absorbed_id,
        "to": survivor_id,
        "absorbed_id": absorbed_id,
        "survivor_id": survivor_id,
        "absorbed_snapshot": deepcopy(absorbed),
        "survivor_pre_snapshot": deepcopy(survivor_pre),
        "merged_post": deepcopy(merged),
    }


def restore_from_edge(edge: dict) -> tuple[dict, dict]:
    """Return (survivor_preimage, absorbed_preimage)."""
    return deepcopy(edge["survivor_pre_snapshot"]), deepcopy(edge["absorbed_snapshot"])


def records_equal(a: dict, b: dict) -> bool:
    if a.get("id") != b.get("id"):
        return False
    if a.get("licence_spdx") != b.get("licence_spdx"):
        return False
    for field in PRESERVED_SETS:
        if _as_set(a.get(field)) != _as_set(b.get(field)):
            return False
    return True


def evaluate_collapse(
    left: dict,
    right: dict,
    merged: dict,
    survivor_id: str,
    edges: list[dict] | None = None,
    auto_write_edge: bool = True,
) -> dict:
    """Admit or reject a proposed collapse.

    Union preservation is a computed set difference, not a prose claim.
    """
    codes: list[str] = []
    pair_ids = {left.get("id"), right.get("id")}
    if survivor_id not in pair_ids:
        codes.append(SURVIVOR_NOT_IN_PAIR)

    required = union_sets(left, right)
    missing = missing_from_union(left, right, merged)
    codes.extend(codes_for_missing(missing))

    governing, lic_err = licence_join(
        str(left.get("licence_spdx") or ""),
        str(right.get("licence_spdx") or ""),
    )
    if lic_err:
        codes.append(lic_err)
        if LICENCE_WEAKENED not in codes:
            codes.append(LICENCE_WEAKENED)
    elif merged.get("licence_spdx") != governing:
        if LICENCE_WEAKENED not in codes:
            codes.append(LICENCE_WEAKENED)

    written_edges: list[dict] = []
    if edges is not None:
        written_edges = [deepcopy(e) for e in edges]
    elif auto_write_edge and not codes:
        written_edges = [make_duplicate_of_edge(left, right, survivor_id, merged)]

    has_dup = any(
        e.get("edge_type") == "duplicate-of"
        and {e.get("from"), e.get("to")} == pair_ids
        for e in written_edges
    )
    if not codes and not has_dup:
        codes.append(MISSING_DUPLICATE_OF)
        written_edges = []

    accepted = len(codes) == 0
    return {
        "accepted": accepted,
        "codes": codes,
        "classes": classify(codes),
        "survivor_id": survivor_id,
        "left_id": left.get("id"),
        "right_id": right.get("id"),
        "required_union": required,
        "missing": missing,
        "governing_licence": governing,
        "merged_licence": merged.get("licence_spdx"),
        "edges": written_edges if accepted else [],
        "policy_constrained": True,
    }


def always_accept_mutant(
    left: dict,
    right: dict,
    merged: dict,
    survivor_id: str,
) -> dict:
    """Non-constraining mutant: admit every collapse. Must fail planted loss."""
    edge = make_duplicate_of_edge(left, right, survivor_id, merged)
    return {
        "accepted": True,
        "codes": [],
        "classes": [],
        "survivor_id": survivor_id,
        "left_id": left.get("id"),
        "right_id": right.get("id"),
        "required_union": union_sets(left, right),
        "missing": missing_from_union(left, right, merged),
        "governing_licence": licence_join(
            str(left.get("licence_spdx") or ""),
            str(right.get("licence_spdx") or ""),
        )[0],
        "merged_licence": merged.get("licence_spdx"),
        "edges": [edge],
        "policy_constrained": False,
    }


def record(
    rid: str,
    mechanisms: Iterable[str],
    provenance: Iterable[str],
    licence_spdx: str,
    obligations: Iterable[str],
    stop_rules: Iterable[str],
) -> dict:
    return {
        "id": rid,
        "mechanisms": _sorted(mechanisms),
        "provenance_anchors": _sorted(provenance),
        "licence_spdx": licence_spdx,
        "licence_obligations": _sorted(obligations),
        "stop_rules": _sorted(stop_rules),
    }


def pair_alpha_beta() -> tuple[dict, dict]:
    alpha = record(
        "wf-scan-alpha",
        mechanisms=(
            "token-jaccard",
            "rename-detect",
            "planted-lossy-unique-alpha",
        ),
        provenance=(
            "registry:08#wf-scan-alpha",
            "harness:_USER-PROMPTS.md:11332",
        ),
        licence_spdx="MIT",
        obligations=("ATTRIBUTION", "NOTICE-PRESERVE"),
        stop_rules=("halt-on-unknown-licence", "halt-on-capability-loss"),
    )
    beta = record(
        "wf-scan-beta",
        mechanisms=(
            "token-jaccard",
            "rename-detect",
            "embedding-cosine-rewrite",
        ),
        provenance=(
            "registry:08#wf-scan-beta",
            "blueprint:09#BP-beta",
        ),
        licence_spdx="AGPL-3.0-only",
        obligations=("ATTRIBUTION", "COPYLEFT-SOURCE", "NETWORK-COPYLEFT"),
        stop_rules=("halt-on-network-copyleft-undisclosed",),
    )
    return alpha, beta


def union_merged(left: dict, right: dict, survivor_id: str) -> dict:
    u = union_sets(left, right)
    governing, err = licence_join(left["licence_spdx"], right["licence_spdx"])
    if err or governing is None:
        raise ValueError(f"cannot form union merged: {err}")
    return {
        "id": survivor_id,
        "mechanisms": u[MECHANISMS],
        "provenance_anchors": u[PROVENANCE],
        "licence_spdx": governing,
        "licence_obligations": u[LICENCE_OBLIGATIONS],
        "stop_rules": u[STOP_RULES],
    }


def planted_lossy_merged(left: dict, right: dict, survivor_id: str) -> dict:
    """Drop beta's unique mechanism — the named fusion-loses-capability plant."""
    merged = union_merged(left, right, survivor_id)
    merged["mechanisms"] = [
        m for m in merged["mechanisms"] if m != "embedding-cosine-rewrite"
    ]
    return merged


def planted_licence_weakened(left: dict, right: dict, survivor_id: str) -> dict:
    merged = union_merged(left, right, survivor_id)
    merged["licence_spdx"] = "MIT"
    merged["licence_obligations"] = [
        o for o in merged["licence_obligations"] if o != "NETWORK-COPYLEFT"
    ]
    return merged


def planted_stop_rule_loss(left: dict, right: dict, survivor_id: str) -> dict:
    merged = union_merged(left, right, survivor_id)
    merged["stop_rules"] = [
        s
        for s in merged["stop_rules"]
        if s != "halt-on-network-copyleft-undisclosed"
    ]
    return merged


def planted_provenance_loss(left: dict, right: dict, survivor_id: str) -> dict:
    merged = union_merged(left, right, survivor_id)
    merged["provenance_anchors"] = [
        p for p in merged["provenance_anchors"] if p != "blueprint:09#BP-beta"
    ]
    return merged


def fixtures() -> dict[str, dict]:
    left, right = pair_alpha_beta()
    survivor = left["id"]
    preserving = union_merged(left, right, survivor)
    return {
        "union-preserving": {
            "id": "union-preserving",
            "left": left,
            "right": right,
            "survivor_id": survivor,
            "merged": preserving,
            "expect_accepted": True,
            "expect_codes": [],
        },
        "planted-lossy-mechanism": {
            "id": "planted-lossy-mechanism",
            "left": left,
            "right": right,
            "survivor_id": survivor,
            "merged": planted_lossy_merged(left, right, survivor),
            "expect_accepted": False,
            "expect_codes": [CAPABILITY_LOSS],
        },
        "planted-licence-weakened": {
            "id": "planted-licence-weakened",
            "left": left,
            "right": right,
            "survivor_id": survivor,
            "merged": planted_licence_weakened(left, right, survivor),
            "expect_accepted": False,
            "expect_codes": [LICENCE_WEAKENED],
        },
        "planted-stop-rule-loss": {
            "id": "planted-stop-rule-loss",
            "left": left,
            "right": right,
            "survivor_id": survivor,
            "merged": planted_stop_rule_loss(left, right, survivor),
            "expect_accepted": False,
            "expect_codes": [STOP_RULE_LOSS],
        },
        "planted-provenance-loss": {
            "id": "planted-provenance-loss",
            "left": left,
            "right": right,
            "survivor_id": survivor,
            "merged": planted_provenance_loss(left, right, survivor),
            "expect_accepted": False,
            "expect_codes": [PROVENANCE_LOSS],
        },
        "union-preserving-no-edge": {
            "id": "union-preserving-no-edge",
            "left": left,
            "right": right,
            "survivor_id": survivor,
            "merged": preserving,
            "auto_write_edge": False,
            "edges": [],
            "expect_accepted": False,
            "expect_codes": [MISSING_DUPLICATE_OF],
        },
    }


def run_fixture(fx: dict) -> dict:
    result = evaluate_collapse(
        fx["left"],
        fx["right"],
        fx["merged"],
        fx["survivor_id"],
        edges=fx.get("edges"),
        auto_write_edge=fx.get("auto_write_edge", True),
    )
    result["fixture_id"] = fx["id"]
    result["expect_accepted"] = fx["expect_accepted"]
    result["expect_codes"] = list(fx["expect_codes"])
    result["matched_expectation"] = (
        result["accepted"] is fx["expect_accepted"]
        and result["codes"] == list(fx["expect_codes"])
    )
    if result["accepted"] and result["edges"]:
        survivor_pre, absorbed = restore_from_edge(result["edges"][0])
        original_survivor = (
            fx["left"] if fx["survivor_id"] == fx["left"]["id"] else fx["right"]
        )
        original_absorbed = (
            fx["right"] if fx["survivor_id"] == fx["left"]["id"] else fx["left"]
        )
        result["restore_ok"] = records_equal(
            survivor_pre, original_survivor
        ) and records_equal(absorbed, original_absorbed)
    else:
        result["restore_ok"] = None
    return result


def run_all() -> dict[str, dict]:
    return {fid: run_fixture(fx) for fid, fx in fixtures().items()}


def compact_eval(result: dict) -> dict:
    edge_summaries = []
    for edge in result.get("edges") or []:
        edge_summaries.append(
            {
                "edge_type": edge.get("edge_type"),
                "from": edge.get("from"),
                "to": edge.get("to"),
                "absorbed_id": edge.get("absorbed_id"),
                "survivor_id": edge.get("survivor_id"),
            }
        )
    return {
        "fixture_id": result["fixture_id"],
        "accepted": result["accepted"],
        "codes": list(result["codes"]),
        "classes": list(result["classes"]),
        "required_union": result["required_union"],
        "missing": result["missing"],
        "governing_licence": result["governing_licence"],
        "merged_licence": result["merged_licence"],
        "edges": edge_summaries,
        "restore_ok": result.get("restore_ok"),
        "matched_expectation": result["matched_expectation"],
        "expect_accepted": result["expect_accepted"],
        "expect_codes": result["expect_codes"],
        "policy_constrained": result.get("policy_constrained"),
    }
