"""Dominance and silence detector."""
from __future__ import annotations

from typing import Any

DOMINANCE_MULTIPLE = 2
SILENCE_MULTIPLE = 0.25


def flag_dominance(share: float, n: int) -> bool:
    return share > (DOMINANCE_MULTIPLE / n)


def flag_silence(share: float, n: int, turns: int | None = None) -> bool:
    if turns == 0:
        return True
    return share < (SILENCE_MULTIPLE / n)


def split_sentences(text: str) -> list[str]:
    out = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in ".!?":
            s = buf.strip()
            if s:
                out.append(s)
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


_FILLER_STOPWORDS = frozenset(
    """
    i you we they he she it this that these those a an the and or but
    is are was were be been being am do does did done have has had
    noted agree agreed with sounds good to me no objection at all likewise
    happy proceed please continue yes okay ok acknowledged seconded keep going
    as previously said concur add nothing have not it
    um uh yeah sure right hmm well thanks thank there here
    """.split()
)


def is_filler_sentence(text: str) -> bool:
    """A sentence is filler when no content word survives the stopword lexicon.

    Planted agreement volume ("Noted. I agree with that. No objection.") is
    filler; substantive contributions carry content words (claim/evidence/
    quota/kernel/...) that survive.
    """
    t = text.strip().lower()
    if not t:
        return True
    words = [w.strip(".,!?;:()") for w in t.split()]
    content = [w for w in words if w and w not in _FILLER_STOPWORDS]
    return not content


def substance_units(text: str) -> int:
    return sum(1 for s in split_sentences(text) if not is_filler_sentence(s))


def excerpts_for(
    council: dict[str, Any],
    seat_names: list[str] | None = None,
    limit: int | None = 4,
) -> dict[str, list[str]] | str:
    """Seat excerpts as {seat: [turn texts]}.

    probes/IMP-0321 contract: excerpts_for(council, [names], limit=4).
    Legacy single-seat form (one dict without council keys) still returns
    the joined text.
    """
    if (
        seat_names is None
        and isinstance(council, dict)
        and "turns" not in council
        and "seats" not in council
    ):
        turns = council.get("turns") or []
        if isinstance(turns, list):
            return " ".join(
                str(t.get("text") if isinstance(t, dict) else t) for t in turns
            )
        return str(council.get("text") or "")

    seats_in = council.get("seats")
    if seats_in:
        texts = {
            name: [
                str(t.get("text") if isinstance(t, dict) else t)
                for t in (rec.get("turns") or [])
            ]
            for name, rec in seats_in.items()
        }
    else:
        texts = {}
        for turn in council.get("turns") or []:
            name = str((turn or {}).get("seat") or "")
            texts.setdefault(name, []).append(str((turn or {}).get("text") or ""))
    if seat_names is None:
        return {k: v[:limit] if limit else v for k, v in texts.items()}
    return {name: texts.get(name, [])[:limit] if limit else texts.get(name, []) for name in seat_names}


