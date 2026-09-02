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


def is_filler_sentence(text: str) -> bool:
    t = text.strip().lower()
    if not t:
        return True
    fillers = ("um", "uh", "yeah", "ok", "okay", "right", "sure", "hmm")
    words = [w.strip(".,!?") for w in t.split()]
    if not words:
        return True
    return all(w in fillers for w in words) or len(words) <= 1


def substance_units(text: str) -> int:
    return sum(1 for s in split_sentences(text) if not is_filler_sentence(s))


def excerpts_for(seat: dict[str, Any]) -> str:
    turns = seat.get("turns") or []
    if isinstance(turns, list):
        return " ".join(str(t.get("text") if isinstance(t, dict) else t) for t in turns)
    return str(seat.get("text") or "")


def analyze_council(council: dict[str, Any]) -> dict[str, Any]:
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
    return {
        "seats": seats,
        "volume_dominant": volume_dominant,
        "substance_dominant": substance_dominant,
        "volume_silent": volume_silent,
        "substance_silent": substance_silent,
        "flagged_volume": bool(volume_dominant or volume_silent),
        "flagged_substance": bool(substance_dominant or substance_silent),
        "measures_disagree": set(volume_dominant) != set(substance_dominant),
        "even": even,
        "n": n,
    }


def analyze_many(councils: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [analyze_council(c) for c in councils]
