#!/usr/bin/env python3
"""Planted dominant vs balanced casts for TST-0275.

Dominant: loud has many long utterances and durable claims; quiet seats have
short perishable claims that loud later rebuts. Unenforced extra-floor feeds
the unique remaining-utterance leader (loud). Enforced speaking quotas skip
loud after max_turns_per_seat.

Balanced: equal scripts, remaining counts stay tied so extra-floor is silent,
and utterances sit under the token cap so enforcement is a no-op.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
from tools.council.simulate import (  # noqa: E402
    compare_runs,
    digest_text,
    run_council,
    seats_of,
    speaking_quotas,
)

SEED = 275
LOUD = "loud"
QUIET = ("quiet-a", "quiet-b")
SEATS = (LOUD, *QUIET)
SPEC_ID = "spec.tst-0275.speaking-quota"
MAX_ROUNDS = 4
MAX_TURNS = 2
MAX_TOKENS = 20
EXTRA_SLOTS = 2
LOUD_UTTERANCES = 12
QUIET_UTTERANCES = 2
BALANCED_UTTERANCES = 2
TURN_SKEW_MIN = 0.55
POST_TURN_MAX = 0.40
BALANCE_EPS = 0.08
PERTURB_EPS = 1e-12


def spec() -> dict[str, Any]:
    return {
        "id": SPEC_ID,
        "title": "Speaking-quota enforcement (TST-0275)",
        "seats": [
            {"id": LOUD, "role": "dominant"},
            {"id": QUIET[0], "role": "analyst"},
            {"id": QUIET[1], "role": "skeptic"},
        ],
        "scheduler": {
            "order": "round-robin",
            "max_rounds": MAX_ROUNDS,
            "speaking_quotas": {
                "max_turns_per_seat": MAX_TURNS,
                "max_tokens_per_turn": MAX_TOKENS,
                "extra_floor_slots_per_round": EXTRA_SLOTS,
            },
        },
    }


def _words(prefix: str, n: int) -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def _loud_utt(i: int, quiet_claim_ids: list[str]) -> dict[str, Any]:
    rebuts = list(quiet_claim_ids)
    return {
        "text": _words(f"LOUD{i}v", 40),
        "claims": [
            {"id": f"loud-{i}-c1", "body": f"durable thesis {i}a", "durable": True},
            {"id": f"loud-{i}-c2", "body": f"durable thesis {i}b", "durable": True},
        ],
        "evidence": [
            {"id": f"ev-loud-{i}-a", "cite": f"planted-source-{i}a"},
            {"id": f"ev-loud-{i}-b", "cite": f"planted-source-{i}b"},
        ],
        "rebuts": rebuts,
    }


def _quiet_utt(seat: str, i: int) -> dict[str, Any]:
    tag = "qa" if seat == QUIET[0] else "qb"
    return {
        "text": _words(f"{tag}{i}t", 10),
        "claims": [{"id": f"{tag}-{i}", "body": f"perishable {seat} {i}", "durable": False}],
        "evidence": [{"id": f"ev-{tag}-{i}", "cite": f"quiet-source-{tag}-{i}"}],
        "rebuts": [],
    }


def dominant_cast() -> dict[str, Any]:
    """Loud rebuts every quiet claim whose index is strictly less than loud's index."""
    personas = []
    quiet_ids_by_index: dict[int, list[str]] = {}
    for seat in QUIET:
        tag = "qa" if seat == QUIET[0] else "qb"
        utts = []
        for i in range(QUIET_UTTERANCES):
            utts.append(_quiet_utt(seat, i))
            quiet_ids_by_index.setdefault(i, []).append(f"{tag}-{i}")
        personas.append({"seat_id": seat, "utterances": utts})
    loud_utts = []
    for i in range(LOUD_UTTERANCES):
        prior: list[str] = []
        for j in range(i):
            prior.extend(quiet_ids_by_index.get(j, []))
        loud_utts.append(_loud_utt(i, prior))
    personas.insert(0, {"seat_id": LOUD, "utterances": loud_utts})
    return {"id": "cast.tst-0275.dominant", "seed": SEED, "personas": personas}


def balanced_cast() -> dict[str, Any]:
    personas = []
    for seat in SEATS:
        utts = []
        for i in range(BALANCED_UTTERANCES):
            utts.append(
                {
                    "text": _words(f"{seat}{i}b", 8),
                    "claims": [{"id": f"{seat}-{i}-c", "body": f"balanced {seat} {i}"}],
                    "evidence": [{"id": f"ev-{seat}-{i}", "cite": f"bal-{seat}-{i}"}],
                    "rebuts": [],
                }
            )
        personas.append({"seat_id": seat, "utterances": utts})
    return {"id": "cast.tst-0275.balanced", "seed": SEED, "personas": personas}


def _share_table(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "counts": copy.deepcopy(result["counts"]),
        "shares": copy.deepcopy(result["shares"]),
        "turns_taken": copy.deepcopy(result["turns_taken"]),
        "transcript_sha256": result["transcript_sha256"],
        "event_count": result["event_count"],
        "enforce_quotas": result["enforce_quotas"],
    }


def four_stats_present(table: dict[str, Any], seats: list[str]) -> bool:
    shares = table.get("shares") or {}
    counts = table.get("counts") or {}
    keys = ("turns", "tokens", "surviving_claims", "cited_evidence")
    for s in seats:
        if s not in shares or s not in counts:
            return False
        for k in keys:
            if k not in shares[s] or k not in counts[s]:
                return False
    return True


