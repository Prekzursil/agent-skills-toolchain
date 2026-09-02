#!/usr/bin/env python3
"""Deterministic council transcript replay for CNF-0086.

Replay consumes recorded proposals, critiques and ballots plus a seed.
The seed drives participant draw, vote tie-break and synthesize wording.
Live model calls are out of scope: this is transcript replay, not a new council.

Production tools/council is probed for; when absent this module is the SUT.
"""
from __future__ import annotations

import hashlib
import json
import random
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"

STAGES = (
    "ingest",
    "participant_draw",
    "propose",
    "critique",
    "vote",
    "synthesize",
)

RATIONALES = (
    "Majority of recorded ballots.",
    "Tie broken by seeded order.",
    "Quorum met from recorded roster.",
)

PRODUCTION_CANDIDATES = (
    "tools/council/cli/audit.py",
    "tools/council/artifacts/store.py",
    "tools/council/replay.py",
    "tools/council/runtime/replay.py",
)


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def rng_for(seed: int, purpose: str) -> random.Random:
    material = f"{int(seed)}|{purpose}".encode("utf-8")
    n = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
    return random.Random(n)


def load_transcript(name: str) -> dict:
    path = FIXTURES / name
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not doc.get("run_id"):
        raise ValueError(f"bad transcript {name}")
    return doc


def locate_production_replay(repo: Path | None = None) -> dict:
    root = repo or REPO
    present = []
    for rel in PRODUCTION_CANDIDATES:
        if (root / rel).is_file():
            present.append(rel)
    return {
        "tools_council_present": bool(present),
        "found_paths": present,
        "implementation_used": (
            "command-center/p2-wave/probes/CNF-0086/replay.py"
            if not present
            else present[0]
        ),
        "note": (
            "Production tools/council replay is absent on this worktree; "
            "confirmation runs the probe-local transcript replay. Not an ADV rebuild."
            if not present
            else "Production replay module located; confirmation still executes the probe-local engine for stage localization controls."
        ),
    }


