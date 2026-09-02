"""Labeled detector controls. Not mixed into program coverage."""
from __future__ import annotations

HOWEVER_ONLY = {
    "id": "RES-0187-CTRL-HOWEVER",
    "claim_id": "RES-0187-CTRL-HOWEVER",
    "canonical_mechanism": "The architecture is production-ready, however.",
    "text": "The architecture is production-ready, however.",
    "strongest_caveat": "however",
}

RECORDED_TRIPLE = {
    "id": "RES-0187-CTRL-RECORDED",
    "claim_id": "RES-0187-CTRL-RECORDED",
    "canonical_mechanism": (
        "Every major conclusion in this program has already been challenged."
    ),
    "counterevidence_search": {
        "query": (
            "\"Every major conclusion in this program has already been challenged\" "
            "disconfirming evidence OR contradicted OR false"
        ),
        "result_set": [
            {
                "rank": 1,
                "title": "no live CLAIM-REGISTRY counterevidence hunts on this worktree",
                "url": "file:///opt/p2/ast-integrate/command-center/CLAIM-REGISTRY.json",
                "note": "path absent; recorded as a result row so the hunt is not silent",
            }
        ],
        "verdict": "NO-COUNTEREVIDENCE-CORPUS-PRESENT",
        "ran_at": "2026-08-24T20:50:00Z",
    },
}

CAVEAT_ONLY = {
    "id": "RES-0187-CTRL-CAVEAT",
    "claim_id": "RES-0187-CTRL-CAVEAT",
    "canonical_mechanism": "Linear pooling is the unique zero-history operator.",
    "strongest_caveat": (
        "However, equal-weight log pooling is also defined at zero history."
    ),
}