def balanced_unperturbed(pre: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    same_hash = pre["transcript_sha256"] == post["transcript_sha256"]
    max_delta = 0.0
    for s in pre["seats"]:
        for k in ("turns", "tokens", "surviving_claims", "cited_evidence"):
            d = abs(float(pre["shares"][s][k]) - float(post["shares"][s][k]))
            if d > max_delta:
                max_delta = d
    n = len(pre["seats"])
    even = 1.0 / n
    within = True
    for s in pre["seats"]:
        for k in ("turns", "tokens", "surviving_claims", "cited_evidence"):
            if abs(float(pre["shares"][s][k]) - even) > BALANCE_EPS:
                within = False
    return {
        "transcripts_identical": same_hash,
        "max_share_delta": max_delta,
        "within_even_band": within,
        "unperturbed": same_hash and max_delta <= PERTURB_EPS,
    }


def run_unit() -> dict[str, Any]:
    sp = spec()
    seats = seats_of(sp)
    dom = dominant_cast()
    bal = balanced_cast()
    pre = run_council(sp, dom, enforce_quotas=False, seed=SEED)
    post = run_council(sp, dom, enforce_quotas=True, seed=SEED)
    pre2 = run_council(sp, dom, enforce_quotas=False, seed=SEED)
    post2 = run_council(sp, dom, enforce_quotas=True, seed=SEED)
    bal_off = run_council(sp, bal, enforce_quotas=False, seed=SEED)
    bal_on = run_council(sp, bal, enforce_quotas=True, seed=SEED)
    effect = compare_runs(pre, post, LOUD)
    balance = balanced_unperturbed(bal_off, bal_on)
    loud_pre_turns = float(pre["shares"][LOUD]["turns"])
    loud_post_turns = float(post["shares"][LOUD]["turns"])
    loud_post_surv = float(post["shares"][LOUD]["surviving_claims"])
    planted_skew = loud_pre_turns >= TURN_SKEW_MIN
    turn_bounded = (
        int(post["turns_taken"][LOUD]) <= speaking_quotas(sp)["max_turns_per_seat"]
        and loud_post_turns <= POST_TURN_MAX
    )
    outcome_persists = loud_post_surv > loud_post_turns
    determinism = (
        pre["transcript_sha256"] == pre2["transcript_sha256"]
        and post["transcript_sha256"] == post2["transcript_sha256"]
    )
    tests = {
        "planted_dominant_pre_quota_skew": {
            "pass": planted_skew,
            "loud_turn_share_pre": loud_pre_turns,
            "threshold": TURN_SKEW_MIN,
        },
        "post_quota_turn_share_bounded": {
            "pass": turn_bounded,
            "loud_turns": int(post["turns_taken"][LOUD]),
            "max_turns_per_seat": speaking_quotas(sp)["max_turns_per_seat"],
            "loud_turn_share_post": loud_post_turns,
            "threshold": POST_TURN_MAX,
        },
        "outcome_dominance_persists_after_turn_cap": {
            "pass": outcome_persists,
            "loud_surviving_claims_share_post": loud_post_surv,
            "loud_turn_share_post": loud_post_turns,
            "constructed": True,
            "why": (
                "Loud packs two durable claims per remaining turn and rebuts quiet "
                "claims spoken before the cap. Quiet's last-round claims survive "
                "because they speak after loud is skipped; surviving-claims share "
                "still exceeds turn share."
            ),
        },
        "both_states_balanced_unperturbed": {
            "pass": bool(balance["unperturbed"] and balance["within_even_band"]),
            **balance,
        },
        "four_share_statistics_present": {
            "pass": four_stats_present(_share_table(pre), seats)
            and four_stats_present(_share_table(post), seats),
        },
        "same_seed_determinism": {
            "pass": determinism,
            "pre": pre["transcript_sha256"],
            "post": post["transcript_sha256"],
        },
    }
    all_pass = all(bool(t.get("pass")) for t in tests.values())
    return {
        "pass": all_pass,
        "seats": seats,
        "loud_seat": LOUD,
        "spec": sp,
        "quotas": speaking_quotas(sp),
        "dominant": {
            "pre_quota": _share_table(pre),
            "post_quota": _share_table(post),
            "claim_ledger_post": post["claim_ledger"],
            "claim_ledger_pre": pre["claim_ledger"],
        },
        "balanced": {
            "pre_quota": _share_table(bal_off),
            "post_quota": _share_table(bal_on),
        },
        "effect_size": effect,
        "tests": tests,
        "casts": {"dominant": dom, "balanced": bal},
    }


def write_fixtures() -> None:
    fx = HERE / "fixtures"
    fx.mkdir(parents=True, exist_ok=True)
    (fx / "council-spec.quota.json").write_text(
        json.dumps(spec(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (fx / "dominant.cast.json").write_text(
        json.dumps(dominant_cast(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (fx / "balanced.cast.json").write_text(
        json.dumps(balanced_cast(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def input_status() -> dict[str, Any]:
    return {
        "tools/council/simulate.py": (REPO / "tools/council/simulate.py").is_file(),
        "command-center/schema/council-spec.schema.json": (
            REPO / "command-center/schema/council-spec.schema.json"
        ).is_file(),
        "_USER-PROMPTS.md": (REPO / "_USER-PROMPTS.md").is_file(),
        "command-center/receipts/TST-0257.json": (
            REPO / "command-center/receipts/TST-0257.json"
        ).is_file(),
        "tools/council/phases.py": (REPO / "tools/council/phases.py").is_file(),
    }


if __name__ == "__main__":
    write_fixtures()
    live = run_unit()
    print(json.dumps({k: live[k] for k in ("pass", "effect_size", "tests") if k in live}, indent=2))
    raise SystemExit(0 if live["pass"] else 1)