def _tally(ballots: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for b in ballots:
        choice = str(b["choice"])
        counts[choice] = counts.get(choice, 0) + 1
    return dict(sorted(counts.items()))


def replay(
    transcript: dict,
    seed: int | None = None,
    *,
    ignore_seed: bool = False,
    inject_stage: str | None = None,
    inject_payload: dict | None = None,
) -> dict:
    """Replay a recorded council. Seed is consumed unless ignore_seed=True."""
    t = deepcopy(transcript)
    if inject_stage == "vote" and inject_payload:
        ballots = list(t.get("ballots") or [])
        if not ballots:
            raise ValueError("cannot inject vote into empty ballots")
        ballots[0] = {**ballots[0], **inject_payload}
        t["ballots"] = ballots
    if inject_stage == "propose" and inject_payload:
        props = list(t.get("proposals") or [])
        if not props:
            raise ValueError("cannot inject propose into empty proposals")
        props[0] = {**props[0], **inject_payload}
        t["proposals"] = props

    used_seed = 0 if ignore_seed else int(t["seed"] if seed is None else seed)

    ingest = {
        "run_id": t["run_id"],
        "question": t["question"],
        "participant_ids": [p["id"] for p in t["participants"]],
        "seed": used_seed,
    }

    order = [p["id"] for p in t["participants"]]
    rng_for(used_seed, "participant_draw").shuffle(order)
    participant_draw = {"order": list(order), "seed": used_seed}

    by_prop = {p["participant"]: p for p in t["proposals"]}
    propose = {"items": [by_prop[i] for i in order]}

    by_crit = {c["participant"]: c for c in t["critiques"]}
    critique = {"items": [by_crit[i] for i in order]}

    ballots = list(t["ballots"])
    tally = _tally(ballots)
    max_v = max(tally.values())
    leaders = sorted(k for k, v in tally.items() if v == max_v)
    tie = len(leaders) > 1
    winner = rng_for(used_seed, "tie-break").choice(leaders)
    vote = {
        "ballots": sorted(ballots, key=lambda b: b["participant"]),
        "tally": tally,
        "leaders": leaders,
        "winner": winner,
        "tie": tie,
        "seed": used_seed,
    }

    idx = rng_for(used_seed, "synthesize").randrange(len(RATIONALES))
    synthesize = {
        "recommendation": winner,
        "tally": tally,
        "rationale": RATIONALES[idx],
        "seed": used_seed,
        "participant_order": list(order),
    }

    stages = {
        "ingest": ingest,
        "participant_draw": participant_draw,
        "propose": propose,
        "critique": critique,
        "vote": vote,
        "synthesize": synthesize,
    }
    stage_digests = {name: digest(stages[name]) for name in STAGES}
    outcome = {name: stages[name] for name in STAGES}
    return {
        "run_id": t["run_id"],
        "seed": used_seed,
        "recommendation": winner,
        "tally": tally,
        "vote_tally": tally,
        "rationale": RATIONALES[idx],
        "participant_order": list(order),
        "tie": tie,
        "claims_deterministic_audit": bool(t.get("claims_deterministic_audit")),
        "stage_outputs": stages,
        "stage_digests": stage_digests,
        "outcome_sha256": digest(outcome),
    }


def recorded_original(transcript: dict) -> dict:
    """Load the frozen original decision, or a planted override for overclaim."""
    override = transcript.get("recorded_decision_override")
    if isinstance(override, dict) and override.get("recommendation"):
        live = public_decision(replay(transcript, int(transcript["seed"])))
        digests = dict(live["stage_digests"])
        digests["synthesize"] = "recorded-override-synthesize-mismatch"
        return {
            "run_id": transcript["run_id"],
            "seed": int(transcript["seed"]),
            "recommendation": override["recommendation"],
            "tally": override.get("tally") or {},
            "rationale": str(override.get("rationale") or ""),
            "participant_order": list(live["participant_order"]),
            "tie": bool(live["tie"]),
            "stage_digests": digests,
            "outcome_sha256": digest(override),
        }
    frozen = transcript.get("recorded_decision")
    if isinstance(frozen, dict) and frozen.get("recommendation"):
        return frozen
    return public_decision(replay(transcript, int(transcript["seed"])))


def public_decision(decision: dict) -> dict:
    """Comparable original/replayed record (no bulky stage_outputs)."""
    return {
        "run_id": decision["run_id"],
        "seed": decision["seed"],
        "recommendation": decision["recommendation"],
        "tally": decision["tally"],
        "rationale": decision["rationale"],
        "participant_order": decision["participant_order"],
        "tie": decision["tie"],
        "stage_digests": decision["stage_digests"],
        "outcome_sha256": decision["outcome_sha256"],
    }


def compare(original: dict, replayed: dict) -> dict:
    rec_id = original["recommendation"] == replayed["recommendation"]
    tally_id = original["tally"] == replayed["tally"]
    first = None
    orig_d = original.get("stage_digests") or {}
    rep_d = replayed.get("stage_digests") or {}
    for name in STAGES:
        if orig_d.get(name) != rep_d.get(name):
            first = name
            break
    mismatch = (not rec_id) or (not tally_id) or (first is not None)
    return {
        "recommendation_identical": rec_id,
        "tally_identical": tally_id,
        "first_divergent_stage": first,
        "mismatch": mismatch,
        "whole_run_mismatch_without_stage": bool(
            ((not rec_id) or (not tally_id)) and first is None
        ),
    }


def classify_overclaim(transcript: dict, comparison: dict) -> dict:
    claims = bool(transcript.get("claims_deterministic_audit"))
    diverged = comparison["recommendation_identical"] is False
    if claims and diverged:
        return {
            "fired": True,
            "classification": "overclaim",
            "reason": (
                "Council claims deterministic audit but replayed final "
                "recommendation diverges from the recorded decision."
            ),
        }
    if comparison.get("whole_run_mismatch_without_stage"):
        return {
            "fired": True,
            "classification": "replay-divergence",
            "reason": "Mismatch reported without a first divergent stage.",
        }
    return {
        "fired": False,
        "classification": "none",
        "reason": "No overclaim: either no determinism claim, or recommendation matched.",
    }


def seed_control(transcript: dict, seed_a: int, seed_b: int) -> dict:
    a = replay(transcript, seed_a)
    b = replay(transcript, seed_b)
    changed = a["outcome_sha256"] != b["outcome_sha256"]
    rec_changed = a["recommendation"] != b["recommendation"]
    ignored = replay(transcript, seed_a, ignore_seed=True)
    ignored_b = replay(transcript, seed_b, ignore_seed=True)
    ignore_hides_seed = ignored["outcome_sha256"] == ignored_b["outcome_sha256"]
    return {
        "performed": True,
        "original_seed": seed_a,
        "changed_seed": seed_b,
        "outcome_changed": changed,
        "recommendation_changed": rec_changed,
        "proves_seed_consumed": changed,
        "original_outcome_sha256": a["outcome_sha256"],
        "changed_outcome_sha256": b["outcome_sha256"],
        "seed_ignored_mutant_hides_change": ignore_hides_seed,
        "a_recommendation": a["recommendation"],
        "b_recommendation": b["recommendation"],
    }


def planted_stage_divergence(transcript: dict, stage: str = "vote") -> dict:
    base = replay(transcript)
    if stage == "vote":
        current = (transcript.get("ballots") or [{}])[0].get("choice")
        other = "defer" if current != "defer" else "adopt"
        mutant = replay(transcript, inject_stage="vote", inject_payload={"choice": other})
    elif stage == "propose":
        mutant = replay(
            transcript,
            inject_stage="propose",
            inject_payload={"text": "PLANTED-DIVERGENCE-PROPOSAL"},
        )
    else:
        raise ValueError(stage)
    cmp = compare(base, mutant)
    return {
        "planted_stage": stage,
        "reported_stage": cmp["first_divergent_stage"],
        "not_whole_run_only": cmp["first_divergent_stage"] is not None
        and not cmp["whole_run_mismatch_without_stage"],
        "comparison": cmp,
        "base_recommendation": base["recommendation"],
        "mutant_recommendation": mutant["recommendation"],
    }
