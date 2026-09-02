"""Both-states detectors. A probe that fires in both states is not shipped."""
from __future__ import annotations

from catalog import CONTROL_COMPONENT
from measure import EPS

SYNTHETIC_BROKEN_DELTA = 0.40


def control_is_approx_zero(delta: float) -> bool:
    return abs(delta) <= EPS


def component_moves(delta: float) -> bool:
    return abs(delta) > EPS


def always_true(_delta: float) -> bool:
    return True


def both_states(exp: dict) -> dict:
    table = {r["component"]: r for r in exp["ablation_delta_table"]}
    ctrl_delta = table[CONTROL_COMPONENT]["delta_from_baseline"]
    content_deltas = {
        r["component"]: r["delta_from_baseline"]
        for r in exp["ablation_delta_table"]
        if r["component"] not in {"full", CONTROL_COMPONENT}
    }
    max_content = max(content_deltas.values(), key=lambda d: abs(d))

    d_ctrl = {
        "id": "D-CONTROL-ZERO",
        "predicate": "abs(delta) <= eps",
        "known_good_fixture": {
            "kind": "live-irrelevant_meta-ablation",
            "delta": ctrl_delta,
            "fired": control_is_approx_zero(ctrl_delta),
            "output": f"control_zero={control_is_approx_zero(ctrl_delta)} delta={ctrl_delta}",
        },
        "known_broken_fixture": {
            "kind": "synthetic-nonzero-labelled-as-control",
            "delta": SYNTHETIC_BROKEN_DELTA,
            "fired": control_is_approx_zero(SYNTHETIC_BROKEN_DELTA),
            "output": (
                f"control_zero={control_is_approx_zero(SYNTHETIC_BROKEN_DELTA)} "
                f"delta={SYNTHETIC_BROKEN_DELTA}"
            ),
        },
    }
    d_ctrl["silent_in_both_states"] = (
        d_ctrl["known_good_fixture"]["fired"]
        and d_ctrl["known_broken_fixture"]["fired"]
    )
    d_ctrl["shipped"] = (
        d_ctrl["known_good_fixture"]["fired"]
        and not d_ctrl["known_broken_fixture"]["fired"]
        and not d_ctrl["silent_in_both_states"]
    )

    d_move = {
        "id": "D-CONTENT-MOVES",
        "predicate": "abs(delta) > eps for some content component",
        "known_good_fixture": {
            "kind": "live-max-content-ablation",
            "delta": max_content,
            "fired": component_moves(max_content),
            "output": f"moves={component_moves(max_content)} delta={max_content}",
        },
        "known_broken_fixture": {
            "kind": "identical-catalog-pair",
            "delta": 0.0,
            "fired": component_moves(0.0),
            "output": f"moves={component_moves(0.0)} delta=0.0",
        },
    }
    d_move["silent_in_both_states"] = (
        d_move["known_good_fixture"]["fired"]
        and d_move["known_broken_fixture"]["fired"]
    )
    d_move["shipped"] = (
        d_move["known_good_fixture"]["fired"]
        and not d_move["known_broken_fixture"]["fired"]
        and not d_move["silent_in_both_states"]
    )

    rejected = {
        "id": "D-ALWAYS-TRUE",
        "predicate": "always true",
        "known_good_fixture": {
            "kind": "any",
            "fired": always_true(max_content),
            "output": "fired=True",
        },
        "known_broken_fixture": {
            "kind": "any",
            "fired": always_true(0.0),
            "output": "fired=True",
        },
        "silent_in_both_states": True,
        "shipped": False,
        "why_rejected": "fires on known-good AND known-broken; measures nothing",
    }

    shipped = [d for d in (d_ctrl, d_move) if d["shipped"]]
    return {
        "eps": EPS,
        "content_deltas": content_deltas,
        "detectors": [d_ctrl, d_move, rejected],
        "shipped_ids": [d["id"] for d in shipped],
        "control_detector_shipped": d_ctrl["shipped"],
        "rejected_silent_probe": rejected["id"],
    }
