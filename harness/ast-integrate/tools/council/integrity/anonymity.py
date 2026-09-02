"""Per-round unlinkable pseudonyms for published council sessions (IMP-0276).

A published session must not let a reader link a participant's turns across
rounds or back to a real identity. Four side channels are treated as linking
signals and are handled explicitly:

* ``order``  — seating order; defeated by a keyed per-round shuffle.
* ``timing`` — ``elapsed_ms``; stripped.
* ``tokens`` — ``token_count``; stripped.
* ``style``  — the free text itself; stripped.

Pseudonyms are ``HMAC(secret, session|round|participant)`` truncated, so a
label never repeats across rounds and cannot be recomputed without the secret.
The module also ships the adversary (``linkage_attack``) and the scorer
(``score_linkage``) so the same code measures how much each channel leaks.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from typing import Any

CHANNELS: tuple[str, ...] = ("order", "timing", "tokens", "style")
PSEUDONYM_HEX = 16
LEVELS = ("pseudonymous", "none")

# Turn fields that carry a linking signal, by channel.
_CHANNEL_FIELDS: dict[str, tuple[str, ...]] = {
    "timing": ("elapsed_ms",),
    "tokens": ("token_count",),
    "style": ("text",),
}
_IDENTITY_FIELDS: tuple[str, ...] = ("participant_id", "display_name")
_CONTENT_FIELDS: tuple[str, ...] = ("vote", "position")


@dataclass(frozen=True)
class AnonymityConfig:
    """What the publisher masks. Every default is the safe (masking) choice."""

    enabled: bool = True
    level: str = "pseudonymous"
    shuffle_order: bool = True
    strip_timing: bool = True
    strip_token_counts: bool = True
    strip_style: bool = True

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ValueError(f"unknown anonymity level {self.level!r}; want one of {LEVELS}")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def secret_from_text(text: str) -> bytes:
    """Derive a 32-byte session secret from a passphrase."""
    return hashlib.sha256(text.encode("utf-8")).digest()


def _mac(secret: bytes, *parts: str) -> str:
    msg = "|".join(parts).encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def pseudonym(secret: bytes, session_id: str, round_id: str, participant_id: str) -> str:
    """Per-round label: changes every round, unrecoverable without the secret."""
    return _mac(secret, "pseudonym", session_id, round_id, participant_id)[:PSEUDONYM_HEX]


def _order_key(secret: bytes, session_id: str, round_id: str, participant_id: str) -> str:
    return _mac(secret, "order", session_id, round_id, participant_id)


def _publish_turn(turn: dict[str, Any], label: str, config: AnonymityConfig) -> dict[str, Any]:
    out: dict[str, Any] = {"pseudonym": label}
    for key in _CONTENT_FIELDS:
        if key in turn:
            out[key] = turn[key]
    if not config.strip_timing and "elapsed_ms" in turn:
        out["elapsed_ms"] = turn["elapsed_ms"]
    if not config.strip_token_counts and "token_count" in turn:
        out["token_count"] = turn["token_count"]
    if not config.strip_style and "text" in turn:
        out["text"] = turn["text"]
    return out


def publish_session(raw: dict[str, Any], secret: bytes, config: AnonymityConfig) -> dict[str, Any]:
    """Return the publishable view of ``raw`` under ``config``.

    With anonymity disabled the turns are copied through untouched (identity
    and all channels kept). Otherwise identities are replaced by per-round
    pseudonyms, the configured channels are dropped and, when
    ``shuffle_order`` is set, each round's turns are re-ordered by a keyed
    hash so seat position carries no cross-round signal.
    """
    session_id = str(raw.get("session_id") or "")
    rounds_out: list[dict[str, Any]] = []
    for rec in raw.get("rounds") or []:
        round_id = str(rec.get("round_id") or "")
        turns = list(rec.get("turns") or [])
        if not config.enabled or config.level == "none":
            rounds_out.append({"round_id": round_id, "turns": [dict(t) for t in turns]})
            continue
        labelled = []
        for t in turns:
            pid = str(t.get("participant_id") or "")
            labelled.append((_order_key(secret, session_id, round_id, pid), _publish_turn(t, pseudonym(secret, session_id, round_id, pid), config)))
        if config.shuffle_order:
            labelled.sort(key=lambda kv: kv[0])
        rounds_out.append({"round_id": round_id, "turns": [t for _, t in labelled]})
    return {
        "session_id": session_id,
        "anonymity": config.as_dict(),
        "rounds": rounds_out,
    }


def _walk_strings(node: Any):
    if isinstance(node, dict):
        for k, v in node.items():
            yield str(k)
            yield from _walk_strings(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            yield from _walk_strings(v)
    elif node is not None:
        yield str(node)


def census_real_ids(published: Any, real_ids: list[str]) -> list[str]:
    """Every real id (or display name) that survives anywhere in ``published``.

    Keys and values are both scanned, as substrings, so an id embedded in free
    text is a hit too. Returns one entry per occurrence.
    """
    hits: list[str] = []
    for s in _walk_strings(published):
        for rid in real_ids:
            if rid and rid in s:
                hits.append(rid)
    return hits


def truth_index_from_raw(
    raw: dict[str, Any],
    published: dict[str, Any],
    *,
    secret: bytes,
    config: AnonymityConfig,
) -> dict[str, Any]:
    """Ground truth for scoring: pseudonym -> real participant, per round.

    Built from the secret (the publisher's side), never from the published
    artifact, so a scorer cannot accidentally read identity out of the output.
    """
    session_id = str(raw.get("session_id") or "")
    by_round: dict[str, dict[str, str]] = {}
    participants: list[str] = []
    for rec in raw.get("rounds") or []:
        round_id = str(rec.get("round_id") or "")
        table: dict[str, str] = {}
        for t in rec.get("turns") or []:
            pid = str(t.get("participant_id") or "")
            if pid not in participants:
                participants.append(pid)
            label = pid if (not config.enabled or config.level == "none") else pseudonym(secret, session_id, round_id, pid)
            table[label] = pid
        by_round[round_id] = table
    return {
        "session_id": session_id,
        "round_ids": [str(r.get("round_id") or "") for r in published.get("rounds") or []],
        "by_round": by_round,
        "participants": participants,
        "n_participants": len(participants),
    }


def _label(turn: dict[str, Any]) -> str:
    return str(turn.get("pseudonym") or turn.get("participant_id") or "")


def _tokens(text: str) -> set[str]:
    return {w.strip(".,;:!?").lower() for w in str(text).split() if w.strip(".,;:!?")}


def channels_present(rounds: list[dict[str, Any]]) -> dict[str, bool]:
    """Which linking channels the published rounds still expose."""
    turns = [t for r in rounds for t in (r.get("turns") or [])]
    present = {ch: any(f in t for t in turns for f in fields) for ch, fields in _CHANNEL_FIELDS.items()}
    present["order"] = len(rounds) > 1 and all(len(r.get("turns") or []) > 0 for r in rounds)
    return present


def _link_one(channel: str, anchor_turns: list[dict[str, Any]], idx: int, turn: dict[str, Any]) -> str | None:
    """Adversary's guess: which anchor-round turn is the same person as ``turn``."""
    if channel == "order":
        return _label(anchor_turns[idx]) if idx < len(anchor_turns) else None
    fields = _CHANNEL_FIELDS[channel]
    key = fields[0]
    if key not in turn:
        return None
    candidates = [a for a in anchor_turns if key in a]
    if not candidates:
        return None
    if channel == "style":
        mine = _tokens(turn[key])
        best = max(
            candidates,
            key=lambda a: (len(mine & _tokens(a[key])) / max(1, len(mine | _tokens(a[key]))), -_label(a) < ""),
        )
        return _label(best)
    value = float(turn[key])
    best = min(candidates, key=lambda a: (abs(float(a[key]) - value), _label(a)))
    return _label(best)


def linkage_attack(rounds: list[dict[str, Any]], channel: str = "order") -> dict[str, Any]:
    """Link every turn in rounds[1:] to a turn of rounds[0] using one channel.

    The attacker sees only the published rounds. ``order`` links by seat
    position, ``timing``/``tokens`` by nearest value, ``style`` by word-set
    overlap. A channel that has been stripped yields no guess (``None``),
    which the scorer counts as a miss.
    """
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel {channel!r}; want one of {CHANNELS}")
    present = channels_present(rounds)
    guesses: list[dict[str, Any]] = []
    if rounds:
        anchor = rounds[0]
        anchor_turns = list(anchor.get("turns") or [])
        for rec in rounds[1:]:
            for idx, turn in enumerate(rec.get("turns") or []):
                guesses.append(
                    {
                        "round_id": str(rec.get("round_id") or ""),
                        "pseudonym": _label(turn),
                        "anchor_round_id": str(anchor.get("round_id") or ""),
                        "linked_to": _link_one(channel, anchor_turns, idx, turn),
                    }
                )
    return {
        "channel": channel,
        "channels_present": present,
        "n_rounds": len(rounds),
        "n_guesses": len(guesses),
        "guesses": guesses,
    }


def score_linkage(attack: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    """Fraction of the attacker's links that name the right person."""
    by_round: dict[str, dict[str, str]] = truth.get("by_round") or {}
    correct = 0
    scored = 0
    for g in attack.get("guesses") or []:
        scored += 1
        linked = g.get("linked_to")
        if linked is None:
            continue
        who = by_round.get(g["round_id"], {}).get(g["pseudonym"])
        anchor = by_round.get(g["anchor_round_id"], {}).get(linked)
        if who is not None and who == anchor:
            correct += 1
    n_participants = int(truth.get("n_participants") or 0)
    return {
        "channel": attack.get("channel"),
        "n": scored,
        "correct": correct,
        "accuracy": (correct / scored) if scored else 0.0,
        "chance": (1.0 / n_participants) if n_participants else None,
    }


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2)


__all__ = [
    "AnonymityConfig",
    "CHANNELS",
    "census_real_ids",
    "channels_present",
    "linkage_attack",
    "pseudonym",
    "publish_session",
    "score_linkage",
    "secret_from_text",
    "truth_index_from_raw",
]