def analyze_council(council: dict[str, Any]) -> dict[str, Any]:
    turns_list = council.get("turns")
    if isinstance(turns_list, list) and turns_list:
        # Transcript format: {"participants": [...], "turns": [{"seat": .., "text": ..}]}
        seats_in: dict[str, dict[str, Any]] = {}
        for turn in turns_list:
            if not isinstance(turn, dict):
                continue
            name = str(turn.get("seat") or turn.get("participant") or "").strip()
            if not name:
                continue
            entry = seats_in.setdefault(name, {"turns": []})
            entry["turns"].append({"text": str(turn.get("text") or "")})
        for name in council.get("participants") or []:
            # Zero-turn seats (planted silent critic) must exist and be silent.
            seats_in.setdefault(str(name), {"turns": []})
        if seats_in:
            council = dict(council)
            council["seats"] = seats_in
    seats_in = council.get("seats") or council
    parsed: dict[str, dict[str, Any]] = {}
    vol = {}
    sub = {}
    for name, seat in seats_in.items():
        if not isinstance(seat, dict):
            continue
        turns = seat.get("turns") or []
        if turns and isinstance(turns[0], dict):
            texts = [str(t.get("text") or "") for t in turns]
        elif turns:
            texts = [str(t) for t in turns]
        else:
            texts = [str(seat.get("text") or "")]
        n_turns = len(turns) if turns else (1 if texts and texts[0] else 0)
        volume = sum(len(t) for t in texts) or n_turns
        subst = sum(substance_units(t) for t in texts)
        parsed[name] = {"turns": n_turns, "volume": volume, "substance": subst, "text": " ".join(texts)}
        vol[name] = volume
        sub[name] = subst
    n = max(1, len(parsed))
    total_v = sum(vol.values()) or 1
    total_s = sum(sub.values()) or 1
    seats = {}
    volume_dominant = []
    substance_dominant = []
    volume_silent = []
    substance_silent = []
    for name, rec in parsed.items():
        vshare = rec["volume"] / total_v
        sshare = rec["substance"] / total_s
        seats[name] = {
            "volume_share": vshare,
            "substance_share": sshare,
            "turns": rec["turns"],
        }
        if flag_dominance(vshare, n):
            volume_dominant.append(name)
        if flag_dominance(sshare, n):
            substance_dominant.append(name)
        if flag_silence(vshare, n, turns=rec["turns"]):
            volume_silent.append(name)
        if flag_silence(sshare, n, turns=rec["turns"]):
            substance_silent.append(name)
    even = not (volume_dominant or substance_dominant or volume_silent or substance_silent)
    volume_loudest = max(seats, key=lambda s: seats[s]["volume_share"]) if seats else None
    substance_loudest = (
        max(seats, key=lambda s: seats[s]["substance_share"]) if seats else None
    )
    return {
        "council_id": council.get("council_id"),
        "label": council.get("label"),
        "seats": seats,
        "volume_dominant": volume_dominant,
        "substance_dominant": substance_dominant,
        "volume_silent": volume_silent,
        "substance_silent": substance_silent,
        "flagged_volume": bool(volume_dominant or volume_silent),
        "flagged_substance": bool(substance_dominant or substance_silent),
        "measures_disagree": (set(volume_dominant) != set(substance_dominant)) or (set(volume_silent) != set(substance_silent)),
        "dominance_threshold": DOMINANCE_MULTIPLE / n,
        "silence_threshold": SILENCE_MULTIPLE / n,
        "disagreement": {
            "volume_loudest": volume_loudest,
            "substance_loudest": substance_loudest,
        },
        "even": even,
        "n": n,
    }


def analyze_many(councils: list[dict[str, Any]]) -> dict[str, Any]:
    """Census aggregate over recorded councils (probes/IMP-0321 contract)."""
    rows = [analyze_council(c) for c in councils]
    disagreements = [r for r in rows if r["measures_disagree"]]

    def _margin(row: dict[str, Any]) -> float:
        d = row["disagreement"]
        vol, sub = d["volume_loudest"], d["substance_loudest"]
        if not vol or not sub or vol == sub:
            return -1.0
        seat_rows = row["seats"]
        share_gap = seat_rows[vol]["volume_share"] - seat_rows[sub]["volume_share"]
        substance_gap = (
            seat_rows[sub]["substance_share"] - seat_rows[vol]["substance_share"]
        )
        return float(share_gap + substance_gap)

    top = None
    for row in sorted(disagreements, key=_margin, reverse=True):
        d = row["disagreement"]
        if d["volume_loudest"] and d["substance_loudest"] and d["volume_loudest"] != d["substance_loudest"]:
            top = {
                "council_id": row["council_id"],
                "volume_loudest": d["volume_loudest"],
                "substance_loudest": d["substance_loudest"],
                "gap": _margin(row),
            }
            break
    return {
        "n_councils": len(rows),
        "n_disagreements": len(disagreements),
        "disagreement_ids": [r["council_id"] for r in disagreements],
        "rows": rows,
        "top_disagreement": top,
    }
