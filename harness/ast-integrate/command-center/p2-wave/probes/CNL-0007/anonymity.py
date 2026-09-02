#!/usr/bin/env python3
"""CNL-0007 anonymity levels: mint, emit, leak-check, de-anonymise.

Four runtime levels (named / pseudonymous / fully_blind / blind_then_revealed)
share one audit split: a participant-facing publishable log and a keeper-only
sealed binder. Attribution in the publishable log uses only the handle the
level allows. Opening or inlining the binder during the independence window
is a leak, as is rewriting independence-epoch votes after a scheduled reveal.

This module is the executable design fragment. It does not claim a production
council runtime exists on this worktree.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

LEVELS = (
    "named",
    "pseudonymous",
    "fully_blind",
    "blind_then_revealed",
)

POPULATION = (
    "seat-alice",
    "seat-bob",
    "seat-carol",
    "seat-drew",
    "seat-erin",
)

# Derangement of 5 seats (5-cycle). Position=roster hypothesis scores 0.
SHUFFLE = (1, 2, 3, 4, 0)

SALT_R1 = b"cnl-0007-round-1-salt-not-in-publishable"
SALT_R2 = b"cnl-0007-round-2-salt-not-in-publishable"

LEAK_REAL_ID = "real_id_in_publishable"
LEAK_BINDER = "binder_embedded_in_publishable"
LEAK_CROSS_ROUND = "cross_round_token_reuse"
LEAK_ORDER = "roster_order_preserved"
LEAK_REWRITE = "independence_epoch_rewritten"
LEAK_ACTOR_WHEN_BLIND = "actor_present_under_blind"
LEAK_NAMED_UNATTRIBUTED = "named_vote_unattributed"

CHOICES = ("approve", "approve", "reject", "approve", "reject")


def mint_token(real_id: str, round_id: str, salt: bytes) -> str:
    digest = hmac.new(
        salt, f"{round_id}|{real_id}".encode("utf-8"), hashlib.sha256
    ).hexdigest()[:10]
    return f"{round_id}-{digest}"


def mint_ballot(real_id: str, round_id: str, salt: bytes, nonce: str) -> str:
    digest = hmac.new(
        salt,
        f"ballot|{round_id}|{real_id}|{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:12]
    return f"b-{digest}"


def _order(ids: tuple[str, ...], shuffled: bool) -> list[str]:
    if not shuffled:
        return list(ids)
    return [ids[i] for i in SHUFFLE]


def _actor_for(level: str, real_id: str, round_id: str, salt: bytes) -> str | None:
    if level == "named":
        return real_id
    if level == "pseudonymous":
        return mint_token(real_id, round_id, salt)
    return None


def _statement(real_id: str, round_id: str, leak_name: bool) -> str:
    if leak_name:
        return (
            f"Round {round_id} dissent from {real_id}: the claim is under-sourced."
        )
    return (
        f"Round {round_id} dissent: the claim is under-sourced and needs a second "
        "measurement before it can carry a verdict."
    )


def build_round(
    level: str,
    round_id: str,
    salt: bytes,
    *,
    shuffled: bool,
    leak_name: bool,
    epoch: str,
) -> dict[str, Any]:
    order = _order(POPULATION, shuffled)
    transcript = []
    votes = []
    dissent = []
    binder = []
    for i, real_id in enumerate(order):
        actor = _actor_for(level, real_id, round_id, salt)
        ballot = mint_ballot(real_id, round_id, salt, nonce=str(i))
        body = _statement(real_id, round_id, leak_name)
        transcript.append(
            {
                "seq": i,
                "actor": actor,
                "text": body if leak_name else f"Position note {i} for round {round_id}.",
            }
        )
        votes.append(
            {
                "ballot_id": ballot,
                "actor": actor,
                "choice": CHOICES[POPULATION.index(real_id)],
            }
        )
        dissent.append(
            {
                "statement_id": f"s-{round_id}-{i}",
                "actor": actor,
                "body": body,
            }
        )
        binder.append(
            {
                "real_id": real_id,
                "actor": actor,
                "ballot_id": ballot,
                "round_id": round_id,
            }
        )
    return {
        "round_id": round_id,
        "transcript": transcript,
        "votes": votes,
        "dissent": dissent,
        "binder": binder,
        "epoch": epoch,
    }


def _publishable_from_round(rnd: dict[str, Any]) -> dict[str, Any]:
    return {
        "round_id": rnd["round_id"],
        "epoch": rnd["epoch"],
        "transcript": rnd["transcript"],
        "votes": rnd["votes"],
        "dissent": rnd["dissent"],
    }


def build_fixture(kind: str) -> dict[str, Any]:
    """Named fixtures used by both probes.

    kind:
      good-named
      good-pseudonymous
      good-fully-blind
      good-blind-then-revealed
      bad-name-in-dissent
      bad-binder-embedded
      bad-unshuffled-order
      bad-cross-round-token
      bad-independence-rewrite
    """
    if kind == "good-named":
        r1 = build_round(
            "named", "R1", SALT_R1, shuffled=False, leak_name=False, epoch="open"
        )
        return _bundle(
            kind,
            "named",
            "open",
            "participant_facing",
            [r1],
            include_binder=False,
            rewrite=False,
        )
    if kind == "good-pseudonymous":
        r1 = build_round(
            "pseudonymous",
            "R1",
            SALT_R1,
            shuffled=True,
            leak_name=False,
            epoch="independence",
        )
        r2 = build_round(
            "pseudonymous",
            "R2",
            SALT_R2,
            shuffled=True,
            leak_name=False,
            epoch="independence",
        )
        return _bundle(
            kind,
            "pseudonymous",
            "independence",
            "participant_facing",
            [r1, r2],
            include_binder=False,
            rewrite=False,
        )
    if kind == "good-fully-blind":
        r1 = build_round(
            "fully_blind",
            "R1",
            SALT_R1,
            shuffled=True,
            leak_name=False,
            epoch="independence",
        )
        return _bundle(
            kind,
            "fully_blind",
            "independence",
            "participant_facing",
            [r1],
            include_binder=False,
            rewrite=False,
        )
    if kind == "good-blind-then-revealed":
        r1 = build_round(
            "fully_blind",
            "R1",
            SALT_R1,
            shuffled=True,
            leak_name=False,
            epoch="independence",
        )
        reveal = {
            "type": "anonymity_reveal",
            "opens_after": {
                "round_id": "R1",
                "last_independent_act": "vote",
            },
            "join_table": [
                {"ballot_id": row["ballot_id"], "real_id": row["real_id"]}
                for row in r1["binder"]
            ],
            "does_not_rewrite_historical_actors": True,
        }
        bundle = _bundle(
            kind,
            "blind_then_revealed",
            "revealed",
            "participant_facing",
            [r1],
            include_binder=False,
            rewrite=False,
        )
        bundle["reveal_event"] = reveal
        return bundle
    if kind == "bad-name-in-dissent":
        r1 = build_round(
            "pseudonymous",
            "R1",
            SALT_R1,
            shuffled=True,
            leak_name=True,
            epoch="independence",
        )
        return _bundle(
            kind,
            "pseudonymous",
            "independence",
            "participant_facing",
            [r1],
            include_binder=False,
            rewrite=False,
        )
    if kind == "bad-binder-embedded":
        r1 = build_round(
            "pseudonymous",
            "R1",
            SALT_R1,
            shuffled=True,
            leak_name=False,
            epoch="independence",
        )
        return _bundle(
            kind,
            "pseudonymous",
            "independence",
            "participant_facing",
            [r1],
            include_binder=True,
            rewrite=False,
        )
    if kind == "bad-unshuffled-order":
        r1 = build_round(
            "pseudonymous",
            "R1",
            SALT_R1,
            shuffled=False,
            leak_name=False,
            epoch="independence",
        )
        return _bundle(
            kind,
            "pseudonymous",
            "independence",
            "participant_facing",
            [r1],
            include_binder=False,
            rewrite=False,
        )
    if kind == "bad-cross-round-token":
        r1 = build_round(
            "pseudonymous",
            "R1",
            SALT_R1,
            shuffled=True,
            leak_name=False,
            epoch="independence",
        )
        r2 = deepcopy(r1)
        r2["round_id"] = "R2"
        for row in r2["transcript"] + r2["votes"] + r2["dissent"]:
            pass
        r2["epoch"] = "independence"
        return _bundle(
            kind,
            "pseudonymous",
            "independence",
            "participant_facing",
            [r1, r2],
            include_binder=False,
            rewrite=False,
        )
    if kind == "bad-independence-rewrite":
        r1 = build_round(
            "fully_blind",
            "R1",
            SALT_R1,
            shuffled=True,
            leak_name=False,
            epoch="independence",
        )
        truth = {row["ballot_id"]: row["real_id"] for row in r1["binder"]}
        for vote in r1["votes"]:
            vote["actor"] = truth[vote["ballot_id"]]
        for row in r1["dissent"]:
            bid = r1["votes"][int(row["statement_id"].split("-")[-1])]["ballot_id"]
            row["actor"] = truth[bid]
        for row in r1["transcript"]:
            bid = r1["votes"][row["seq"]]["ballot_id"]
            row["actor"] = truth[bid]
        bundle = _bundle(
            kind,
            "blind_then_revealed",
            "revealed",
            "participant_facing",
            [r1],
            include_binder=False,
            rewrite=True,
        )
        bundle["reveal_event"] = {
            "type": "anonymity_reveal",
            "opens_after": {"round_id": "R1", "last_independent_act": "vote"},
            "join_table": [
                {"ballot_id": row["ballot_id"], "real_id": row["real_id"]}
                for row in r1["binder"]
            ],
            "does_not_rewrite_historical_actors": False,
        }
        return bundle
    raise KeyError(kind)


def _bundle(
    kind: str,
    level: str,
    epoch: str,
    channel: str,
    rounds: list[dict[str, Any]],
    *,
    include_binder: bool,
    rewrite: bool,
) -> dict[str, Any]:
    publishable_rounds = [_publishable_from_round(r) for r in rounds]
    keeper = []
    for r in rounds:
        keeper.extend(r["binder"])
    bundle: dict[str, Any] = {
        "kind": kind,
        "anonymity_level": level,
        "epoch": epoch,
        "channel": channel,
        "population_ids": list(POPULATION),
        "publishable": {"rounds": publishable_rounds},
        "rewrite_flag": rewrite,
    }
    if include_binder:
        bundle["sealed_binder"] = {"plaintext_map": keeper}
    else:
        bundle["_keeper_only_binder"] = keeper
    return bundle


def iter_publishable_strings(publishable: dict[str, Any]) -> list[str]:
    blobs: list[str] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, str):
            blobs.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(publishable)
    return blobs


def find_real_id_mentions(publishable: dict[str, Any], population: list[str]) -> list[dict[str, str]]:
    hits = []
    for blob in iter_publishable_strings(publishable):
        for pid in population:
            if pid and pid in blob:
                hits.append({"real_id": pid, "where": blob[:160]})
    return hits


def _actors_in_round(rnd: dict[str, Any]) -> list[str | None]:
    return [row.get("actor") for row in rnd.get("transcript") or []]


def check_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Leak checker. FIRES on participant-facing identity leakage.

    Silent on a known-good bundle for the declared level. Named bundles MAY
    contain real ids; that is attribution, not a leak.
    """
    level = bundle["anonymity_level"]
    epoch = bundle.get("epoch") or "independence"
    channel = bundle.get("channel") or "participant_facing"
    population = list(bundle.get("population_ids") or [])
    pub = bundle.get("publishable") or {}
    reasons: list[dict[str, str]] = []

    if channel == "participant_facing":
        binder = bundle.get("sealed_binder")
        if isinstance(binder, dict) and binder.get("plaintext_map"):
            reasons.append(
                {
                    "code": LEAK_BINDER,
                    "detail": "plaintext binder shipped on the participant-facing channel",
                }
            )

    mentions = find_real_id_mentions(pub, population)
    if level != "named" and mentions:
        # A scheduled reveal join table is allowed beside independence rounds,
        # but not inside publishable round bodies.
        reasons.append(
            {
                "code": LEAK_REAL_ID,
                "detail": f"{len(mentions)} real-id substring(s) in publishable log",
            }
        )

    rounds = list((pub.get("rounds") or []))
    token_to_rounds: dict[str, set[str]] = {}
    for rnd in rounds:
        rid = str(rnd.get("round_id") or "")
        for actor in _actors_in_round(rnd):
            if isinstance(actor, str) and actor:
                token_to_rounds.setdefault(actor, set()).add(rid)
    reused = {t: sorted(rs) for t, rs in token_to_rounds.items() if len(rs) > 1}
    if level == "pseudonymous" and reused:
        reasons.append(
            {
                "code": LEAK_CROSS_ROUND,
                "detail": f"{len(reused)} handle(s) reused across rounds",
            }
        )

    if level == "pseudonymous":
        for rnd in rounds:
            actors = [a for a in _actors_in_round(rnd) if isinstance(a, str)]
            expected = [
                mint_token(pid, str(rnd.get("round_id")), SALT_R1 if rnd.get("round_id") == "R1" else SALT_R2)
                for pid in POPULATION
            ]
            # Roster-order leak: emitted handle sequence equals mint(roster order).
            # The checker is the test oracle; a live runtime would compare against
            # the unpublished roster order held by the keeper, not the salt.
            if actors == expected:
                reasons.append(
                    {
                        "code": LEAK_ORDER,
                        "detail": f"round {rnd.get('round_id')} emission order equals roster order",
                    }
                )

    if level in {"fully_blind", "blind_then_revealed"}:
        independence_rounds = [
            rnd
            for rnd in rounds
            if str(rnd.get("epoch") or epoch) == "independence"
        ]
        for rnd in independence_rounds:
            actors = [a for a in _actors_in_round(rnd) if a]
            vote_actors = [v.get("actor") for v in rnd.get("votes") or [] if v.get("actor")]
            if actors or vote_actors:
                reasons.append(
                    {
                        "code": LEAK_ACTOR_WHEN_BLIND,
                        "detail": f"independence round {rnd.get('round_id')} carries actor handles",
                    }
                )

    if level == "blind_then_revealed" and bundle.get("rewrite_flag"):
        reasons.append(
            {
                "code": LEAK_REWRITE,
                "detail": "independence-epoch actors were rewritten after reveal",
            }
        )
    if level == "blind_then_revealed":
        reveal = bundle.get("reveal_event") or {}
        if reveal.get("does_not_rewrite_historical_actors") is False:
            if not any(r["code"] == LEAK_REWRITE for r in reasons):
                reasons.append(
                    {
                        "code": LEAK_REWRITE,
                        "detail": "reveal_event.does_not_rewrite_historical_actors is false",
                    }
                )

    if level == "named":
        for rnd in rounds:
            missing = [v for v in rnd.get("votes") or [] if not v.get("actor")]
            if missing:
                reasons.append(
                    {
                        "code": LEAK_NAMED_UNATTRIBUTED,
                        "detail": f"{len(missing)} named-level vote(s) lack an actor",
                    }
                )

    fired = bool(reasons)
    return {
        "fired": fired,
        "silent": not fired,
        "level": level,
        "kind": bundle.get("kind"),
        "reasons": reasons,
        "mention_count": len(mentions),
    }


