"""Honest live-input census. Absence is recorded; nothing is invented."""
from __future__ import annotations

import json
from pathlib import Path

import contract as C


def _present(repo: Path, rel: str) -> dict:
    path = repo / rel
    exists = path.is_file() and path.stat().st_size > 0
    return {
        "path": rel,
        "present": exists,
        "bytes": path.stat().st_size if exists else 0,
    }


def _canonical_mechanism_count(repo: Path) -> int:
    path = repo / C.CLAIM_REGISTRY_REL
    if not path.is_file() or path.stat().st_size <= 0:
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return 0
    claims = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(claims, list):
        return 0
    n = 0
    for row in claims:
        if isinstance(row, dict) and row.get("canonical_mechanism"):
            n += 1
    return n


def scan(repo: Path) -> dict:
    syn = _present(repo, C.SYN_0011_REL)
    claims = _present(repo, C.CLAIM_REGISTRY_REL)
    cc = _present(repo, C.CC_0020_REL)
    canon_n = _canonical_mechanism_count(repo)
    helper_hits = []
    tools = repo / "tools" / "command-center"
    if tools.is_dir():
        for p in sorted(tools.rglob("*")):
            if p.is_file() and "dedup" in p.name.lower():
                helper_hits.append(p.relative_to(repo).as_posix())
    return {
        "syn_0011": {
            **syn,
            "used_as_finding_source": False,
            "note": (
                "Merged SYN-0011 adjudication set is absent on this worktree. "
                "The detector is proven on the planted fixture corpus, not on "
                "a fabricated live finding list."
            ),
        },
        "claim_registry": {
            **claims,
            "canonical_mechanism_field_count": canon_n,
            "canonical_mechanism_used_as_collapse_rule": False,
            "note": (
                "CLAIM-REGISTRY.json is present but no claim carries "
                "canonical_mechanism. Fixture rows still label that key, and "
                "it is NOT the collapse rule (a full rewrite shares the key "
                "and must remain uncollapsed under the detectors)."
            ),
        },
        "cc_0020": {
            **cc,
            "helpers_found": helper_hits,
            "note": (
                "CC-0020 receipt and command-center dedup helpers are absent. "
                "SYN-0017 ships its own two-detector gate rather than importing "
                "a missing helper."
            ),
        },
        "finding_source": "fixture-corpus-with-planted-mutants",
    }
