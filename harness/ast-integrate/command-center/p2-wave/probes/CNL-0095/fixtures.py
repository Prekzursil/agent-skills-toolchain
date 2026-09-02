"""Planted council transcripts for CNL-0095.

Texts are chosen so paraphrase pairs Jaccard-merge (>=0.80) and distinct
ideas do not. Category labels are a fixture taxonomy; live CNL-0054
taxonomy is absent on this tree and is a residual unknown.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

TAXONOMY = [
    "cost",
    "safety",
    "latency",
    "operability",
    "correctness",
    "rollback",
]

IDEAS = {
    "cost": "Replace the always-on GPU worker pool with scale-to-zero inference to cut idle spend",
    "safety": "Fail closed on payment-vendor timeout by inserting a circuit breaker in the charge path",
    "latency": "Put a Redis cache in front of the session store to cut read latency",
    "operability": "Ship a runbook plus a single dashboard for the new charge path before go-live",
    "correctness": "Add a golden-replay suite that the charge path must match before each release",
    "rollback": "Keep the previous charge path behind a flag so a bad release reverts in one toggle",
}

LATENCY_PARAPHRASE = (
    "Put a Redis cache in front of the session store, cutting read latency"
)

OBJS = {
    "cost": "Scale-to-zero cold starts will miss the p99 latency SLO during traffic spikes",
    "safety": "Circuit breaker fail-closed drops legitimate charges and inflates support load",
    "latency": "Redis cache stampede will drop the session store when many TTLs expire together",
    "operability": "A runbook without page-owner mapping still leaves night on-call guessing",
    "correctness": "Golden replay that only covers the happy path will rubber-stamp charge bugs",
    "rollback": "A flag that is default-on in production is not a rollback, it is a latent dual-path",
}

LATENCY_OBJ_PARAPHRASE = (
    "A Redis cache stampede will drop the session store when many TTLs expire together"
)


def _base(fid: str, idea_q: int, obj_q: int, question_class: str) -> dict[str, Any]:
    return {
        "id": fid,
        "question_id": "charge-path-cutover",
        "question_class": question_class,
        "declared_divergence": {
            "idea_quota": idea_q,
            "objection_quota": obj_q,
            "taxonomy": list(TAXONOMY),
        },
        "events": [],
    }


def _idea(cat: str, text: str, rnd: int, eid: str) -> dict[str, Any]:
    return {
        "kind": "idea",
        "id": eid,
        "category": cat,
        "text": text,
        "round": rnd,
    }


def _obj(cat: str, text: str, rnd: int, eid: str) -> dict[str, Any]:
    return {
        "kind": "objection",
        "id": eid,
        "category": cat,
        "text": text,
        "round": rnd,
    }


def _converge(rnd: int, thesis: str) -> dict[str, Any]:
    return {"kind": "converge", "round": rnd, "thesis": thesis}


THESIS_CACHE = "Adopt the Redis session-store cache and stop."


def planted_bad() -> dict[str, Any]:
    """Pathology present: first converge with paraphrase-padded ideas, quotas unmet."""
    run = _base("planted-bad", 6, 4, "hard")
    # Six idea events and four objection events, all paraphrases of one
    # cluster each: an event-count decoy is SILENT; the cluster detector FIREs.
    run["events"] = [
        _idea("latency", IDEAS["latency"], 1, "i-lat-1"),
        _idea("latency", LATENCY_PARAPHRASE, 1, "i-lat-1b"),
        _idea("latency", IDEAS["latency"], 1, "i-lat-1c"),
        _idea("latency", LATENCY_PARAPHRASE, 1, "i-lat-1d"),
        _idea("latency", IDEAS["latency"], 1, "i-lat-1e"),
        _idea("latency", LATENCY_PARAPHRASE, 1, "i-lat-1f"),
        _obj("latency", OBJS["latency"], 1, "o-lat-1"),
        _obj("latency", LATENCY_OBJ_PARAPHRASE, 1, "o-lat-1b"),
        _obj("latency", OBJS["latency"], 1, "o-lat-1c"),
        _obj("latency", LATENCY_OBJ_PARAPHRASE, 1, "o-lat-1d"),
        _converge(1, THESIS_CACHE),
    ]
    return run


def known_present() -> dict[str, Any]:
    """Detector-control clone: known-present instance, separate fixture id."""
    run = planted_bad()
    run["id"] = "known-present"
    return run


def known_good() -> dict[str, Any]:
    """Quotas met with six distinct ideas and four distinct objections."""
    run = _base("known-good", 6, 4, "hard")
    events: list[dict[str, Any]] = []
    for i, cat in enumerate(TAXONOMY, start=1):
        events.append(_idea(cat, IDEAS[cat], i, f"i-{cat}"))
    for i, cat in enumerate(TAXONOMY[:4], start=1):
        events.append(_obj(cat, OBJS[cat], i, f"o-{cat}"))
    events.append(
        _converge(6, "Cut over behind a flag after replay, cache, and breaker land.")
    )
    run["events"] = events
    return run


def easy_met_quota() -> dict[str, Any]:
    """Easy question: small quotas attained in round 1. Must be SILENT.

    Distinguishes premature convergence from a genuinely easy question
    on quota attainment, not round count.
    """
    run = _base("easy-met-quota", 2, 2, "easy")
    run["events"] = [
        _idea("latency", IDEAS["latency"], 1, "i-lat"),
        _idea("operability", IDEAS["operability"], 1, "i-ops"),
        _obj("latency", OBJS["latency"], 1, "o-lat"),
        _obj("operability", OBJS["operability"], 1, "o-ops"),
        _converge(1, "Cache plus a runbook is enough for this narrow question."),
    ]
    return run


def round10_premature() -> dict[str, Any]:
    """Hard question, ten rounds of paraphrases, still one idea cluster. Must FIRE.

    Proves round count is not the signal: late stop can still be premature.
    """
    run = _base("round10-premature", 6, 4, "hard")
    events: list[dict[str, Any]] = []
    for rnd in range(1, 11):
        events.append(
            _idea("latency", IDEAS["latency"] if rnd % 2 else LATENCY_PARAPHRASE, rnd, f"i-{rnd}")
        )
        events.append(
            _obj(
                "latency",
                OBJS["latency"] if rnd % 2 else LATENCY_OBJ_PARAPHRASE,
                rnd,
                f"o-{rnd}",
            )
        )
    events.append(_converge(10, THESIS_CACHE))
    run["events"] = events
    return run


def clean_over_quota() -> dict[str, Any]:
    run = known_good()
    run["id"] = "clean-over-quota"
    run["events"] = list(run["events"])
    extra = [
        _idea("cost", IDEAS["cost"] + " and park unused accelerators", 6, "i-cost-2"),
        _obj("rollback", OBJS["rollback"], 6, "o-rollback"),
    ]
    conv = run["events"].pop()
    run["events"].extend(extra)
    run["events"].append(conv)
    return run


def clean_late_round_met() -> dict[str, Any]:
    """Quotas already met; converge at round 12. Must be SILENT (not 'late is bad')."""
    run = known_good()
    run["id"] = "clean-late-round-met"
    events = [e for e in run["events"] if e.get("kind") != "converge"]
    events.append(
        _converge(12, "Cut over behind a flag after replay, cache, and breaker land.")
    )
    run["events"] = events
    return run


def clean_exact_quota() -> dict[str, Any]:
    run = known_good()
    run["id"] = "clean-exact-quota"
    return run


def no_converge() -> dict[str, Any]:
    run = planted_bad()
    run["id"] = "no-converge"
    run["events"] = [e for e in run["events"] if e.get("kind") != "converge"]
    return run


def theater_second_round() -> dict[str, Any]:
    """Premature stop plus a second round of paraphrases in the same category."""
    run = planted_bad()
    run["id"] = "theater-second-round"
    extra = [
        _idea("latency", LATENCY_PARAPHRASE, 2, "i-lat-r2a"),
        _idea("latency", IDEAS["latency"], 2, "i-lat-r2b"),
        _obj("latency", LATENCY_OBJ_PARAPHRASE, 2, "o-lat-r2"),
        _converge(2, THESIS_CACHE),
    ]
    run["events"] = list(run["events"]) + extra
    return run


def complement_rediverge() -> dict[str, Any]:
    """Premature stop plus complement ideas in uncovered categories + new objections."""
    run = planted_bad()
    run["id"] = "complement-rediverge"
    extra: list[dict[str, Any]] = []
    for cat in TAXONOMY:
        if cat == "latency":
            continue
        extra.append(_idea(cat, IDEAS[cat], 2, f"i-{cat}-r2"))
    extra.extend(
        [
            _obj("cost", OBJS["cost"], 2, "o-cost-r2"),
            _obj("safety", OBJS["safety"], 2, "o-safety-r2"),
            _obj("operability", OBJS["operability"], 2, "o-ops-r2"),
            _converge(2, "Cut over behind a flag after replay, cache, and breaker land."),
        ]
    )
    run["events"] = list(run["events"]) + extra
    return run


def clean_fixtures() -> list[dict[str, Any]]:
    return [
        known_good(),
        easy_met_quota(),
        clean_over_quota(),
        clean_late_round_met(),
        clean_exact_quota(),
    ]


def all_named() -> dict[str, dict[str, Any]]:
    return {
        "planted-bad": planted_bad(),
        "known-present": known_present(),
        "known-good": known_good(),
        "easy-met-quota": easy_met_quota(),
        "round10-premature": round10_premature(),
        "clean-over-quota": clean_over_quota(),
        "clean-late-round-met": clean_late_round_met(),
        "clean-exact-quota": clean_exact_quota(),
        "no-converge": no_converge(),
        "theater-second-round": theater_second_round(),
        "complement-rediverge": complement_rediverge(),
    }


def dumps() -> dict[str, Any]:
    return {k: deepcopy(v) for k, v in all_named().items()}