def _truth_map(bundle: dict[str, Any]) -> dict[str, str]:
    """Handle-or-ballot -> real_id. Keeper only; withheld from the adversary."""
    keeper = bundle.get("_keeper_only_binder")
    if keeper is None:
        binder = bundle.get("sealed_binder") or {}
        keeper = binder.get("plaintext_map") or []
    out: dict[str, str] = {}
    for row in keeper:
        rid = row["real_id"]
        if row.get("actor"):
            out[str(row["actor"])] = rid
        if row.get("ballot_id"):
            out[str(row["ballot_id"])] = rid
    return out


def attack_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """De-anonymisation attempt.

    Adversary inputs: publishable transcript + vote history + invite-list
    population. Adversary is withheld: salts, keeper binder (unless leaked
    onto the participant-facing channel).
    """
    population = list(bundle.get("population_ids") or [])
    pub = bundle.get("publishable") or {}
    truth = _truth_map(bundle)
    n = len(population) or 1
    chance = 1.0 / n

    mention_map: dict[str, str] = {}
    for rnd in pub.get("rounds") or []:
        for row in list(rnd.get("dissent") or []) + list(rnd.get("transcript") or []):
            body = str(row.get("body") or row.get("text") or "")
            actor = row.get("actor")
            for pid in population:
                if pid in body:
                    key = str(actor or row.get("statement_id") or body[:40])
                    mention_map[key] = pid

    binder_map: dict[str, str] = {}
    binder = bundle.get("sealed_binder") or {}
    for row in binder.get("plaintext_map") or []:
        if row.get("actor"):
            binder_map[str(row["actor"])] = row["real_id"]
        if row.get("ballot_id"):
            binder_map[str(row["ballot_id"])] = row["real_id"]

    position_maps = []
    position_perfect = []
    for rnd in pub.get("rounds") or []:
        actors = [a for a in _actors_in_round(rnd) if isinstance(a, str) and a]
        if len(actors) != len(population):
            continue
        guessed = {actors[i]: population[i] for i in range(len(actors))}
        correct = sum(1 for a, g in guessed.items() if truth.get(a) == g)
        acc = correct / len(actors)
        position_maps.append({"round_id": rnd.get("round_id"), "accuracy": acc, "guessed": guessed})
        position_perfect.append(acc == 1.0)

    confident: dict[str, str] = {}
    confident.update(mention_map)
    confident.update(binder_map)
    if position_perfect and all(position_perfect) and position_maps:
        for row in position_maps:
            confident.update(row["guessed"])

    scored_keys = [k for k in confident if k in truth]
    if scored_keys:
        correct = sum(1 for k in scored_keys if confident[k] == truth[k])
        confident_accuracy = correct / len(scored_keys)
    else:
        confident_accuracy = 0.0

    # Forced position hypothesis on first round with handles (may be unconfident).
    forced_accuracy = 0.0
    if position_maps:
        forced_accuracy = position_maps[0]["accuracy"]

    supports_anonymity = len(confident) == 0
    return {
        "population_n": n,
        "chance_baseline": chance,
        "mention_joins": mention_map,
        "binder_joins": binder_map,
        "position_maps": [
            {"round_id": r["round_id"], "accuracy": r["accuracy"]} for r in position_maps
        ],
        "confident_join_count": len(confident),
        "confident_accuracy": confident_accuracy,
        "forced_position_accuracy": forced_accuracy,
        "supports_anonymity": supports_anonymity,
        "adversary_inputs": [
            "publishable.rounds.*.transcript",
            "publishable.rounds.*.votes",
            "publishable.rounds.*.dissent",
            "population_ids",
        ],
        "adversary_withheld": ["round salts", "keeper binder unless embedded"],
    }


