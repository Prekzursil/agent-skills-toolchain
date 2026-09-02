#!/usr/bin/env python3
"""Saturation vs quota-filling classifier for the 100-idea target (CNL-0055).

Two mechanically different readings:

  Signal 1 — token-set Jaccard unique-idea yield (Y). Two candidate strings
  are the SAME idea when Jaccard(token-set) >= JACCARD_DUP. This is the
  local stand-in for CNL-0051's semantic unique counter; it is not a claim
  that CNL-0051 is delivered on this tree.

  Signal 2 — raw offered volume versus remaining raw-count quota gap.
  This reading never looks at Jaccard. It asks only whether this round's
  candidate dump is large enough to close (quota - len(ledger)).

Decision (conjunction, not a blended score):

  QUOTA_FILLING if Y == 0 AND volume chases the remaining quota.
      stop_round = False. Padding must not satisfy unique_ideas >= 100.
  SATURATION    if Y == 0 AND volume does not chase the quota.
      stop_round = True. Real exhaustion stops the round, including
      early saturation before 100; the quota arm stays unsatisfied
      unless unique_after already meets quota without padding.
  CONTINUE      if Y > 0.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

QUOTA = 100
JACCARD_DUP = 0.80
TRIGRAM_DUP = 0.75
PADDING_VOLUME_FLOOR = 20
SATURATION_VOLUME_CEILING = 8
TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> frozenset[str]:
    return frozenset(TOKEN_RE.findall(text.lower()))


def trigrams(text: str) -> frozenset[str]:
    s = re.sub(r"\s+", " ", text.lower()).strip()
    if len(s) < 3:
        return frozenset({s})
    return frozenset(s[i : i + 3] for i in range(len(s) - 2))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = len(a | b)
    if union == 0:
        return 0.0
    return len(a & b) / union


def cluster_count(texts: list[str], feature, threshold: float) -> int:
    """Greedy clusters. A text joins a cluster if it is similar to ANY member.

    Matching against the union of members is rejected: a suffix merge would
    fatten the set and let a later prefix of the same parent fall below
    threshold (6/8 = 0.75), which would count padding as unique.
    """
    clusters: list[list[frozenset[str]]] = []
    for text in texts:
        feat = feature(text)
        hit = None
        for i, members in enumerate(clusters):
            if any(jaccard(feat, member) >= threshold for member in members):
                hit = i
                break
        if hit is None:
            clusters.append([feat])
        else:
            clusters[hit].append(feat)
    return len(clusters)


def unique_jaccard(texts: list[str]) -> int:
    return cluster_count(texts, tokens, JACCARD_DUP)


def unique_trigram(texts: list[str]) -> int:
    return cluster_count(texts, trigrams, TRIGRAM_DUP)


def naive_exact(texts: list[str]) -> int:
    return len(set(texts))


def _volume_chases_quota(raw_n: int, offered_n: int, quota: int) -> bool:
    raw_gap = quota - raw_n
    if raw_gap <= 0:
        return False
    if offered_n < PADDING_VOLUME_FLOOR:
        return False
    return offered_n >= min(raw_gap, PADDING_VOLUME_FLOOR)


def classify(
    ledger: list[str],
    offered: list[str],
    quota: int = QUOTA,
    unique_fn=unique_jaccard,
) -> dict:
    unique_before = unique_fn(list(ledger))
    unique_after = unique_fn(list(ledger) + list(offered))
    y = unique_after - unique_before
    r = len(offered)
    raw_n = len(ledger)
    raw_gap = quota - raw_n
    padding_ratio = (1.0 - (y / r)) if r else 0.0
    volume_chases = _volume_chases_quota(raw_n, r, quota)
    naive_before = naive_exact(ledger)
    naive_after = naive_exact(list(ledger) + list(offered))

    if y == 0 and volume_chases:
        decision = "QUOTA_FILLING"
        stop_round = False
        reason = (
            "marginal unique yield is 0 while offered volume is large enough "
            "to close the remaining raw quota gap"
        )
    elif y == 0:
        decision = "SATURATION"
        stop_round = True
        reason = (
            "next round adds no unique idea and the dump is not a quota chase "
            f"(offered={r}, raw_gap={raw_gap})"
        )
    else:
        decision = "CONTINUE"
        stop_round = False
        reason = f"round added {y} unique ideas"

    satisfy_unique_quota = unique_after >= quota and decision != "QUOTA_FILLING"
    return {
        "decision": decision,
        "stop_round": stop_round,
        "satisfy_unique_quota": satisfy_unique_quota,
        "reason": reason,
        "quota": quota,
        "offered_n": r,
        "ledger_n": raw_n,
        "raw_gap": raw_gap,
        "unique_before": unique_before,
        "unique_after": unique_after,
        "unique_yield": y,
        "padding_ratio": round(padding_ratio, 4),
        "volume_chases_quota": volume_chases,
        "naive_before": naive_before,
        "naive_after": naive_after,
        "naive_yield": naive_after - naive_before,
        "unique_fn": getattr(unique_fn, "__name__", str(unique_fn)),
        "low_volume": r <= SATURATION_VOLUME_CEILING,
    }


def classify_both(ledger: list[str], offered: list[str], quota: int = QUOTA) -> dict:
    s1 = classify(ledger, offered, quota=quota, unique_fn=unique_jaccard)
    s2_volume = {
        "raw_ledger_n": len(ledger),
        "raw_gap": quota - len(ledger),
        "offered_n": len(offered),
        "volume_chases_quota": _volume_chases_quota(len(ledger), len(offered), quota),
        "naive_yield": naive_exact(list(ledger) + list(offered)) - naive_exact(ledger),
    }
    s1_trigram = classify(ledger, offered, quota=quota, unique_fn=unique_trigram)
    return {
        "signal1_jaccard": s1,
        "signal2_raw_volume": s2_volume,
        "independent_trigram": s1_trigram,
        "decision": s1["decision"],
        "stop_round": s1["stop_round"],
        "satisfy_unique_quota": s1["satisfy_unique_quota"],
        "methods_agree_on_decision": s1["decision"] == s1_trigram["decision"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", choices=["padding", "saturated", "continue", "early_saturation"])
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json-out", type=str, default="")
    args = parser.parse_args()
    sys.path.insert(0, str(HERE))
    import fixtures as F  # noqa: E402

    if args.self_test:
        report = F.self_test()
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.get("pass") else 1
    if not args.fixture:
        parser.error("need --fixture or --self-test")
    pack = F.build(args.fixture)
    result = classify_both(pack["ledger"], pack["offered"], quota=pack["quota"])
    result["fixture"] = args.fixture
    result["expected_decision"] = pack["expected_decision"]
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
