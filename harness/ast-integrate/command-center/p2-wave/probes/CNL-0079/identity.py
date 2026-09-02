"""Objection identity: restatement vs genuinely new.

Lexical-only identity is the known-bad mutant (CNL-0051 measured Jaccard
0.93-1.00 on renames and silence on rewrites). This unit requires TWO
mechanically different signals before two utterances count as the SAME
objection:

  Signal S1 (structured slots): (target_claim_id, polarity, defect_class)
  Signal S2 (observation fingerprint): normalized named_observation

SAME iff S1 matches AND S2 matches.
A paraphrase of the same defect keeps both slots and the observation.
A genuinely new objection changes at least one slot.

Untyped free-text (missing slots) is INADMISSIBLE and does not count as
an objection for the quiet-round counter — it cannot game the metric.
"""

from __future__ import annotations

import re
from typing import Any

_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "a an the is are was were be to of and or for in on at by with from that this it".split()
)


def _norm_obs(value: str) -> str:
    return _WS.sub("", str(value).strip().lower())


def _tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1)


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def admissible(obj: dict[str, Any]) -> bool:
    return all(
        str(obj.get(k) or "").strip()
        for k in ("target_claim_id", "polarity", "defect_class", "named_observation")
    )


def slot_key(obj: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(obj["target_claim_id"]).strip(),
        str(obj["polarity"]).strip(),
        str(obj["defect_class"]).strip(),
    )


def observation_key(obj: dict[str, Any]) -> str:
    return _norm_obs(str(obj.get("named_observation") or ""))


def same_objection(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Canonical identity: structured slots AND observation fingerprint."""
    if not admissible(a) or not admissible(b):
        return False
    return slot_key(a) == slot_key(b) and observation_key(a) == observation_key(b)


def same_objection_lexical_only(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Planted-bad identity: exact text or high Jaccard. Misses paraphrase."""
    ta = str(a.get("text") or a.get("text") or "").strip()
    tb = str(b.get("text") or b.get("text") or "").strip()
    if ta == tb and ta:
        return True
    return jaccard(ta, tb) >= 0.85


jaccard = jaccard
admissible = admissible
same_objection = same_objection
slot_key = slot_key
same_objection_lexical_only = same_objection_lexical_only
jaccard = jaccard
