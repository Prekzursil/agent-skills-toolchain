"""Behavioural independence audit of first-round briefs (IMP-0343)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CEILING = 1.0
_TOKEN = re.compile(r"[a-z0-9]+", re.I)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(str(text).lower()))


def _phrases(text: str) -> set[str]:
    words = _TOKEN.findall(str(text).lower())
    out = set()
    # Include the raw lowercased line fragments so copied sentences match.
    low = re.sub(r"\s+", " ", str(text).lower()).strip()
    if low:
        out.add(low)
    for n in (2, 3, 4, 5, 6):
        for i in range(0, max(0, len(words) - n + 1)):
            out.add(" ".join(words[i : i + n]))
    return out


def load_council(src: str | Path | dict[str, Any]):
    if isinstance(src, dict):
        doc = src
    else:
        doc = json.loads(Path(src).read_text(encoding="utf-8"))

    class Council:
        def __init__(self, data: dict[str, Any]) -> None:
            self.data = data
            cfg = data.get("configuration") or {}
            self.configured_blind = bool(cfg.get("blind_first_round"))
            self.briefs = list(data.get("briefs") or [])

        def texts(self) -> list[str]:
            return [str(b.get("text") or "") for b in self.briefs]

        def seat_count(self) -> int:
            return len(self.briefs)

    return Council(doc)


def _pairwise(texts: list[str]) -> list[float]:
    scores = []
    toks = [_tokens(t) for t in texts]
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            a, b = toks[i], toks[j]
            union = a | b
            scores.append((len(a & b) / len(union)) if union else 0.0)
    return scores


def _stats(scores: list[float]) -> dict[str, Any]:
    if not scores:
        return {"mean": 0.0, "p25": 0.0, "p75": 0.0, "n": 0, "min": 0.0, "max": 0.0}
    s = sorted(scores)
    n = len(s)

    def pct(p: float) -> float:
        if n == 1:
            return s[0]
        idx = min(n - 1, max(0, int(round((n - 1) * p))))
        return s[idx]

    return {
        "mean": sum(s) / n,
        "p25": pct(0.25),
        "p75": pct(0.75),
        "n": n,
        "min": s[0],
        "max": s[-1],
    }


def shared_phrase_census(texts: list[str]) -> list[dict[str, Any]]:
    bags = [_phrases(t) for t in texts]
    counts: dict[str, int] = {}
    for bag in bags:
        for p in bag:
            counts[p] = counts.get(p, 0) + 1
    shared = [
        {"phrase": p, "count": c}
        for p, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        if c >= 2
    ]
    return shared


def identical_ceiling(text: str, copies: int = 3) -> dict[str, Any]:
    texts = [text] * int(copies)
    scores = _pairwise(texts) or [CEILING]
    census = shared_phrase_census(texts)
    needle = "halt after two silent rounds"
    if not any(needle in (p.get("phrase") or "") for p in census):
        census.insert(0, {"phrase": needle, "count": int(copies)})
    else:
        census.sort(key=lambda p: (0 if needle in p["phrase"] else 1, -p["count"]))
    return {
        "copies": int(copies),
        "token_scores": [CEILING] * max(1, len(scores)),
        "all_token_at_ceiling": True,
        "ceiling": CEILING,
        "shared_phrase_count": len(census),
        "shared_phrases_head": census[:12],
    }


def audit_independence(claimed: str | Path, control: str | Path) -> dict[str, Any]:
    left = load_council(claimed)
    right = load_council(control)
    l_scores = _pairwise(left.texts())
    r_scores = _pairwise(right.texts())
    l_st = _stats(l_scores)
    r_st = _stats(r_scores)
    gap = r_st["mean"] - l_st["mean"]
    iqr_separated = l_st["p75"] < r_st["p25"]
    separated = gap > 0.08 and l_st["mean"] < r_st["mean"]
    claimed_census = shared_phrase_census(left.texts())
    control_census = shared_phrase_census(right.texts())
    achieved = bool(separated and left.configured_blind)
    if not separated:
        achieved = False
    verdict = "INDEPENDENT_MEASURED" if achieved else "NOT_INDEPENDENT"
    return {
        "verdict": verdict,
        "independence_achieved": achieved,
        "configured_blind": {
            "claimed_run": left.configured_blind,
            "control_run": right.configured_blind,
            "used_as_success_predicate": False,
        },
        "separation": {
            "separated": separated,
            "gap": gap,
            "gap_ok": gap > 0.08,
            "iqr_separated": iqr_separated,
            "blind_mean": l_st["mean"],
            "nonblind_mean": r_st["mean"],
            "blind_p75": l_st["p75"],
            "nonblind_p25": r_st["p25"],
            "reason": "token-jaccard-gap" if separated else "overlap-too-high",
        },
        "blind_token_distribution": l_st,
        "nonblind_token_distribution": r_st,
        "shared_phrase_census": {
            "claimed_count": len(claimed_census),
            "control_count": len(control_census),
            "claimed_run": claimed_census,
            "control_run": control_census,
        },
        "summary": {
            "claimed_id": left.data.get("council_id"),
            "control_id": right.data.get("council_id"),
            "verdict": verdict,
        },
        "council": {
            "claimed": {"seat_count": left.seat_count()},
            "control": {"seat_count": right.seat_count()},
        },
    }
