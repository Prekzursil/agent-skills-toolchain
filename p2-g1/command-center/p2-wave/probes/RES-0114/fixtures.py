"""Fixtures for RES-0114 named probes (both-states + planted silent-download)."""
from __future__ import annotations

import contract as C

# Planted analogue of the estate motivating case: comment lies, fetch happens.
LYING_GETPIP = {
    "id": "planted-silent-get-pip",
    "comment": C.LYING_COMMENT,
    "claims_offline": True,
    "attempted_destinations": [
        {
            "host": "bootstrap.pypa.io",
            "port": 443,
            "path": "/get-pip.py",
            "via": "urllib",
        }
    ],
    "expect": "silent-download",
}

GENUINELY_HERMETIC = {
    "id": "genuinely-hermetic-hash-local",
    "comment": C.LYING_COMMENT,
    "claims_offline": True,
    "attempted_destinations": [],
    "expect": "hermetic",
}

DECLARED_WEB = {
    "id": "declared-websearch",
    "comment": "this step uses WebSearch by design; destinations are declared",
    "claims_offline": False,
    "attempted_destinations": [
        {"host": "api.search.example", "port": 443, "via": "WebSearch"}
    ],
    "expect": "declared-network-dependency",
}

CLASSIFY_FIXTURES = (LYING_GETPIP, GENUINELY_HERMETIC, DECLARED_WEB)

# Profile both-states for the impossible property.
PROFILE_LIVE_AGENT = {
    "id": "live-model-and-web",
    "live_model": True,
    "live_web": True,
    "note": "catalog question: inputs include a live model and a live web",
}
PROFILE_CLOSED_BUILD = {
    "id": "closed-software-build",
    "live_model": False,
    "live_web": False,
    "note": "Lamb Definition 1 closed input set; not an agent run",
}

# Headline number with no baseline: E3, cannot promote.
E3_NO_BASELINE = {
    "id": "M-PLANTED-NO-BASELINE",
    "title": "Hermetic builds make every agent run 100% bit-identical",
    "evidence_tier": "E3",
    "arxiv_or_doi": "none",
    "locator": "planted-overclaim",
    "effect_size": "100% of agent runs bit-identical",
    "baseline": None,
    "promoted": False,
    "hold_out_reason": "headline-without-baseline-E3",
}

# Overclaim the refuter kills: Definition 1 over live model+web.
OVERCLAIM_BIT_IDENTITY = {
    "id": "M-FULL-AGENT-BIT-IDENTITY",
    "title": "An agent run with a live model and live web satisfies Lamb Definition 1",
    "evidence_tier": "E4",
    "arxiv_or_doi": "2104.06020",
    "locator": "inferred transfer of Definition 1 onto live APIs",
    "effect_size": None,
    "baseline": None,
    "promoted": False,
    "hold_out_reason": "E4-inferred-cannot-promote",
}
