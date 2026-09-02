"""Planted council graphs for TST-0261.

Node ids and edge order are part of the contract: the 3-node cycle must
print the exact closed path ``claim-alpha -> claim-beta -> claim-gamma -> claim-alpha``.
"""
from __future__ import annotations

CLAIM_ALPHA = "claim-alpha"
CLAIM_BETA = "claim-beta"
CLAIM_GAMMA = "claim-gamma"
THREE_CYCLE_PATH = [
    CLAIM_ALPHA,
    CLAIM_BETA,
    CLAIM_GAMMA,
    CLAIM_ALPHA,
]
THREE_CYCLE_PRINTED = "claim-alpha -> claim-beta -> claim-gamma -> claim-alpha"

EV_ROOT = "ev-root"
EV_LEFT = "ev-left"
EV_RIGHT = "ev-right"
MID_1 = "mid-1"
MID_2 = "mid-2"
MID_3 = "mid-3"
MID_4 = "mid-4"
CLAIM_TIP = "claim-tip"


def planted_three_node_cycle() -> dict:
    """Cites-loop of length 3. Detector must FIRE and print the exact path."""
    return {
        "nodes": [
            {"id": CLAIM_ALPHA, "kind": "claim"},
            {"id": CLAIM_BETA, "kind": "claim"},
            {"id": CLAIM_GAMMA, "kind": "claim"},
        ],
        "support_edges": [
            {"from": CLAIM_ALPHA, "to": CLAIM_BETA},
            {"from": CLAIM_BETA, "to": CLAIM_GAMMA},
            {"from": CLAIM_GAMMA, "to": CLAIM_ALPHA},
        ],
        "contradiction_edges": [],
    }


def planted_diamond_long_chain() -> dict:
    """Long support chains that share ancestor ev-root. A diamond, not a cycle."""
    return {
        "nodes": [
            {"id": CLAIM_TIP, "kind": "claim"},
            {"id": MID_1, "kind": "claim"},
            {"id": MID_2, "kind": "claim"},
            {"id": MID_3, "kind": "claim"},
            {"id": MID_4, "kind": "claim"},
            {"id": EV_LEFT, "kind": "evidence"},
            {"id": EV_RIGHT, "kind": "evidence"},
            {"id": EV_ROOT, "kind": "evidence"},
        ],
        "support_edges": [
            {"from": CLAIM_TIP, "to": MID_1},
            {"from": MID_1, "to": MID_2},
            {"from": MID_2, "to": EV_LEFT},
            {"from": EV_LEFT, "to": EV_ROOT},
            {"from": CLAIM_TIP, "to": MID_3},
            {"from": MID_3, "to": MID_4},
            {"from": MID_4, "to": EV_RIGHT},
            {"from": EV_RIGHT, "to": EV_ROOT},
        ],
        "contradiction_edges": [],
    }


def planted_empty_evidence() -> dict:
    """Council with claim nodes and a contradiction pair, but zero evidence edges."""
    return {
        "nodes": [
            {"id": CLAIM_ALPHA, "kind": "claim"},
            {"id": CLAIM_BETA, "kind": "claim"},
            {"id": CLAIM_GAMMA, "kind": "claim"},
        ],
        "support_edges": [],
        "contradiction_edges": [
            {"from": CLAIM_ALPHA, "to": CLAIM_BETA},
            {"from": CLAIM_BETA, "to": CLAIM_ALPHA},
        ],
    }


def planted_contradiction_only_cycle() -> dict:
    """Same as empty-evidence: contradiction 2-cycle must not count as citation."""
    return planted_empty_evidence()
