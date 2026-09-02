#!/usr/bin/env python3
"""Both-states negative controls and planted mechanism mutants for RES-0151."""
from __future__ import annotations

import hashlib
from typing import Any

from mechanism import jaccard, mechanism_key

# 30 near-identical sources: string-distinct paraphrases of ONE mechanism.
# A string-equality stopper would treat these as 30 new claims and stay silent.
NEAR_IDENTICAL_TEXTS: tuple[str, ...] = (
    "The parser rejects unknown fields.",
    "The parser refuses unknown fields.",
    "Unknown fields are rejected by the parser.",
    "Unknown fields are refused by the parser.",
    "A parser rejects unknown fields.",
    "A parser refuses unknown fields.",
    "Parser rejects unknown fields.",
    "Parser refuses unknown fields.",
    "The parser will reject unknown fields.",
    "The parser will refuse unknown fields.",
    "Unknown fields get rejected by the parser.",
    "Unknown fields get refused by the parser.",
    "Parser will reject unknown fields.",
    "Parser will refuse unknown fields.",
    "The parser does reject unknown fields.",
    "The parser does refuse unknown fields.",
    "Unknown fields make the parser reject.",
    "Unknown fields make the parser refuse.",
    "The parser errors on unknown fields.",
    "The parser fails on unknown fields.",
    "Unknown fields are denied by the parser.",
    "Unknown fields get denied by the parser.",
    "The parser raises on unknown fields.",
    "Parser raises on unknown fields.",
    "A parser will reject unknown fields.",
    "A parser will refuse unknown fields.",
    "Unknown fields get rejected at the parser.",
    "Unknown fields get refused at the parser.",
    "The parser rejected unknown fields.",
    "The parser refused unknown fields.",
)

# 30 genuinely different mechanisms (disjoint primary objects).
DIVERSE_TEXTS: tuple[str, ...] = (
    "Rollback invalidates the package cache so the restored version is served.",
    "Warm clients and cold clients agree on the restored resolution.",
    "Duplicate JSON keys error rather than last-wins overwrite.",
    "Case-distinct keys collide under a case-insensitive client.",
    "Coverage percentages can hide a line-set trade.",
    "A confirmation whose verifier fingerprint equals its source fingerprint is rejected.",
    "Same-probe re-runs of CONFIRMED verdicts are not independent evidence.",
    "An owner packet carries exactly one foundation-level question.",
    "Answers recorded in OWNER-DECISIONS are never re-asked.",
    "A one-key schema document fallback accepts garbage as delivered.",
    "A non-json suffix skips the delivery gate entirely.",
    "A vacuous declared contract cannot fail yet still reports delivered.",
    "Existence-only ready_units counts BLOCKED artifacts as done.",
    "A dark contract checker still prints SUCCESS on the partition run.",
    "quality.yml historically never invoked ready_units.",
    "unitgate git cat-file blobs must agree with the worktree copy.",
    "Marketplace signing and SBOM machinery is dead weight for a single owner.",
    "A 200 response with the quote missing is a failed citation.",
    "A dead host falls back to the archival capture, not a live pass.",
    "Fetched untrusted HTML bytes are data, never instructions.",
    "Kappa thresholds are preregistered before any agreement is computed.",
    "Collapse retains every duplicate-of edge and the losing provenance.",
    "Rank uses independent evidence and must ignore repetition count.",
    "A planted live-only skill must be found without auto-deploy.",
    "A planted repo-only skill must appear in the reconcile diff.",
    "Adversarial padding must not push completeness_score to the 0.90 gate.",
    "The timeout arm of a stopping OR must be logged apart from saturation.",
    "Circular citation rings are a distinct defect from missing quotes.",
    "Plugin manifests with unknown fields must be rejected, not ignored.",
    "Worktree-isolated execution must not mutate the live skill tree.",
)

# Planted mutants for the dedup both-states control.
PARAPHRASE_PAIRS: tuple[tuple[str, str], ...] = (
    (
        "The parser rejects unknown fields.",
        "Unknown fields are refused by the parser.",
    ),
    (
        "Existence-only ready_units counts blocked artifacts as done.",
        "Blocked artifacts are counted as done by existence-only ready_units.",
    ),
)
TRUE_DISTINCTIONS: tuple[tuple[str, str], ...] = (
    (
        "The parser rejects unknown fields.",
        "The parser rejects duplicate keys.",
    ),
    (
        "A planted live-only skill must be found without auto-deploy.",
        "A planted repo-only skill must appear in the reconcile diff.",
    ),
)


def _as_sources(texts: tuple[str, ...], prefix: str) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for i, text in enumerate(texts, 1):
        digest = hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()
        sources.append(
            {
                "source_id": f"{prefix}-{i:02d}",
                "index": i,
                "heading": f"{prefix} source {i}",
                "resolved_url": f"file://command-center/p2-wave/probes/RES-0151/controls.py#{prefix}-{i:02d}",
                "fetch_timestamp": "2026-08-24T18:45:00Z",
                "sha256": digest,
                "sherman_kent_band": "almost-certain",
                "claims": [{"text": text, "kind": "planted-control"}],
            }
        )
    return sources


def near_identical_sources() -> list[dict[str, Any]]:
    if len(NEAR_IDENTICAL_TEXTS) != 30:
        raise RuntimeError("near-identical control is not 30 sources")
    srcs = _as_sources(NEAR_IDENTICAL_TEXTS, "near-identical")
    keys = {mechanism_key(t) for t in NEAR_IDENTICAL_TEXTS}
    if len(keys) > 3:
        raise RuntimeError(f"near-identical extractor split too far: {sorted(keys)}")
    return srcs


def diverse_sources() -> list[dict[str, Any]]:
    if len(DIVERSE_TEXTS) != 30:
        raise RuntimeError("diverse control is not 30 sources")
    keys = [mechanism_key(t) for t in DIVERSE_TEXTS]
    if len(set(keys)) < 24:
        raise RuntimeError(
            f"diverse extractor collapsed too far: {len(set(keys))} unique of 30"
        )
    return _as_sources(DIVERSE_TEXTS, "diverse")


def mutant_report() -> dict[str, Any]:
    para = []
    for a, b in PARAPHRASE_PAIRS:
        ka, kb = mechanism_key(a), mechanism_key(b)
        para.append(
            {
                "a": a,
                "b": b,
                "key_a": ka,
                "key_b": kb,
                "collapsed": ka == kb,
                "jaccard": round(jaccard(a, b), 4),
            }
        )
    dist = []
    for a, b in TRUE_DISTINCTIONS:
        ka, kb = mechanism_key(a), mechanism_key(b)
        dist.append(
            {
                "a": a,
                "b": b,
                "key_a": ka,
                "key_b": kb,
                "kept_apart": ka != kb,
                "jaccard": round(jaccard(a, b), 4),
            }
        )
    ok = all(p["collapsed"] for p in para) and all(d["kept_apart"] for d in dist)
    return {"paraphrases": para, "true_distinctions": dist, "pass": ok}


def string_equality_distinct_count(texts: tuple[str, ...]) -> int:
    return len({t.strip() for t in texts})
