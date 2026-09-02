"""Overclaim check for ARC-0026 architecture-review claims.

Every REFUTED row must name DESIGN vs SENTENCE. Probe 2 drops defect_locus
on a REFUTED row and asserts this checker then fails. The two process
readings must remain separate; the estate 2037 figure must not be today's
number. The both-states codes must differ.
"""
from __future__ import annotations

from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})


def check_overclaim(doc: dict[str, Any]) -> tuple[bool, str]:
    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 3:
        return False, "claims-missing-or-short"
    refuted = 0
    confirmed = 0
    for i, row in enumerate(claims):
        if not isinstance(row, dict):
            return False, f"claims[{i}]-not-object"
        verdict = str(row.get("verdict") or "")
        if verdict not in VERDICTS:
            return False, f"claims[{i}]-bad-verdict:{verdict}"
        if verdict == "REFUTED":
            refuted += 1
            locus = str(row.get("defect_locus") or "")
            if locus not in LOCUS:
                return False, f"claims[{i}]-REFUTED-missing-defect_locus"
            if not str(row.get("claim") or "").strip():
                return False, f"claims[{i}]-empty-claim"
        elif verdict == "CONFIRMED":
            confirmed += 1
    if refuted < 1:
        return False, "no-REFUTED-claim"
    if confirmed < 1:
        return False, "no-CONFIRMED-claim"

    live = doc.get("live_process_multiplication") or {}
    try:
        ps = int(live["powershell_process_count"])
        cfg = int(live["mcp_config_per_session_count"])
    except (KeyError, TypeError, ValueError):
        return False, "two-probe-counts-not-separate"
    if "combined_process_count" in live:
        return False, "combined-count-forbidden"
    if live.get("cited_estate_figure_as_today") is True:
        return False, "cited-earlier-figure"
    if ps < 0 or cfg < 0:
        return False, "negative-count"

    bs = doc.get("both_states") or {}
    a = str(bs.get("not_selected_code") or "")
    b = str(bs.get("index_miss_installed_code") or "")
    if not a or not b:
        return False, "both-states-codes-missing"
    if a == b:
        return False, "signal-does-not-distinguish"
    if a != "NOT_SELECTED" or b != "INDEX_MISS_INSTALLED":
        return False, f"unexpected-codes:{a}/{b}"
    if bs.get("collapsed_same_in_both_states") is not True:
        return False, "collapsed-control-missing"

    ceil = doc.get("ceiling_test") or {}
    if ceil.get("kind") != "simulated":
        return False, "ceiling-not-simulated"
    if ceil.get("eager_superlinear") is True:
        return False, "eager-marked-superlinear-without-p1-record"
    if ceil.get("planted_superlinear") is not True:
        return False, "superlinear-detector-did-not-fire-on-plant"
    if ceil.get("p1_on_eager") is True:
        return False, "p1-claimed-on-linear-eager"

    design = REPO_A4_DESIGN_PRESENT(doc)
    if design:
        return False, "a4-design-must-not-be-rebuilt-here"

    return True, f"refuted={refuted} confirmed={confirmed} ps={ps} cfg={cfg} a={a} b={b}"


def REPO_A4_DESIGN_PRESENT(doc: dict[str, Any]) -> bool:
    return bool((doc.get("a4_design") or {}).get("present"))
