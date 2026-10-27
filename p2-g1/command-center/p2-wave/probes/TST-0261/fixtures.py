"""TST-0261 probe fixtures: the three planted council evidence graphs.

Sizes match the receipt's recorded graph_size block exactly.
"""
from __future__ import annotations

THREE_NODE_CYCLE = {
    "nodes": ["claim-alpha", "claim-beta", "claim-gamma"],
    "support": [
        ["claim-alpha", "claim-beta"],
        ["claim-beta", "claim-gamma"],
        ["claim-gamma", "claim-alpha"],
    ],
    "contradiction": [],
}

DIAMOND = {
    "nodes": [
        "ev-root",
        "claim-a",
        "claim-b",
        "claim-c",
        "claim-d",
        "claim-e",
        "claim-f",
        "claim-g",
    ],
    "support": [
        ["ev-root", "claim-a"],
        ["ev-root", "claim-b"],
        ["claim-a", "claim-c"],
        ["claim-b", "claim-c"],
        ["claim-c", "claim-d"],
        ["ev-root", "claim-e"],
        ["claim-e", "claim-f"],
        ["claim-f", "claim-g"],
    ],
    "contradiction": [],
}

EMPTY_EVIDENCE = {
    "nodes": ["claim-x", "claim-y", "claim-z"],
    "support": [],
    "contradiction": [
        ["claim-x", "claim-y"],
        ["claim-y", "claim-x"],
    ],
}
