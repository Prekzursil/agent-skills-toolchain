"""Circular-debate detector: per-round information gain.

Information units in round t:
    G_t = |new claims| + |new evidence nodes|

A claim is new only if its claim_id is unseen AND its text is not a
duplicate of a prior claim (token Jaccard >= 0.85 OR char-4gram Jaccard
>= 0.35). Evidence is new iff its evidence_id is unseen.

The debate is circling when G_t < FLOOR for WINDOW consecutive rounds.

Vote motion and position entropy are diagnostic traces. They do not
enter G_t: two camps swapping slogans can twitch votes without adding
information. Entropy collapse without new claims or evidence is
premature-convergence (IMP-0323), not this detector's sole trigger;
copy-paste agreement with G_t = 0 still fires here because nothing new
was said.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from canonicalize import is_duplicate_text

FLOOR = 1
WINDOW = 2
HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def shannon(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    h = 0.0
    for n in counts.values():
        if n <= 0:
            continue
        p = n / total
        h -= p * math.log2(p)
    return h


def _utterances(round_doc: dict) -> list[dict]:
    rows = round_doc.get("utterances") or []
    if not isinstance(rows, list):
        return []
    return [u for u in rows if isinstance(u, dict)]


def round_gain(
    round_doc: dict,
    prior_claim_ids: set[str],
    prior_evidence_ids: set[str],
    prior_texts: list[str],
    prior_positions: dict[str, str],
) -> dict:
    new_claim_ids: list[str] = []
    duplicate_claim_ids: list[str] = []
    new_evidence_ids: list[str] = []
    seen_claim_this = set()
    seen_ev_this = set()
    seen_texts = list(prior_texts)
    positions: dict[str, int] = {}
    vote_changes = 0
    seats_seen = 0
    dup_scores: list[dict] = []

    for u in _utterances(round_doc):
        seat = str(u.get("seat") or "")
        cid = str(u.get("claim_id") or "")
        text = str(u.get("claim_text") or "")
        pos = str(u.get("position_id") or "")
        if pos:
            positions[pos] = positions.get(pos, 0) + 1
        if seat:
            seats_seen += 1
            prev = prior_positions.get(seat)
            if prev is not None and prev != pos:
                vote_changes += 1
        if cid and cid not in prior_claim_ids and cid not in seen_claim_this:
            score = is_duplicate_text(text, seen_texts)
            dup_scores.append({"claim_id": cid, **score})
            if score["duplicate"]:
                duplicate_claim_ids.append(cid)
            else:
                new_claim_ids.append(cid)
                if text:
                    seen_texts.append(text)
            seen_claim_this.add(cid)
        elif cid:
            if cid in prior_claim_ids or cid in seen_claim_this:
                duplicate_claim_ids.append(cid)
        for eid in u.get("evidence_ids") or []:
            eid_s = str(eid)
            if not eid_s or eid_s in seen_ev_this:
                continue
            seen_ev_this.add(eid_s)
            if eid_s not in prior_evidence_ids:
                new_evidence_ids.append(eid_s)

    units = len(new_claim_ids) + len(new_evidence_ids)
    entropy = shannon(positions)
    return {
        "round": int(round_doc.get("round") or 0),
        "new_claim_ids": new_claim_ids,
        "duplicate_claim_ids": duplicate_claim_ids,
        "new_evidence_ids": new_evidence_ids,
        "information_units": units,
        "subfloor": units < FLOOR,
        "vote_changes": vote_changes,
        "seats": seats_seen,
        "entropy_bits": round(entropy, 4),
        "position_ids": sorted(positions),
        "duplicate_scores": dup_scores,
        "next_claim_ids": set(prior_claim_ids) | seen_claim_this,
        "next_evidence_ids": set(prior_evidence_ids) | seen_ev_this,
        "next_texts": seen_texts,
        "next_positions": {
            **prior_positions,
            **{
                str(u.get("seat") or ""): str(u.get("position_id") or "")
                for u in _utterances(round_doc)
                if u.get("seat")
            },
        },
    }


def detect(doc: dict) -> dict:
    rounds = doc.get("rounds") or []
    prior_claim_ids: set[str] = set()
    prior_evidence_ids: set[str] = set()
    prior_texts: list[str] = []
    prior_positions: dict[str, str] = {}
    curve: list[dict] = []
    consecutive = 0
    fired_at = None
    for rnd in rounds:
        g = round_gain(
            rnd,
            prior_claim_ids,
            prior_evidence_ids,
            prior_texts,
            prior_positions,
        )
        prior_claim_ids = g.pop("next_claim_ids")
        prior_evidence_ids = g.pop("next_evidence_ids")
        prior_texts = g.pop("next_texts")
        prior_positions = g.pop("next_positions")
        if g["subfloor"]:
            consecutive += 1
            if consecutive >= WINDOW and fired_at is None:
                fired_at = g["round"]
        else:
            consecutive = 0
        g["consecutive_subfloor"] = consecutive
        curve.append(g)

    fired = fired_at is not None
    return {
        "fixture_id": doc.get("id"),
        "expected": doc.get("expected"),
        "fired": fired,
        "silent": not fired,
        "fired_at_round": fired_at,
        "floor": FLOOR,
        "window": WINDOW,
        "information_units": "new_claims + new_evidence",
        "gain_curve": curve,
        "rounds": len(curve),
    }


def detect_path(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    result = detect(doc)
    result["path"] = str(path)
    return result


def id_set_gain(doc: dict) -> dict:
    """Mechanically different signal: claim_id / evidence_id set difference only.

    Ignores claim text. A paraphrase that mints new ids looks like gain.
    """
    prior_c: set[str] = set()
    prior_e: set[str] = set()
    curve = []
    consecutive = 0
    fired_at = None
    for rnd in doc.get("rounds") or []:
        c_now: set[str] = set()
        e_now: set[str] = set()
        for u in _utterances(rnd):
            cid = str(u.get("claim_id") or "")
            if cid:
                c_now.add(cid)
            for eid in u.get("evidence_ids") or []:
                e_now.add(str(eid))
        new_c = sorted(c_now - prior_c)
        new_e = sorted(e_now - prior_e)
        units = len(new_c) + len(new_e)
        if units < FLOOR:
            consecutive += 1
            if consecutive >= WINDOW and fired_at is None:
                fired_at = int(rnd.get("round") or 0)
        else:
            consecutive = 0
        curve.append(
            {
                "round": int(rnd.get("round") or 0),
                "new_claim_ids": new_c,
                "new_evidence_ids": new_e,
                "information_units": units,
                "subfloor": units < FLOOR,
                "consecutive_subfloor": consecutive,
            }
        )
        prior_c |= c_now
        prior_e |= e_now
    fired = fired_at is not None
    return {
        "fixture_id": doc.get("id"),
        "signal": "id-set-difference-only",
        "fired": fired,
        "silent": not fired,
        "fired_at_round": fired_at,
        "gain_curve": curve,
    }


def fixture_path(name: str) -> Path:
    return FIXTURES / name
