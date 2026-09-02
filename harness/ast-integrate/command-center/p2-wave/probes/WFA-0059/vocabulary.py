"""Closed, versioned mechanism vocabulary for WFA-0059 extraction.

Ids use the `mech:` namespace so they cannot collide with candidate (`wf-`),
blueprint (`bp-`), option, or catalog unit ids.

An unmapped free-text string is a vocabulary gap, not a free-text fallback
id. The WFA-0058 estate artifact is absent on this tree; this pack is the
closed vocabulary the extractor uses, and is replaced if
command-center/wfa/WFA-0058-mechanism-vocabulary.json later lands.
"""
from __future__ import annotations

from typing import Any

VOCAB_VERSION = "wfa-0059.vocab.1"
VOCAB_NAMESPACE = "mech:"

# Canonical id, definition, discriminating example, implementation needles
# (definition fields only), and prose aliases (self-description field).
MECHANISMS: tuple[dict[str, Any], ...] = (
    {
        "id": "mech:blind-independent-first-pass",
        "definition": (
            "Raters produce a first score without seeing other raters' scores "
            "or a shared transcript."
        ),
        "discriminating_example": (
            "independent-rating stage; scores without seeing other ballots"
        ),
        "impl_needles": (
            "blind independent first pass",
            "scores without seeing other",
            "independent-rating",
        ),
        "prose_aliases": (
            "blind independent first pass",
            "blind first pass",
            "independent scoring round",
        ),
    },
    {
        "id": "mech:shared-context-deliberation",
        "definition": (
            "Agents read a shared transcript and update a joint position; "
            "later speakers see earlier speakers."
        ),
        "discriminating_example": "shared-deliberation stage with a common transcript",
        "impl_needles": (
            "shared transcript deliberation",
            "shared-deliberation",
            "joint position from a common transcript",
        ),
        "prose_aliases": (
            "shared-context deliberation",
            "shared context deliberation",
            "open deliberation",
        ),
    },
    {
        "id": "mech:deterministic-replay",
        "definition": (
            "The same pinned inputs and seed yield byte-identical outputs; "
            "replay is a function, not a resample."
        ),
        "discriminating_example": "deterministic-replay stage; same seed same bytes",
        "impl_needles": (
            "byte-identical replay",
            "deterministic-replay",
            "same pinned inputs and seed yield byte-identical",
        ),
        "prose_aliases": (
            "deterministic replay",
            "reproducible replay",
        ),
    },
    {
        "id": "mech:nondeterministic-sampling",
        "definition": (
            "A sampling step draws from a distribution; repeats need not match."
        ),
        "discriminating_example": "stochastic-sample stage; temperature sampling",
        "impl_needles": (
            "temperature sampling draw",
            "stochastic-sample",
            "draws from a distribution",
        ),
        "prose_aliases": (
            "nondeterministic sampling",
            "non-deterministic sampling",
            "temperature sampling",
        ),
    },
    {
        "id": "mech:fire-and-forget-dispatch",
        "definition": (
            "Work is dispatched without waiting for the worker's result at "
            "the call site."
        ),
        "discriminating_example": "fire-forget-dispatch stage; no join at caller",
        "impl_needles": (
            "dispatch without waiting",
            "fire-forget-dispatch",
            "no join at the call site",
        ),
        "prose_aliases": (
            "fire-and-forget dispatch",
            "fire and forget dispatch",
            "fire-and-forget",
        ),
    },
    {
        "id": "mech:blocking-fan-in-barrier",
        "definition": (
            "A join waits for every dispatched branch before the next stage."
        ),
        "discriminating_example": "blocking-fan-in stage; wait-for-all barrier",
        "impl_needles": (
            "wait-for-all barrier",
            "blocking-fan-in",
            "join waits for every dispatched branch",
        ),
        "prose_aliases": (
            "blocking fan-in barrier",
            "blocking fan in barrier",
            "fan-in barrier",
        ),
    },
    {
        "id": "mech:typed-stopping-rule",
        "definition": (
            "Stop is an evaluable expression over run state, not free-text advice."
        ),
        "discriminating_example": "typed-stop-eval stage; max_stages compiled to a predicate",
        "impl_needles": (
            "evaluable stop expression",
            "typed-stop-eval",
            "stop compiles to a predicate",
        ),
        "prose_aliases": (
            "typed stopping rule",
            "evaluable stop rule",
            "typed stop",
        ),
    },
    {
        "id": "mech:information-partition",
        "definition": (
            "Judges are denied author identity or other specified fields before scoring."
        ),
        "discriminating_example": "info-partition stage; author id stripped before score",
        "impl_needles": (
            "author identity stripped",
            "info-partition",
            "denied author identity",
        ),
        "prose_aliases": (
            "information partition",
            "identity concealment",
        ),
    },
    {
        "id": "mech:provenance-anchor",
        "definition": (
            "Every node carries a dereferenceable source anchor (commit, URL, file:line)."
        ),
        "discriminating_example": "provenance-pin stage; commit SHA plus file:line",
        "impl_needles": (
            "dereferenceable source anchor",
            "provenance-pin",
            "commit sha plus file:line",
        ),
        "prose_aliases": (
            "provenance anchor",
            "source anchor",
            "provenance pin",
        ),
    },
    {
        "id": "mech:human-checkpoint",
        "definition": (
            "A stage blocks until a named human role records an accept or reject."
        ),
        "discriminating_example": "human-gate stage; owner accept required",
        "impl_needles": (
            "blocks until a named human",
            "human-gate",
            "owner accept required",
        ),
        "prose_aliases": (
            "human checkpoint",
            "human gate",
            "owner checkpoint",
        ),
    },
    {
        "id": "mech:idempotent-retry",
        "definition": (
            "Failed stages may rerun; a second success is observationally equal "
            "to the first."
        ),
        "discriminating_example": "idempotent-retry stage; replay-safe on failure",
        "impl_needles": (
            "replay-safe on failure",
            "idempotent-retry",
            "second success is observationally equal",
        ),
        "prose_aliases": (
            "idempotent retry",
            "safe retry",
        ),
    },
    {
        "id": "mech:fusion-decompose",
        "definition": (
            "A fused workflow can be decomposed back into the source component id set."
        ),
        "discriminating_example": "fusion-decompose stage; recover source ids",
        "impl_needles": (
            "decomposed back into the source",
            "fusion-decompose",
            "recover source component ids",
        ),
        "prose_aliases": (
            "fusion decompose",
            "decomposable fusion",
        ),
    },
)

MECH_BY_ID = {m["id"]: m for m in MECHANISMS}
CLOSED_IDS = frozenset(MECH_BY_ID)


def as_public() -> dict[str, Any]:
    return {
        "version": VOCAB_VERSION,
        "namespace": VOCAB_NAMESPACE,
        "closed": True,
        "n": len(MECHANISMS),
        "ids": [m["id"] for m in MECHANISMS],
        "records": [
            {
                "id": m["id"],
                "definition": m["definition"],
                "discriminating_example": m["discriminating_example"],
            }
            for m in MECHANISMS
        ],
        "collision_rule": (
            "mech: prefix is disjoint from wf-, bp-, opt-, and catalog unit ids"
        ),
        "unmapped_policy": "vocabulary-gap, never a free-text fallback id",
        "replaces": "command-center/wfa/WFA-0058-mechanism-vocabulary.json when present",
    }
