"""Dominance and silence detector (IMP-0321).

Two mechanically different participation measures are computed side by side
over a recorded council transcript:

* **volume** - whitespace tokens a seat spoke (airtime);
* **substance** - surviving claims a seat carried (``claims`` recorded on each
  turn; when a turn carries no ``claims`` field, claim-bearing sentences are
  counted instead, with acknowledgement filler discounted).

Dominance fires when a seat's share is strictly above ``DOMINANCE_MULTIPLE / n``
(twice its fair share); silence fires when a seat has no turns at all or its
share is below ``SILENCE_MULTIPLE / n`` (a quarter of its fair share).  The two
measures are reported separately so that a filler-padded chair (loud, empty)
and a terse claim-bearing seat (quiet, substantive) are told apart; when the
measures disagree that disagreement is itself a published finding.

Accepted council shapes:

* transcript ``{"council_id", "label", "participants": [seat, ...],
  "turns": [{"seat", "text", "claims": [...], ...}, ...]}``;
* seat map ``{"seats": {name: {"turns": [...] | "text": str}}}`` or a bare
  ``{name: {...}}`` mapping of seat records.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

DOMINANCE_MULTIPLE = 2
SILENCE_MULTIPLE = 0.25

# Single-word acknowledgements: a sentence made only of these carries no claim.
FILLER_WORDS = frozenset(
    {
        "um", "uh", "yeah", "ok", "okay", "right", "sure", "hmm", "yes", "no",
        "noted", "likewise", "acknowledged", "seconded", "agreed", "indeed",
        "fine", "understood", "absolutely", "exactly", "correct", "great", "good",
        "mm", "mhm", "yep", "yup", "nope", "true", "same", "ditto",
    }
)
# Multi-word acknowledgement phrases, normalised (lower-case, punctuation gone).
FILLER_PHRASES = frozenset(
    {
        "i agree", "i agree with that", "agree with that", "i agree with the above",
        "sounds good", "sounds good to me", "that sounds good", "that sounds right",
        "sounds right", "no objection", "no objection at all", "no objections",
        "happy to proceed", "i have nothing to add", "nothing to add", "nothing further",
        "please continue", "as previously said", "as said before", "as i said",
        "i concur", "keep going", "go ahead", "makes sense", "that makes sense",
        "me too", "same here", "no further comment", "carry on", "i second that",
        "fully agree", "moving on", "let us proceed", "lets proceed", "will do",
        "got it", "thank you", "thanks", "of course", "very well", "all good",
    }
)

_WORD_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")


def flag_dominance(share: float, n: int) -> bool:
    """A seat dominates when its share is strictly above ``DOMINANCE_MULTIPLE / n``."""
    return float(share) > (DOMINANCE_MULTIPLE / max(1, int(n)))


def flag_silence(share: float, n: int, turns: int | None = None) -> bool:
    """A seat is silent with zero turns, or with a share below ``SILENCE_MULTIPLE / n``."""
    if turns is not None and int(turns) == 0:
        return True
    return float(share) < (SILENCE_MULTIPLE / max(1, int(n)))


def dominance_threshold(n: int) -> float:
    """Share above which a seat of an ``n``-seat council dominates."""
    return DOMINANCE_MULTIPLE / max(1, int(n))


def silence_threshold(n: int) -> float:
    """Share below which a seat of an ``n``-seat council is silent."""
    return SILENCE_MULTIPLE / max(1, int(n))


def split_sentences(text: str) -> list[str]:
    """Split ``text`` on sentence terminators, keeping the terminator on each piece."""
    out: list[str] = []
    buf = ""
    for ch in str(text):
        buf += ch
        if ch in ".!?":
            piece = buf.strip()
            if piece:
                out.append(piece)
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(str(text).lower())


def is_filler_sentence(text: str) -> bool:
    """True when a sentence is an acknowledgement with no claim in it.

    A sentence is filler when it is empty, a single word, made only of
    acknowledgement words (``FILLER_WORDS``), or - once leading/trailing
    acknowledgement words are stripped - one of the ``FILLER_PHRASES``.
    """
    words = _words(text)
    if len(words) <= 1:
        return True
    if all(w in FILLER_WORDS for w in words):
        return True
    phrase = " ".join(words)
    if phrase in FILLER_PHRASES:
        return True
    core = [w for w in words if w not in FILLER_WORDS]
    if not core:
        return True
    return " ".join(core) in FILLER_PHRASES


def substance_units(text: str) -> int:
    """Count claim-bearing (non-filler) sentences in ``text``."""
    return sum(1 for s in split_sentences(text) if not is_filler_sentence(s))


def volume_units(text: str) -> int:
    """Count whitespace tokens (airtime) in ``text``."""
    return len(str(text).split())


def _turn_text(turn: Any) -> str:
    if isinstance(turn, dict):
        return str(turn.get("text") or "")
    return str(turn or "")


def _turn_substance(turn: Any) -> int:
    if isinstance(turn, dict) and "claims" in turn:
        claims = turn.get("claims") or []
        return len(claims) if isinstance(claims, (list, tuple)) else int(bool(claims))
    return substance_units(_turn_text(turn))


def seat_turns(council: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Group a council's turns by seat, in participant order, as ``{"text", "claims"?}`` dicts.

    Participants with no turns are kept with an empty list so silence is visible.
    """
    by_seat: dict[str, list[dict[str, Any]]] = {}
    turns = council.get("turns")
    seats_map = council.get("seats")
    if isinstance(turns, list) and (
        "participants" in council or any(isinstance(t, dict) and "seat" in t for t in turns)
    ):
        for name in council.get("participants") or []:
            by_seat.setdefault(str(name), [])
        for turn in turns:
            if not isinstance(turn, dict):
                continue
            seat = str(turn.get("seat") or turn.get("seat_id") or "")
            if not seat:
                continue
            rec: dict[str, Any] = {"text": _turn_text(turn)}
            if "claims" in turn:
                rec["claims"] = list(turn.get("claims") or [])
            by_seat.setdefault(seat, []).append(rec)
        return by_seat
    source = seats_map if isinstance(seats_map, dict) else council
    for name, seat in source.items():
        if not isinstance(seat, dict):
            continue
        rows: list[dict[str, Any]] = []
        raw_turns = seat.get("turns")
        if isinstance(raw_turns, list):
            for turn in raw_turns:
                rec = {"text": _turn_text(turn)}
                if isinstance(turn, dict) and "claims" in turn:
                    rec["claims"] = list(turn.get("claims") or [])
                rows.append(rec)
        elif seat.get("text"):
            rows.append({"text": str(seat.get("text"))})
        by_seat[str(name)] = rows
    return by_seat


