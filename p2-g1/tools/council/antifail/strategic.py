"""Strategic-vote / pivotal-abstention detector (IMP-0347)."""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

_STANCE = re.compile(r"STANCE:(AYE|NAY|ABSTAIN)", re.I)
POLICY_ID = "majority-of-seated:include-abstain-in-denominator"


def _stances(text_or_hist) -> list[str]:
    texts: list[str] = []
    if isinstance(text_or_hist, str):
        texts = [text_or_hist]
    elif isinstance(text_or_hist, list):
        for item in text_or_hist:
            if isinstance(item, dict):
                texts.append(str(item.get("text") or ""))
            else:
                texts.append(str(item))
    out = []
    for t in texts:
        out.extend(m.group(1).lower() for m in _STANCE.finditer(t))
    return out


def evaluate_ballot(pair: Mapping[str, Any]) -> dict[str, Any]:
    hist = pair.get("reasoning_history") or pair.get("history") or pair.get("text") or []
    stances = _stances(hist)
    implied = stances[-1] if stances else None
    ballot = str(pair.get("ballot") or pair.get("vote") or "").lower()
    change = len(set(stances)) > 1
    strategic_vote = bool(
        implied and ballot and implied != ballot and implied != "abstain" and ballot not in {"abstain", ""}
    )
    if change and implied == ballot:
        strategic_vote = False
    return {
        "id": pair.get("id"),
        "participant_id": pair.get("participant_id") or pair.get("id"),
        "strategic": strategic_vote,
        "strategic_vote": strategic_vote,
        "strategic_abstention": False,
        "pivotal_abstention": False,
        "change_of_mind": change,
        "implied_stance": implied,
        "ballot": ballot,
        "honest_counterfactual": None,
    }


def score_corpus(corpus: Mapping[str, Any]) -> dict[str, Any]:
    pairs = list(corpus.get("pairs") or [])
    rows = []
    tp = fp = fn = tn = 0
    cm_n = 0
    cm_fp = 0
    for p in pairs:
        det = evaluate_ballot(p)
        label = str(p.get("label") or "")
        pred = bool(det["strategic_vote"])
        truth = label == "strategic_vote"
        if truth and pred:
            tp += 1
        elif (not truth) and pred:
            fp += 1
        elif truth and not pred:
            fn += 1
        else:
            tn += 1
        if label == "change_of_mind":
            cm_n += 1
            if pred:
                cm_fp += 1
        rows.append({**det, "pred_strategic": pred, "label": label})
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    return {
        "n_pairs": len(pairs),
        "precision": prec,
        "recall": rec,
        "metrics": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "change_of_mind_n": cm_n,
        "change_of_mind_false_positives": cm_fp,
        "change_of_mind_fpr": (cm_fp / cm_n) if cm_n else 0.0,
        "profile_reports": [],
        "rows": rows,
    }


def _outcome(aye: int, nay: int, *, need: int) -> dict[str, Any]:
    if aye >= need:
        return {"outcome": "PASS", "winner": "aye", "aye": aye, "nay": nay, "need": need}
    if nay >= need:
        return {"outcome": "PASS", "winner": "nay", "aye": aye, "nay": nay, "need": need}
    return {"outcome": "FAIL", "winner": None, "aye": aye, "nay": nay, "need": need}


def tally(profile_or_ballots, *args, **kwargs) -> dict[str, Any]:
    if isinstance(profile_or_ballots, Mapping) and "seats" in profile_or_ballots:
        ballots = [str(s.get("ballot") or "abstain").lower() for s in profile_or_ballots.get("seats") or []]
        n_seats = int(profile_or_ballots.get("n_seats") or len(ballots))
        quorum = int(profile_or_ballots.get("quorum") or ((n_seats // 2) + 1))
        threshold = str(profile_or_ballots.get("threshold") or "majority_of_seated")
        policy = str(profile_or_ballots.get("abstention_policy") or "include_in_denominator")
    else:
        ballots = [str(b).lower() for b in list(profile_or_ballots)]
        n_seats = int(kwargs.get("n_seats") or len(ballots))
        quorum = int(kwargs.get("quorum") or ((n_seats // 2) + 1))
        threshold = str(kwargs.get("threshold") or "majority_of_seated")
        policy = str(kwargs.get("abstention_policy") or "include_in_denominator")
    aye = sum(1 for b in ballots if b in {"aye", "yes", "for"})
    nay = sum(1 for b in ballots if b in {"nay", "no", "against"})
    abstain = n_seats - aye - nay
    need = quorum if threshold == "majority_of_seated" else quorum
    actual = _outcome(aye, nay, need=need)
    actual.update(
        {
            "policy_id": POLICY_ID,
            "quorum": quorum,
            "threshold": threshold,
            "abstention_policy": policy,
            "n_seats": n_seats,
            "abstain": abstain,
        }
    )
    return actual


def _honest_vote(implied: str | None, ballot: str) -> str:
    if implied in {"aye", "nay"}:
        return implied
    return ballot or "abstain"


def quorum_sensitivity(profile: Mapping[str, Any]) -> dict[str, Any]:
    seats = list(profile.get("seats") or [])
    actual = tally(profile)
    need = int(actual["need"])
    pivotal_ids: list[str] = []
    enriched = []
    for s in seats:
        det = evaluate_ballot(
            {
                "id": s.get("participant_id"),
                "participant_id": s.get("participant_id"),
                "ballot": s.get("ballot"),
                "reasoning_history": s.get("reasoning_history") or [],
            }
        )
        ballot = det["ballot"]
        implied = det["implied_stance"]
        aye = int(actual["aye"])
        nay = int(actual["nay"])
        if ballot in {"aye", "yes"}:
            aye -= 1
        elif ballot in {"nay", "no"}:
            nay -= 1
        is_abs = ballot in {"abstain", ""}
        aye_flip = _outcome(aye + 1, nay, need=need)["outcome"] != actual["outcome"]
        nay_flip = _outcome(aye, nay + 1, need=need)["outcome"] != actual["outcome"]
        pivotal = bool(is_abs and (aye_flip or nay_flip))
        hv = _honest_vote(implied, ballot)
        if hv in {"aye", "yes"}:
            honest = _outcome(aye + 1, nay, need=need)
        elif hv in {"nay", "no"}:
            honest = _outcome(aye, nay + 1, need=need)
        else:
            honest = dict(actual)
        flips = honest["outcome"] != actual["outcome"]
        if pivotal:
            pivotal_ids.append(str(s.get("participant_id")))
        det["pivotal_abstention"] = pivotal
        det["strategic_abstention"] = bool(pivotal and implied in {"aye", "nay"})
        det["strategic"] = det["strategic_abstention"] or det["strategic_vote"]
        det["honest_counterfactual"] = {**honest, "flips_vs_actual": flips}
        enriched.append(det)
    return {
        "profile_id": profile.get("profile_id"),
        "policy_id": POLICY_ID,
        "actual": actual,
        "pivotal_ids": pivotal_ids,
        "detections": enriched,
    }


def evaluate_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    q = quorum_sensitivity(profile)
    return {
        "profile_id": profile.get("profile_id"),
        "detections": q["detections"],
        "tally": q["actual"],
        "pivotal_ids": q["pivotal_ids"],
        "policy_id": POLICY_ID,
    }
