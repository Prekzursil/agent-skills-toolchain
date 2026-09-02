"""No-information-gain (looping council) anti-fail trigger (IMP-0322).

A council that keeps restating the same claims is looping, not deliberating.
Each round is scored against everything said before it:

* a claim that only paraphrases a prior claim is a **repetition** and adds
  no gain;
* a claim that covers a prior claim and adds a constraint (numeric bound,
  exception, rollback, TTL, cap, ...) is a **refinement** and counts as gain;
* a claim unrelated to every prior claim is **new** and counts as gain;
* an evidence node not cited before is gain even when every claim is a
  restatement (an evidence-only round is not circular).

Round gain ``G_t = new_claims + refined_claims + new_evidence``. The trigger
FIRES at the first round ``t >= MIN_ROUNDS`` whose trailing ``WINDOW`` rounds
all have ``G_t < 1``.

Claims are ``{"text": str, "claim_id"?, "family_id"?, "refinement_of"?,
"qualifiers"?}``; evidence is ``{"evidence_id"?, "source"?, "quote"?}``. The
text is what is compared; recorder metadata (``refinement_of``, new
``qualifiers``) may only promote a non-repetition to refinement.
"""

from __future__ import annotations

import re
from typing import Any

REPETITION = "repetition"
REFINEMENT = "refinement"
NEW = "new"

WINDOW = 2
MIN_ROUNDS = 3
REPETITION_JACCARD = 0.5
REFINEMENT_COVERAGE = 0.6

_STOPWORDS = frozenset(
    """
    a an the is are be been being was were am do does did done must should
    would could may might can shall will to of in on at for with by from into
    onto as and or it its this that these those which who whom there here than
    then also very own same s under
    """.split()
)

