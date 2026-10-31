"""Scratch-environment both-states scenario for ARC-0048."""
from __future__ import annotations

from typing import Any

import choke as C
import classify as K
import surfaces as S

OWNER_KEY = b"arc0048-scratch-owner-key"


def marker_results(owner_key: bytes = OWNER_KEY) -> dict[str, Any]:
    surfaces = S.all_inject()
    intact: dict[str, Any] = {}
    mutant: dict[str, Any] = {}
    for name, art in surfaces.items():
        good = C.run_turn([art], owner_key=owner_key)
        bad = C.run_turn([art], owner_key=owner_key, skip_taint=True)
        intact[name] = {
            "proposed": good.proposed is not None,
            "principal": good.principal,
            "reached": good.marker_reached_tool_call,
        }
        mutant[name] = {
            "proposed": bad.proposed is not None,
            "principal": bad.principal,
            "reached": bad.marker_reached_tool_call,
        }
    mention = C.run_turn([S.skill(False)], owner_key=owner_key)
    return {
        "intact": intact,
        "mutant_skip_taint": mutant,
        "mention": {
            "proposed": mention.proposed is not None,
            "reached": mention.marker_reached_tool_call,
        },
        "intact_any_reached": any(v["reached"] for v in intact.values()),
        "mutant_any_reached": any(v["reached"] for v in mutant.values()),
        "intact_all_proposed": all(v["proposed"] for v in intact.values()),
        "mention_silent": mention.proposed is None,
    }


def run_scenario(owner_key: bytes = OWNER_KEY) -> dict[str, Any]:
    S.write_fixtures()
    markers = marker_results(owner_key)
    paths = K.classify_paths(owner_key)
    ok_disc, why_disc = K.discipline(paths)
    both_ok = (
        markers["intact_all_proposed"]
        and not markers["intact_any_reached"]
        and markers["mutant_any_reached"]
        and markers["mention_silent"]
        and ok_disc
    )
    return {
        "pass": both_ok,
        "discipline_ok": ok_disc,
        "discipline_why": why_disc,
        "markers": markers,
        "paths": paths,
        "path_count": len(paths),
        "structurally_impossible": sum(
            1 for p in paths if p["classification"] == K.SI
        ),
        "policy_forbidden": sum(1 for p in paths if p["classification"] == K.PF),
        "owner_key_source": "probe-local scratch bytes (not an estate API key)",
        "design_json_present": False,
        "adv_rebuild_circle": False,
    }