def excerpts_for(
    council: dict[str, Any], seats: Iterable[str] | None = None, limit: int = 4
) -> dict[str, list[str]]:
    """Return up to ``limit`` turn texts per requested seat (all seats when ``seats`` is None)."""
    grouped = seat_turns(council)
    wanted = [str(s) for s in seats] if seats is not None else list(grouped)
    limit = max(0, int(limit))
    return {
        seat: [row["text"] for row in grouped.get(seat, [])][:limit] for seat in wanted
    }


def _loudest(values: dict[str, int]) -> str | None:
    """Seat with the unique maximum; None when everything is zero or the top is tied."""
    if not values:
        return None
    top = max(values.values())
    if top <= 0:
        return None
    winners = [name for name, v in values.items() if v == top]
    return winners[0] if len(winners) == 1 else None


def analyze_council(council: dict[str, Any]) -> dict[str, Any]:
    """Score one council on volume and substance and flag dominance / silence per measure."""
    grouped = seat_turns(council)
    n = max(1, len(grouped))
    vol: dict[str, int] = {}
    sub: dict[str, int] = {}
    turns_by_seat: dict[str, int] = {}
    for name, rows in grouped.items():
        vol[name] = sum(volume_units(r["text"]) for r in rows)
        sub[name] = sum(_turn_substance(r) for r in rows)
        turns_by_seat[name] = len(rows)
    total_v = sum(vol.values()) or 1
    total_s = sum(sub.values()) or 1

    seats: dict[str, dict[str, Any]] = {}
    volume_dominant: list[str] = []
    substance_dominant: list[str] = []
    volume_silent: list[str] = []
    substance_silent: list[str] = []
    for name in grouped:
        vshare = vol[name] / total_v
        sshare = sub[name] / total_s
        seats[name] = {
            "turns": turns_by_seat[name],
            "volume": vol[name],
            "substance": sub[name],
            "volume_share": vshare,
            "substance_share": sshare,
        }
        if flag_dominance(vshare, n):
            volume_dominant.append(name)
        if flag_dominance(sshare, n):
            substance_dominant.append(name)
        if flag_silence(vshare, n, turns=turns_by_seat[name]):
            volume_silent.append(name)
        if flag_silence(sshare, n, turns=turns_by_seat[name]):
            substance_silent.append(name)

    vol_loudest = _loudest(vol)
    sub_loudest = _loudest(sub)
    loudest_differ = (
        vol_loudest is not None and sub_loudest is not None and vol_loudest != sub_loudest
    )
    gap = 0.0
    if loudest_differ:
        gap = round(
            abs(seats[vol_loudest]["volume_share"] - seats[vol_loudest]["substance_share"]), 6
        )
    even = not (volume_dominant or substance_dominant or volume_silent or substance_silent)
    return {
        "council_id": str(council.get("council_id") or council.get("id") or ""),
        "label": str(council.get("label") or ""),
        "n": n,
        "dominance_threshold": dominance_threshold(n),
        "silence_threshold": silence_threshold(n),
        "seats": seats,
        "volume_dominant": volume_dominant,
        "substance_dominant": substance_dominant,
        "volume_silent": volume_silent,
        "substance_silent": substance_silent,
        "flagged_volume": bool(volume_dominant or volume_silent),
        "flagged_substance": bool(substance_dominant or substance_silent),
        "disagreement": {
            "volume_loudest": vol_loudest,
            "substance_loudest": sub_loudest,
            "gap": gap,
        },
        "measures_disagree": bool(
            loudest_differ or set(volume_dominant) != set(substance_dominant)
        ),
        "even": even,
    }


def analyze_many(councils: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Census over recorded councils: per-council rows plus the volume-vs-substance disagreement count.

    ``top_disagreement`` is the disagreeing council whose volume-loudest seat has
    the widest volume-minus-substance share gap (first in corpus order on ties);
    None when no council has distinct loudest seats on the two measures.
    """
    rows = [analyze_council(c) for c in councils]
    disagreeing = [r for r in rows if r["measures_disagree"]]
    top: dict[str, Any] | None = None
    for row in disagreeing:
        dis = row["disagreement"]
        if dis["volume_loudest"] is None or dis["substance_loudest"] is None:
            continue
        if top is None or dis["gap"] > top["gap"]:
            top = {
                "council_id": row["council_id"],
                "gap": dis["gap"],
                "volume_loudest": dis["volume_loudest"],
                "substance_loudest": dis["substance_loudest"],
            }
    return {
        "n_councils": len(rows),
        "rows": rows,
        "n_disagreements": len(disagreeing),
        "disagreement_ids": [r["council_id"] for r in disagreeing],
        "top_disagreement": top,
    }