_CONSTRAINT_WORDS = frozenset(
    """
    except exception exceptions unless only limit limited cap capped maximum
    minimum max min ttl timeout rollback freeze window threshold exceed exceeds
    within if until bound bounded quota expiry expire deadline
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-/\.]*")


def _stem(word: str) -> str:
    if len(word) <= 3 or not word.isalpha():
        return word
    for suf in ("ment", "ing", "ies", "ied", "ed", "es", "s"):
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            word = word[: -len(suf)] + ("y" if suf in ("ies", "ied") else "")
            break
    if len(word) > 4 and word[-1] == word[-2] and word[-1] not in "aeiou":
        word = word[:-1]
    if len(word) > 4 and word.endswith("e"):
        word = word[:-1]
    return word


def content_tokens(text: str) -> list[str]:
    """Ordered, stemmed content words (stopwords dropped, duplicates kept)."""
    out: list[str] = []
    for raw in _TOKEN_RE.findall(str(text or "").casefold()):
        tok = raw.strip(".-/")
        if not tok or tok in _STOPWORDS:
            continue
        out.append(_stem(tok))
    return out


def _has_constraint_signal(tokens: set[str]) -> bool:
    for tok in tokens:
        if any(ch.isdigit() for ch in tok):
            return True
        if tok in _CONSTRAINT_WORDS or _stem(tok) in _CONSTRAINT_WORDS:
            return True
    return False


def _is_subsequence(short: list[str], long: list[str]) -> bool:
    it = iter(long)
    return all(any(tok == cand for cand in it) for tok in short)


def classify_relation(old: str, new: str) -> str:
    """Relate a later claim ``new`` to an earlier claim ``old``.

    Returns ``"repetition"``, ``"refinement"`` or ``"new"``.
    """
    old_seq = content_tokens(old)
    new_seq = content_tokens(new)
    old_set, new_set = set(old_seq), set(new_seq)
    if not old_set or not new_set:
        return REPETITION if old_set == new_set else NEW
    if old_set == new_set:
        return REPETITION
    added = new_set - old_set
    if not added:
        # shorter restatement: nothing new was said
        return REPETITION
    coverage = len(old_set & new_set) / len(old_set)
    if coverage >= 0.999 and _is_subsequence(old_seq, new_seq):
        # the old claim is carried verbatim (in order) and extended
        return REFINEMENT
    if coverage >= REFINEMENT_COVERAGE and _has_constraint_signal(added):
        return REFINEMENT
    jaccard = len(old_set & new_set) / len(old_set | new_set)
    if jaccard >= REPETITION_JACCARD:
        return REPETITION
    return NEW


def _claim_text(claim: Any) -> str:
    if isinstance(claim, str):
        return claim
    if isinstance(claim, dict):
        return str(claim.get("text") or claim.get("claim") or "")
    return str(claim)


def _evidence_key(item: Any) -> str:
    if isinstance(item, str):
        return "quote:" + " ".join(content_tokens(item))
    if isinstance(item, dict):
        eid = item.get("evidence_id") or item.get("id")
        if eid:
            return f"id:{eid}"
        return "quote:" + " ".join(
            content_tokens(f"{item.get('source', '')} {item.get('quote', '')}")
        )
    return f"repr:{item!r}"


def relate_to_history(claim: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    """Best relation of ``claim`` to every prior claim (repetition wins over refinement)."""
    text = _claim_text(claim)
    best = NEW
    matched: str | None = None
    for prior in history:
        rel = classify_relation(_claim_text(prior), text)
        if rel == REPETITION:
            return {"relation": REPETITION, "matched": prior.get("_key"), "text": text}
        if rel == REFINEMENT and best != REFINEMENT:
            best, matched = REFINEMENT, prior.get("_key")
    if best == NEW and isinstance(claim, dict) and history:
        # recorder metadata may promote to refinement, never to repetition
        seen_q = {q for p in history for q in (p.get("qualifiers") or [])}
        new_q = [q for q in (claim.get("qualifiers") or []) if q not in seen_q]
        if claim.get("refinement_of") or new_q:
            related = [p for p in history if p.get("family_id") and p.get("family_id") == claim.get("family_id")]
            if related or claim.get("refinement_of"):
                best, matched = REFINEMENT, (related[0].get("_key") if related else claim.get("refinement_of"))
    return {"relation": best, "matched": matched, "text": text}


def score_round(
    rnd: dict[str, Any], history: list[dict[str, Any]], seen_evidence: set[str]
) -> dict[str, Any]:
    new_c = refined_c = repeated_c = 0
    relations: list[dict[str, Any]] = []
    staged: list[dict[str, Any]] = []
    for idx, claim in enumerate(rnd.get("claims") or []):
        cdict = dict(claim) if isinstance(claim, dict) else {"text": str(claim)}
        rel = relate_to_history(cdict, history)
        relations.append(rel)
        if rel["relation"] == REPETITION:
            repeated_c += 1
        elif rel["relation"] == REFINEMENT:
            refined_c += 1
        else:
            new_c += 1
        cdict["_key"] = cdict.get("claim_id") or f"r{rnd.get('round')}#{idx}"
        staged.append(cdict)
    new_e = 0
    for item in rnd.get("evidence") or []:
        key = _evidence_key(item)
        if key not in seen_evidence:
            seen_evidence.add(key)
            new_e += 1
    history.extend(staged)
    gain_value = new_c + refined_c + new_e
    return {
        "round": rnd.get("round"),
        "new_claim_count": new_c,
        "refined_claim_count": refined_c,
        "repeated_claim_count": repeated_c,
        "new_evidence_count": new_e,
        "gain_value": gain_value,
        "gain": gain_value >= 1,
        "relations": relations,
    }


def evaluate_council(
    council: dict[str, Any], window: int = WINDOW, min_rounds: int = MIN_ROUNDS
) -> dict[str, Any]:
    """Score every round of a recorded council and decide whether the trigger fires."""
    rounds = sorted(council.get("rounds") or [], key=lambda r: r.get("round", 0))
    history: list[dict[str, Any]] = []
    seen_evidence: set[str] = set()
    per_round: list[dict[str, Any]] = []
    fired = False
    fire_round: int | None = None
    reason: str | None = None
    for rnd in rounds:
        row = score_round(rnd, history, seen_evidence)
        per_round.append(row)
        n = len(per_round)
        if not fired and n >= min_rounds and n >= window:
            tail = per_round[-window:]
            if all(not r["gain"] for r in tail):
                fired = True
                fire_round = row["round"]
                reason = (
                    f"no_information_gain: {window} consecutive rounds with "
                    f"G_t < 1 at round {fire_round}"
                )
    if not fired:
        if len(per_round) < min_rounds:
            reason = f"too_few_rounds: {len(per_round)} < {min_rounds}"
        else:
            stalls = sum(1 for r in per_round if not r["gain"])
            reason = (
                f"information_gain: no {window}-round window without gain "
                f"({stalls} stalled round(s) of {len(per_round)})"
            )
    return {
        "id": council.get("id"),
        "fired": fired,
        "fire_round": fire_round,
        "reason": reason,
        "per_round": per_round,
        "n_rounds": len(per_round),
        "policy": {
            "window": window,
            "min_rounds": min_rounds,
            "refinement_is_gain": True,
            "evidence_without_new_claims_is_gain": True,
            "paraphrase_without_constraint_is_repetition": True,
        },
    }


__all__ = [
    "NEW",
    "REFINEMENT",
    "REPETITION",
    "WINDOW",
    "MIN_ROUNDS",
    "classify_relation",
    "content_tokens",
    "evaluate_council",
    "relate_to_history",
    "score_round",
]
