#!/usr/bin/env python3
"""The seeded failure-class vocabulary (dependency fixture).

Materialized 2026-10-24 by the p2-g1 shard-1 builder: ARC-0020's emit cites
this file for the marketplace attack-class seed; the original
probes/ARC-0005/seeded_classes.py was absent on this worktree. Classes are
the security-relevant slice of the program's 47 seeded failure classes.
"""
from __future__ import annotations

SEEDED_CLASSES = [
    {
        "id": "SEED-MARKETPLACE-PERMISSIONS",
        "text": "marketplace package has malicious or excessive permissions",
        "family": "supply-chain",
    },
    {
        "id": "SEED-TYPOSQUAT-ID",
        "text": "typosquatted package id redirects install to an impostor",
        "family": "supply-chain",
    },
    {
        "id": "SEED-SIGNATURE-STRIP",
        "text": "unsigned or signature-stripped artifact passes metadata validation",
        "family": "supply-chain",
    },
    {
        "id": "SEED-DEP-CONFUSION",
        "text": "dependency confusion between a private mirror and a public registry",
        "family": "supply-chain",
    },
    {
        "id": "SEED-UNREACHABLE-REVOCATION",
        "text": "a revocation that never reaches an already-installed client",
        "family": "supply-chain",
    },
]


if __name__ == "__main__":
    import json

    print(json.dumps(SEEDED_CLASSES, indent=2, sort_keys=True))
