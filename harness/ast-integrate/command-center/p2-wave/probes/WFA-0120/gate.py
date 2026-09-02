#!/usr/bin/env python3
"""Anti-rebuild gate for BUILD-NEW workflow routes (WFA-0120).

Fails a BUILD-NEW proposal when the registry already contains a candidate
whose definition-derived mechanism set *covers* the proposal (proposal ⊆
existing, non-empty) and whose evidence is equal or better.

A gate that has never rejected a rebuild has not been shown to detect one:
call plant_rebuild() and evaluate() in the both-states probes.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

NAMED_FAILURE = (
    "workflow discovery ignores an existing superior workflow and rebuilds it"
)

VERDICT_BLOCK = "BLOCK-REBUILD"
VERDICT_ALLOW = "ALLOW-BUILD-NEW"
VERDICT_SKIP = "SKIP-NOT-BUILD-NEW"
VERDICT_INCOMPLETE = "BLOCK-INCOMPLETE"

TIER_RANK = {"E1": 4, "E2": 3, "E3": 2, "E4": 1, "NONE": 0}

# Closed vocabulary. An id not in this set is a vocabulary gap, not free text.
VOCAB: frozenset[str] = frozenset(
    {
        "mech.blind-independent-first-pass",
        "mech.shared-context-deliberation",
        "mech.deterministic-replay",
        "mech.nondeterministic-sampling",
        "mech.fire-and-forget-dispatch",
        "mech.blocking-fan-in-barrier",
        "mech.citation-grounding",
        "mech.contradiction-hunt",
        "mech.licence-verify",
        "mech.prior-art-search",
        "mech.static-scan",
        "mech.benchmark-harness",
        "mech.human-checkpoint",
        "mech.provenance-carry",
        "mech.fusion-collapse",
        "mech.schema-validate",
        "mech.injection-neutralise",
        "mech.token-bucket",
        "mech.lattice-surgery-schedule",
        "mech.quantum-error-surface",
        "mech.zk-circuit-arithmetization",
        "mech.homomorphic-eval-schedule",
        "mech.incremental-sat-cone",
        "mech.discrete-diffgeo-remesh",
        "mech.crdt-frontier",
    }
)


def mechanisms_of(record: Mapping[str, Any]) -> frozenset[str]:
    """Definition-derived set only. Self-description is never credited."""
    raw = record.get("mechanisms_from_definition")
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(str(x).strip() for x in raw if isinstance(x, str) and x.strip())


def vocab_gaps(mechs: Iterable[str]) -> list[str]:
    return sorted(m for m in mechs if m not in VOCAB)


def evidence_key(record: Mapping[str, Any]) -> tuple[int, int, int]:
    tier = str(record.get("evidence_tier") or "NONE")
    try:
        sources = int(record.get("independent_source_count") or 0)
    except (TypeError, ValueError):
        sources = 0
    try:
        quality = int(record.get("quality") or 0)
    except (TypeError, ValueError):
        quality = 0
    return (TIER_RANK.get(tier, 0), sources, quality)


def overlap(proposal: frozenset[str], existing: frozenset[str]) -> dict[str, Any]:
    inter = proposal & existing
    union = proposal | existing
    jaccard = (len(inter) / len(union)) if union else 0.0
    return {
        "intersection": sorted(inter),
        "proposal_only": sorted(proposal - existing),
        "existing_only": sorted(existing - proposal),
        "jaccard": round(jaccard, 6),
        "proposal_subset_of_existing": bool(proposal) and proposal <= existing,
        "same_set": bool(proposal) and proposal == existing,
    }


def nearest_existing(
    proposal: Mapping[str, Any], registry: Iterable[Mapping[str, Any]]
) -> dict[str, Any] | None:
    p = mechanisms_of(proposal)
    best: dict[str, Any] | None = None
    best_key: tuple | None = None
    for cand in registry:
        if not isinstance(cand, Mapping):
            continue
        ov = overlap(p, mechanisms_of(cand))
        key = (
            1 if ov["proposal_subset_of_existing"] else 0,
            float(ov["jaccard"]),
            evidence_key(cand),
            str(cand.get("id") or ""),
        )
        if best_key is None or key > best_key:
            best_key = key
            best = {"candidate": cand, "overlap": ov}
    return best


def plant_rebuild(candidate: Mapping[str, Any], new_id: str) -> dict[str, Any]:
    """Rename an existing candidate and re-propose it as BUILD-NEW."""
    clone = deepcopy(dict(candidate))
    origin = str(candidate.get("id") or "")
    clone["id"] = new_id
    clone["kind"] = "blueprint"
    clone["route"] = "BUILD-NEW"
    clone["state"] = "NEW"
    clone["title"] = f"Renamed rebuild of {origin}"
    clone["evidence_tier"] = "E4"
    clone["independent_source_count"] = 0
    clone["quality"] = 0
    clone["planted_from"] = origin
    clone["mechanisms_from_definition"] = sorted(mechanisms_of(candidate))
    return clone


def evaluate(
    proposal: Mapping[str, Any],
    registry: Iterable[Mapping[str, Any]],
    *,
    enabled: bool = True,
) -> dict[str, Any]:
    pid = str(proposal.get("id") or "")
    route = str(proposal.get("route") or "")
    pset = mechanisms_of(proposal)
    gaps = vocab_gaps(pset)
    base = {
        "proposal_id": pid,
        "route": route,
        "named_failure": NAMED_FAILURE,
        "gated": enabled,
        "vocab_gaps": gaps,
        "proposal_mechanisms": sorted(pset),
    }
    if route != "BUILD-NEW":
        return {
            **base,
            "verdict": VERDICT_SKIP,
            "reason": "route-is-not-BUILD-NEW",
            "cited_candidate_id": None,
            "nearest_existing_id": None,
            "overlap": None,
            "evidence_comparison": None,
        }
    if not pset:
        return {
            **base,
            "verdict": VERDICT_INCOMPLETE,
            "reason": "mechanism-set-empty",
            "cited_candidate_id": None,
            "nearest_existing_id": None,
            "overlap": None,
            "evidence_comparison": None,
        }

    rows = [c for c in registry if isinstance(c, Mapping)]
    near = nearest_existing(proposal, rows)
    if near is None:
        return {
            **base,
            "verdict": VERDICT_ALLOW,
            "reason": "registry-empty",
            "cited_candidate_id": None,
            "nearest_existing_id": None,
            "overlap": None,
            "evidence_comparison": None,
        }

    cand = near["candidate"]
    ov = near["overlap"]
    cid = str(cand.get("id") or "")
    ev_ex = evidence_key(cand)
    ev_pr = evidence_key(proposal)
    comparison = {
        "existing": list(ev_ex),
        "proposal": list(ev_pr),
        "existing_ge_proposal": ev_ex >= ev_pr,
        "rule": "lexicographic (tier_rank, independent_source_count, quality)",
    }

    if not enabled:
        return {
            **base,
            "verdict": VERDICT_ALLOW,
            "reason": "gate-bypassed",
            "cited_candidate_id": None,
            "nearest_existing_id": cid,
            "overlap": ov,
            "evidence_comparison": comparison,
        }

    covers = bool(ov["proposal_subset_of_existing"])
    dominates = covers and ev_ex >= ev_pr
    if dominates:
        return {
            **base,
            "verdict": VERDICT_BLOCK,
            "reason": "existing-covers-mechanism-set-equal-or-better-evidence",
            "cited_candidate_id": cid,
            "nearest_existing_id": cid,
            "overlap": ov,
            "evidence_comparison": comparison,
        }
    return {
        **base,
        "verdict": VERDICT_ALLOW,
        "reason": "no-covering-equal-or-better-existing",
        "cited_candidate_id": None,
        "nearest_existing_id": cid,
        "overlap": ov,
        "evidence_comparison": comparison,
    }


def evaluate_build_new_route(
    corpus: Mapping[str, Any], *, enabled: bool = True
) -> list[dict[str, Any]]:
    from query import registry_candidates, by_route  # local typed query

    registry = registry_candidates(corpus)
    proposals = by_route(corpus, "BUILD-NEW")
    return [evaluate(p, registry, enabled=enabled) for p in proposals]