def dump_fixtures() -> dict[str, str]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    written = {}
    for kind in (
        "good-named",
        "good-pseudonymous",
        "good-fully-blind",
        "good-blind-then-revealed",
        "bad-name-in-dissent",
        "bad-binder-embedded",
        "bad-unshuffled-order",
        "bad-cross-round-token",
        "bad-independence-rewrite",
    ):
        doc = build_fixture(kind)
        path = FIXTURES / f"{kind}.json"
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written[kind] = path.relative_to(HERE).as_posix()
    return written


def both_states() -> dict[str, Any]:
    """Checker discrimination table used by probe2 and the design artifact."""
    cases = [
        ("good-named", False),
        ("good-pseudonymous", False),
        ("good-fully-blind", False),
        ("good-blind-then-revealed", False),
        ("bad-name-in-dissent", True),
        ("bad-binder-embedded", True),
        ("bad-unshuffled-order", True),
        ("bad-cross-round-token", True),
        ("bad-independence-rewrite", True),
    ]
    rows = []
    for kind, want_fire in cases:
        got = check_bundle(build_fixture(kind))
        rows.append(
            {
                "kind": kind,
                "want_fire": want_fire,
                "fired": got["fired"],
                "silent": got["silent"],
                "ok": got["fired"] is want_fire,
                "reasons": [r["code"] for r in got["reasons"]],
            }
        )
    return {
        "rows": rows,
        "fired_on_every_bad": all(r["ok"] for r in rows if r["want_fire"]),
        "silent_on_every_good": all(r["ok"] for r in rows if not r["want_fire"]),
        "pass": all(r["ok"] for r in rows),
    }


def deanonymisation_states() -> dict[str, Any]:
    good = attack_bundle(build_fixture("good-pseudonymous"))
    bad_name = attack_bundle(build_fixture("bad-name-in-dissent"))
    bad_binder = attack_bundle(build_fixture("bad-binder-embedded"))
    bad_order = attack_bundle(build_fixture("bad-unshuffled-order"))
    return {
        "good_pseudonymous": good,
        "bad_name_in_dissent": bad_name,
        "bad_binder_embedded": bad_binder,
        "bad_unshuffled_order": bad_order,
        "pass": (
            good["supports_anonymity"] is True
            and good["confident_join_count"] == 0
            and bad_name["supports_anonymity"] is False
            and bad_name["confident_join_count"] >= 1
            and bad_binder["supports_anonymity"] is False
            and bad_binder["confident_join_count"] >= 1
            and bad_order["supports_anonymity"] is False
            and bad_order["forced_position_accuracy"] == 1.0
        ),
    }
