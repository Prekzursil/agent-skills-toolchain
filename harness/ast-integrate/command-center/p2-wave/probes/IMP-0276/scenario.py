"""Shared fixtures and measurements for IMP-0276 anonymity probes."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.integrity.anonymity import (  # noqa: E402
    AnonymityConfig,
    census_real_ids,
    linkage_attack,
    publish_session,
    score_linkage,
    secret_from_text,
    truth_index_from_raw,
)

PARTICIPANTS = [
    "part-alice-7f3a",
    "part-blake-91c2",
    "part-chloe-44de",
    "part-devon-b18f",
    "part-ellis-0aa1",
    "part-farah-66c9",
    "part-gwen-e204",
    "part-hiro-3b77",
]
DISPLAY_NAMES = [p.replace("part-", "Name ") for p in PARTICIPANTS]
N_PARTICIPANTS = len(PARTICIPANTS)
N_ROUNDS = 12
N_SESSIONS = 8
CHANCE = 1.0 / N_PARTICIPANTS
FULL_ANON_MAX_MEAN = CHANCE + 0.10
UNSHUFFLED_MIN = 0.90
STYLE_MARKERS = [
    "Henceforth the lemma holds, q.e.d.; moreover the bound is tight.",
    "yeah so like we should just ship it lol wait maybe not???",
    "SHORT. STOP. FRAGMENT. AGAIN.",
    "Insofar as the prior is misspecified, posterior mass concentrates elsewhere.",
    "ok. ok. repeating myself. ok. repeating myself.",
    "Tokenomic grawlix: foo-bar-baz 12345 --- nnnn.",
    "A measured, even cadence with little ornament and no contractions.",
    "WHY ARE WE YELLING ABOUT LATENCY AND TOKENS AND STYLE????",
]
CHANNELS = ("order", "timing", "tokens", "style")


def _latency_ms(pid: str) -> int:
    return 400 + (hashlib.sha256(pid.encode()).digest()[0] % 50) * 80


def _token_count(pid: str) -> int:
    return 120 + (hashlib.sha256(pid.encode()).digest()[1] % 40) * 17


def _style(pid: str) -> str:
    return STYLE_MARKERS[PARTICIPANTS.index(pid)]


def build_raw_session(*, session_i: int, n_rounds: int = N_ROUNDS) -> dict[str, Any]:
    """Stable seating order; per-person distinctive timing/tokens/style every round."""
    rounds = []
    for r in range(n_rounds):
        turns = []
        for pid in PARTICIPANTS:
            turns.append(
                {
                    "participant_id": pid,
                    "display_name": pid.replace("part-", "Name "),
                    "elapsed_ms": _latency_ms(pid) + r,
                    "token_count": _token_count(pid),
                    "text": f"round-{r} {pid} {_style(pid)}",
                    "vote": "ACCEPT" if PARTICIPANTS.index(pid) < 4 else "HOLD",
                    "position": "expand" if PARTICIPANTS.index(pid) % 2 == 0 else "hold",
                }
            )
        rounds.append({"round_id": f"r{r}", "turns": turns})
    return {
        "session_id": f"council-sess-{session_i:02d}",
        "anonymity": {
            "enabled": True,
            "level": "pseudonymous",
            "shuffle_order": True,
            "strip_timing": True,
            "strip_token_counts": True,
            "strip_style": True,
        },
        "rounds": rounds,
    }


def full_config() -> AnonymityConfig:
    return AnonymityConfig(
        enabled=True,
        level="pseudonymous",
        shuffle_order=True,
        strip_timing=True,
        strip_token_counts=True,
        strip_style=True,
    )


def leaky_order_config() -> AnonymityConfig:
    """Names masked and metadata stripped, but seating order left unshuffled."""
    return AnonymityConfig(
        enabled=True,
        level="pseudonymous",
        shuffle_order=False,
        strip_timing=True,
        strip_token_counts=True,
        strip_style=True,
    )


def measure_session(
    raw: dict[str, Any], secret: bytes, config: AnonymityConfig
) -> dict[str, Any]:
    published = publish_session(raw, secret, config)
    hits = census_real_ids(published, PARTICIPANTS)
    hits += census_real_ids(published, DISPLAY_NAMES)
    truth = truth_index_from_raw(raw, published, secret=secret, config=config)
    scored: dict[str, Any] = {}
    for channel in CHANNELS:
        attack = linkage_attack(published["rounds"], channel=channel)
        scored[channel] = score_linkage(attack, truth)
        scored[channel]["channels_present"] = attack["channels_present"]
    label_sets = []
    for rec in published["rounds"]:
        labels = [t.get("pseudonym") for t in rec["turns"]]
        label_sets.append(set(x for x in labels if x))
    labels_leak_across_rounds = False
    if label_sets and all(label_sets):
        labels_leak_across_rounds = any(
            label_sets[0] & label_sets[i] for i in range(1, len(label_sets))
        )
    return {
        "published": published,
        "census_hits": hits,
        "scored": scored,
        "labels_leak_across_rounds": labels_leak_across_rounds,
        "n_participants": N_PARTICIPANTS,
        "n_rounds": len(published["rounds"]),
        "chance": CHANCE,
    }


def run_full_anonymity_battery() -> dict[str, Any]:
    accuracies: list[float] = []
    census_total = 0
    label_leaks = 0
    channel_means: dict[str, list[float]] = {ch: [] for ch in CHANNELS}
    present: dict[str, list[bool]] = {ch: [] for ch in CHANNELS}
    for i in range(N_SESSIONS):
        raw = build_raw_session(session_i=i)
        secret = secret_from_text(f"imp-0276-sess-{i}")
        measured = measure_session(raw, secret, full_config())
        census_total += len(measured["census_hits"])
        if measured["labels_leak_across_rounds"]:
            label_leaks += 1
        for channel, row in measured["scored"].items():
            channel_means[channel].append(row["accuracy"])
            present[channel].append(bool(row["channels_present"].get(channel)))
        accuracies.append(measured["scored"]["order"]["accuracy"])
    mean_order = sum(accuracies) / len(accuracies)
    channel_present_any = {ch: any(v) for ch, v in present.items()}
    return {
        "n_sessions": N_SESSIONS,
        "n_participants": N_PARTICIPANTS,
        "n_rounds": N_ROUNDS,
        "chance": CHANCE,
        "mean_order_accuracy": mean_order,
        "session_order_accuracies": accuracies,
        "channel_mean_accuracy": {
            ch: (sum(vals) / len(vals) if vals else None)
            for ch, vals in channel_means.items()
        },
        "channel_present_any": channel_present_any,
        "census_hit_count": census_total,
        "label_leak_sessions": label_leaks,
        "pass_threshold": FULL_ANON_MAX_MEAN,
        "passed": (
            mean_order <= FULL_ANON_MAX_MEAN
            and census_total == 0
            and label_leaks == 0
            and not channel_present_any["timing"]
            and not channel_present_any["tokens"]
            and not channel_present_any["style"]
        ),
    }


def run_unshuffled_control() -> dict[str, Any]:
    raw = build_raw_session(session_i=99)
    secret = secret_from_text("imp-0276-unshuffled")
    measured = measure_session(raw, secret, leaky_order_config())
    order_acc = measured["scored"]["order"]["accuracy"]
    return {
        "n_participants": N_PARTICIPANTS,
        "n_rounds": N_ROUNDS,
        "chance": CHANCE,
        "order_accuracy": order_acc,
        "census_hit_count": len(measured["census_hits"]),
        "channel_present": measured["scored"]["order"]["channels_present"],
        "min_threshold": UNSHUFFLED_MIN,
        "passed": order_acc >= UNSHUFFLED_MIN and order_acc > CHANCE + 0.50,
    }


def security_refuter(full: dict[str, Any], leaky: dict[str, Any]) -> dict[str, Any]:
    """Defaults to REFUTED when evidence is missing or the control cannot go red."""
    missing = []
    if full.get("chance") is None:
        missing.append("chance_baseline")
    if full.get("mean_order_accuracy") is None:
        missing.append("full_anon_accuracy")
    if leaky.get("order_accuracy") is None:
        missing.append("unshuffled_accuracy")
    if full.get("census_hit_count") is None:
        missing.append("census")
    if missing:
        return {
            "verdict": "REFUTED",
            "independent": True,
            "role": "security-refuter",
            "default_when_insufficient": "REFUTED",
            "reason": "insufficient evidence: " + ",".join(missing),
        }
    if full["census_hit_count"] != 0:
        return {
            "verdict": "REFUTED",
            "independent": True,
            "role": "security-refuter",
            "reason": "real ids survived in the published artifact",
        }
    if full["mean_order_accuracy"] > full["pass_threshold"]:
        return {
            "verdict": "REFUTED",
            "independent": True,
            "role": "security-refuter",
            "reason": "linkage accuracy above chance bound",
        }
    if leaky["order_accuracy"] < leaky["min_threshold"]:
        return {
            "verdict": "REFUTED",
            "independent": True,
            "role": "security-refuter",
            "reason": "negative control did not rise above chance",
        }
    return {
        "verdict": "PASS",
        "independent": True,
        "role": "security-refuter",
        "default_when_insufficient": "REFUTED",
        "reason": (
            "linkage at chance under full anonymity; unshuffled order "
            "raises accuracy; census empty"
        ),
    }


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2)
