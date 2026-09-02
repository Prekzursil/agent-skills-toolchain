#!/usr/bin/env python3
"""Fixture idea ledger for CNF-0087.

Live council ledger (tools/council/protocol/brainstorm.py) and
tools/council/quota/unique_ideas.py are absent on this worktree. The
confirmation still has to recount a 100-claim substrate and plant three
trivial variants. This fixture is that substrate: 97 mechanistically
distinct ideas plus one seed and three wording variants of that seed,
which a string-identity counter treats as 100 unique.
"""
from __future__ import annotations

import json
from pathlib import Path

from measures import council_normalize, mechanism_key

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

SEED_ID = "I-001"
SEED_TEXT = (
    "Record each brainstorm idea with author round and a canonical mechanism field."
)
# Three trivial wording variants of SEED_TEXT. Distinct as strings;
# same canonical mechanism key after stopword/stem clustering.
PLANTED = [
    (
        "I-098",
        "Each brainstorm idea is recorded with author, round, and a canonical mechanism field.",
    ),
    (
        "I-099",
        "Record every brainstorm idea with author round plus a canonical mechanism field.",
    ),
    (
        "I-100",
        "Brainstorm ideas get recorded with author, round and a canonical-mechanism field.",
    ),
]

# Distinct named controls. Template tokens are shared; the slug supplies
# the uniqueness of the mechanism key so they do not collide with the seed.
_SLUGS = [
    "sha256-citation-pin",
    "submission-barrier-hide",
    "vote-proposition-hash",
    "dissent-ledger-keep",
    "stopping-floor-bind",
    "dual-signal-collapse",
    "unknown-list-row",
    "completeness-empty-reject",
    "instruction-shaped-isolate",
    "seeded-replay-diverge",
    "minority-report-surface",
    "calibration-band-attach",
    "evidence-url-resolve",
    "freshness-stamp-require",
    "contradiction-edge-draw",
    "support-edge-draw",
    "claim-id-stable",
    "settling-probe-name",
    "confidence-vocabulary-lock",
    "participant-sybil-detect",
    "collusion-pair-flag",
    "chair-capture-watch",
    "strategic-abstention-log",
    "vote-trade-forbid",
    "citation-cycle-break",
    "expertise-hallucination-mark",
    "conflict-interest-declare",
    "prompt-injection-neutralize",
    "peer-content-untrust",
    "tool-result-untrust",
    "display-name-untrust",
    "transcript-untrust",
    "bundle-untrust",
    "min-rounds-precondition",
    "min-evidence-precondition",
    "role-spoken-precondition",
    "opening-position-precondition",
    "proof-impossibility-reach",
    "and-or-partial-evidence",
    "truth-table-full-row",
    "changed-seed-control",
    "replay-stage-localize",
    "dry-run-extra-write",
    "estimate-accounting-source",
    "scout-source-class-plant",
    "workflow-invalid-six",
    "cache-stale-mutation",
    "predicate-always-true-stub",
    "checkpoint-corrupt-refuse",
    "kill-point-resume",
    "blueprint-load-no-artifact",
    "filesystem-not-catalog-enum",
    "rename-jaccard-blind",
    "full-rewrite-embed-fire",
    "option-card-body-dedup",
    "work-unit-mutant-gate",
    "floor-near-duplicate-silent",
    "padding-rename-reject",
    "claim-rank-not-repetition",
    "duplicate-of-edge-rederive",
    "mechanism-vocab-collapse",
    "bipartite-zero-blueprint",
    "mutual-exclusion-pair",
    "terminal-only-mechanism",
    "graph-not-isomorphic",
    "substitution-edge-express",
    "provenance-hop-gate",
    "licence-class-hop",
    "crash-stack-fingerprint",
    "fuzz-minimise-input",
    "restatement-blog-collapse",
    "yield-not-restate",
    "both-states-detector",
    "known-broken-fixture-fire",
    "known-good-fixture-silent",
    "second-vendor-reproduce",
    "split-verdict-escalate",
    "never-majority-vote-split",
    "raw-source-adjudicate",
    "blob-worktree-agree",
    "forged-completion-reject",
    "dark-checker-fail-closed",
    "vacuous-contract-fallback",
    "schema-document-merit",
    "garbage-probe-reject",
    "crlf-normalize-hash",
    "manifest-sha-match",
    "named-probe-rerun",
    "self-declared-blocked-undelivered",
    "cloud-ok-not-delivery",
    "unit-manifest-per-unit",
    "no-global-manifest-write",
    "two-strike-park",
    "adv-rebuild-forbid",
    "predicate-absent-implement",
    "live-named-probes-exit-zero",
]


def _distinct_text(slug: str) -> str:
    words = slug.replace("-", " ")
    return (
        f"Install a {words} control that the council ledger stores as its own row."
    )


def build_ledger() -> dict:
    ideas: list[dict] = [
        {
            "id": SEED_ID,
            "text": SEED_TEXT,
            "author": "P-seed",
            "round": 1,
            "planted": False,
            "plant_of": None,
        }
    ]
    for i, slug in enumerate(_SLUGS, start=2):
        ideas.append(
            {
                "id": f"I-{i:03d}",
                "text": _distinct_text(slug),
                "author": f"P-{(i % 7) + 1}",
                "round": 1 + (i % 4),
                "planted": False,
                "plant_of": None,
            }
        )
    for vid, text in PLANTED:
        ideas.append(
            {
                "id": vid,
                "text": text,
                "author": "P-plant",
                "round": 2,
                "planted": True,
                "plant_of": SEED_ID,
            }
        )
    if len(ideas) != 100:
        raise SystemExit(f"ledger size {len(ideas)} want=100")
    seed_key = mechanism_key(SEED_TEXT)
    for _, text in PLANTED:
        if mechanism_key(text) != seed_key:
            raise SystemExit(
                f"planted variant key mismatch: {mechanism_key(text)!r} vs {seed_key!r}"
            )
        if council_normalize(text) == council_normalize(SEED_TEXT):
            raise SystemExit("planted variant collapsed under council measure")
    seen: dict[str, str] = {}
    for idea in ideas:
        if idea["planted"]:
            continue
        k = mechanism_key(idea["text"])
        if k in seen:
            raise SystemExit(f"key collision {seen[k]} vs {idea['id']}: {k}")
        seen[k] = idea["id"]
    return {
        "id": "CNF-0087-fixture-ledger",
        "source": (
            "fixture: live tools/council/protocol/brainstorm.py idea ledger absent; "
            "live tools/council/quota/unique_ideas.py absent"
        ),
        "claimed_unique_under_council_measure": 100,
        "target": 100,
        "seed_id": SEED_ID,
        "planted_variant_ids": [p[0] for p in PLANTED],
        "ideas": ideas,
    }


def write_ledger(path: Path | None = None) -> dict:
    ledger = build_ledger()
    dest = path or (FIXTURES / "idea-ledger.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    return ledger


if __name__ == "__main__":
    doc = write_ledger()
    print(
        f"ideas={len(doc['ideas'])} seed={doc['seed_id']} plants={doc['planted_variant_ids']}"
    )
