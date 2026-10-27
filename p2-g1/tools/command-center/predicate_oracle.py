"""Differential oracle: seven fan-in sites vs one 200-artifact corpus.

Spec failure class 'two completion predicates disagree' (line 11314). Gold
requires byte-identical verdicts across every call-site pair. The planted
control patches ``cloud_dispatcher`` to ``min_bytes=1``; if that fork is
silent, the oracle measures nothing.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any, Mapping

from completion_predicate import DEFAULT_MIN_BYTES, judge
from fanin_sites import SITE_IDS, canonical_verdict_bytes, check_unit

CORPUS_SIZE = 200
MIN_BORDERLINE = 40
PLANTED_SITE = "cloud_dispatcher"
PLANTED_MIN_BYTES = 1
BORDER_HI = DEFAULT_MIN_BYTES * 2  # 256; sizes in [1, 256) sit on the threshold

_NON_SIZE_FAIL_KEYS = (
    ("state", "RUNNING"),
    ("exists", False),
    ("parses", False),
    ("sentinel", ""),
    ("evidence_count", 0),
    ("tests_passed", False),
    ("negative_controls_ok", False),
    ("reviewer_pass", False),
    ("open_p0p1", True),
    ("manifest_registered", False),
    ("downstream_readable", False),
)


def _complete_base(*, size: int, art_id: str) -> dict[str, Any]:
    return {
        "id": art_id,
        "state": "SUCCESS",
        "exit_code": 0,
        "exists": True,
        "bytes": size,
        "parses": True,
        "sentinel": "SENTINEL:OK",
        "evidence_count": 2,
        "tests_passed": True,
        "negative_controls_ok": True,
        "reviewer_pass": True,
        "open_p0p1": False,
        "manifest_registered": True,
        "downstream_readable": True,
        "min_bytes": DEFAULT_MIN_BYTES,
    }


def build_corpus() -> list[dict[str, Any]]:
    """200 mixed complete/incomplete artifacts; >=40 sit on the size threshold.

    Layout (matches a closed 200-row mix):
      0-58   gold COMPLETE, size well above 2*min_bytes (not borderline)
      59-78  COMPLETE just above min_bytes (borderline)
      79-141 otherwise-complete but size in [1, 127] (borderline; planted diverges)
      142-199 other-condition INCOMPLETE, large size (not borderline)
    """
    rows: list[dict[str, Any]] = []
    for i in range(59):
        rows.append(_complete_base(size=400 + i, art_id=f"art-{i:03d}"))
    for j in range(20):
        i = 59 + j
        rows.append(_complete_base(size=128 + (j % 20), art_id=f"art-{i:03d}"))
    for j in range(63):
        i = 79 + j
        rows.append(_complete_base(size=1 + j, art_id=f"art-{i:03d}"))
    for j in range(58):
        i = 142 + j
        art = _complete_base(size=400, art_id=f"art-{i:03d}")
        key, value = _NON_SIZE_FAIL_KEYS[j % len(_NON_SIZE_FAIL_KEYS)]
        art[key] = value
        rows.append(art)
    if len(rows) != CORPUS_SIZE:
        raise RuntimeError(f"corpus size {len(rows)} != {CORPUS_SIZE}")
    return rows


def other_conditions_pass(record: Mapping[str, Any]) -> bool:
    """True when every condition except the size floor would SATISFY."""
    out = judge(record, min_bytes=PLANTED_MIN_BYTES)
    return out["complete"] is True or out["failing"] == ["C03"]


def is_borderline(record: Mapping[str, Any]) -> bool:
    try:
        size = int(record.get("bytes") or 0)
    except (TypeError, ValueError):
        return False
    if not (1 <= size < BORDER_HI):
        return False
    return other_conditions_pass(record)


def _site_result(
    site_id: str,
    record: Mapping[str, Any],
    overrides: Mapping[str, int] | None,
) -> dict[str, Any]:
    floor = None if not overrides else overrides.get(site_id)
    return check_unit(site_id, record, min_bytes=floor)


def disagreement_matrix(
    corpus: list[dict[str, Any]],
    overrides: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    per_art: list[dict[str, bytes]] = []
    complete_count = 0
    incomplete_count = 0
    per_site_complete = {s: 0 for s in SITE_IDS}
    for art in corpus:
        blobs: dict[str, bytes] = {}
        first_complete: bool | None = None
        for site in SITE_IDS:
            result = _site_result(site, art, overrides)
            blobs[site] = canonical_verdict_bytes(result)
            if site == SITE_IDS[0]:
                first_complete = bool(result["complete"])
            if result["complete"]:
                per_site_complete[site] += 1
        per_art.append(blobs)
        if first_complete:
            complete_count += 1
        else:
            incomplete_count += 1

    pairs = []
    for a, b in combinations(SITE_IDS, 2):
        n = sum(1 for blobs in per_art if blobs[a] != blobs[b])
        pairs.append({"site_a": a, "site_b": b, "disagreements": n})
    pair_sum = sum(p["disagreements"] for p in pairs)
    return {
        "pairs": pairs,
        "pair_disagreement_sum": pair_sum,
        "any_disagreement": pair_sum > 0,
        "counts": {
            "complete": complete_count,
            "incomplete": incomplete_count,
            "per_site_complete": per_site_complete,
        },
    }


def run_oracle(overrides: Mapping[str, int] | None = None) -> dict[str, Any]:
    corpus = build_corpus()
    matrix = disagreement_matrix(corpus, overrides)
    borderline = sum(1 for art in corpus if is_borderline(art))
    complete = matrix["counts"]["complete"]
    incomplete = matrix["counts"]["incomplete"]
    too_easy = borderline < MIN_BORDERLINE
    agree = (not matrix["any_disagreement"]) and not too_easy
    return {
        "corpus_size": len(corpus),
        "call_sites": list(SITE_IDS),
        "call_site_count": len(SITE_IDS),
        "borderline_count": borderline,
        "complete_count": complete,
        "incomplete_count": incomplete,
        "matrix": matrix,
        "oracle_too_easy": too_easy,
        "agree": agree and complete + incomplete == len(corpus),
        "min_bytes_default": DEFAULT_MIN_BYTES,
    }


def run_planted_divergence() -> dict[str, Any]:
    corpus = build_corpus()
    baseline = run_oracle()
    planted_overrides = {PLANTED_SITE: PLANTED_MIN_BYTES}
    planted_matrix = disagreement_matrix(corpus, planted_overrides)
    expected = 0
    for art in corpus:
        gold = judge(art, min_bytes=DEFAULT_MIN_BYTES)
        lax = judge(art, min_bytes=PLANTED_MIN_BYTES)
        if (not gold["complete"]) and lax["complete"]:
            expected += 1
    fired = (
        planted_matrix["any_disagreement"] is True
        and planted_matrix["pair_disagreement_sum"] > 0
        and expected >= 1
        and baseline["agree"] is True
    )
    return {
        "baseline_agree": baseline["agree"],
        "baseline_disagreements": baseline["matrix"]["pair_disagreement_sum"],
        "planted_site": PLANTED_SITE,
        "planted_min_bytes": PLANTED_MIN_BYTES,
        "planted_any_disagreement": planted_matrix["any_disagreement"],
        "planted_pair_disagreement_sum": planted_matrix["pair_disagreement_sum"],
        "expected_diverging_count": expected,
        "fired": fired,
    }
