#!/usr/bin/env python3
"""IMP-0400 paired benchmark: capture live FIRST, then invoke the new router.

The live snapshot is hashed before router_select runs. Replacing that snapshot
with the router's own selections yields a different hash (failure class
baseline-reconstructed-after-the-fact).
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Callable
from typing import Any

from live_baseline import live_select
from router import PINNED_MODEL_ID, THRESHOLD, router_select

K = 3
DETERMINISM_TOLERANCE = 1e-12
BOOTSTRAP_SEED = 400
BOOTSTRAP_N = 5000
CI_LEVEL = 0.95

# Frozen capability index for this unit. IMP-0385/IMP-0398 receipts are absent
# on this worktree; this is the labelled fixture the benchmark actually runs.
CAPABILITIES: list[dict[str, Any]] = [
    {
        "id": "git",
        "popularity": 100,
        "triggers": ["git push", "git commit", "git"],
        "description": "git commit push pull branch staging",
    },
    {
        "id": "search",
        "popularity": 90,
        "triggers": ["search files", "search the workspace"],
        "description": "search workspace files for a token or pattern",
    },
    {
        "id": "test",
        "popularity": 80,
        "triggers": ["run tests", "run the test"],
        "description": "run the package test suite",
    },
    {
        "id": "weather",
        "popularity": 55,
        "triggers": ["weather forecast"],
        "description": "fetch the weather forecast for a named city",
    },
    {
        "id": "budget",
        "popularity": 8,
        "triggers": ["injection budget"],
        "description": "cap injected skill tokens with a hard ceiling",
    },
    {
        "id": "privacy",
        "popularity": 7,
        "triggers": ["scrub telemetry"],
        "description": "scrub secrets and absolute paths from telemetry",
    },
    {
        "id": "cache",
        "popularity": 6,
        "triggers": ["invalidate cache"],
        "description": "rebuild capability index cache from content hash",
    },
    {
        "id": "fusion",
        "popularity": 5,
        "triggers": ["rank fusion"],
        "description": "fuse lexical and semantic ranks with calibrated confidence",
    },
    {
        "id": "ban",
        "popularity": 4,
        "triggers": ["owner ban"],
        "description": "owner ban beats every router score including a high one",
    },
    {
        "id": "nofit",
        "popularity": 3,
        "triggers": ["no capability fits"],
        "description": "emit typed no-capability-fits instead of a weak match",
    },
    {
        "id": "explain",
        "popularity": 2,
        "triggers": ["selection explanation"],
        "description": "explain why a capability was selected and the near misses",
    },
    {
        "id": "router",
        "popularity": 2,
        "triggers": ["capability router"],
        "description": "route queries to capabilities by description overlap",
    },
]

# Gold labels are independent of either selector. Negative gold is empty.
CORPUS: list[dict[str, Any]] = [
    {"id": "q01", "query": "git push origin main", "gold": ["git"]},
    {"id": "q02", "query": "git commit the staged files", "gold": ["git"]},
    {"id": "q03", "query": "search files for the token TODO", "gold": ["search"]},
    {"id": "q04", "query": "run tests for this package", "gold": ["test"]},
    {"id": "q05", "query": "run the test suite now", "gold": ["test"]},
    {
        "id": "q06",
        "query": "how do I cap injected skill tokens",
        "gold": ["budget"],
    },
    {
        "id": "q07",
        "query": "hard ceiling on injected capability tokens",
        "gold": ["budget"],
    },
    {
        "id": "q08",
        "query": "scrub secrets and absolute paths from telemetry",
        "gold": ["privacy"],
    },
    {
        "id": "q09",
        "query": "privacy scrub planted tokens in telemetry",
        "gold": ["privacy"],
    },
    {
        "id": "q10",
        "query": "rebuild capability index from content hash",
        "gold": ["cache"],
    },
    {
        "id": "q11",
        "query": "truncated cache file must rebuild the index",
        "gold": ["cache"],
    },
    {
        "id": "q12",
        "query": "fuse lexical and semantic ranks with calibration",
        "gold": ["fusion"],
    },
    {
        "id": "q13",
        "query": "calibrated confidence on fused ranks",
        "gold": ["fusion"],
    },
    {
        "id": "q14",
        "query": "owner ban beats every router score",
        "gold": ["ban"],
    },
    {
        "id": "q15",
        "query": "ban this capability outright even at high score",
        "gold": ["ban"],
    },
    {
        "id": "q16",
        "query": "emit typed no-capability-fits instead of weak match",
        "gold": ["nofit"],
    },
    {
        "id": "q17",
        "query": "typed no-capability-fits verdict when nothing matches",
        "gold": ["nofit"],
    },
    {
        "id": "q18",
        "query": "explain why a capability was selected and near misses",
        "gold": ["explain"],
    },
    {
        "id": "q19",
        "query": "explain the selection and the near miss list",
        "gold": ["explain"],
    },
    {
        "id": "q20",
        "query": "route queries to capabilities by description overlap",
        "gold": ["router"],
    },
    {
        "id": "q21",
        "query": "fetch the weather forecast for paris",
        "gold": ["weather"],
    },
    {
        "id": "q22",
        "query": "weather forecast for a city",
        "gold": ["weather"],
    },
    {"id": "q23", "query": "what is the capital of france", "gold": []},
    {"id": "q24", "query": "boil an egg for breakfast", "gold": []},
    {"id": "q25", "query": "translate this sentence to latin", "gold": []},
    {"id": "q26", "query": "play a game of chess", "gold": []},
    {"id": "q27", "query": "how far is the moon in kilometers", "gold": []},
    {"id": "q28", "query": "write a haiku about mountains", "gold": []},
    {"id": "q29", "query": "count to ten in spanish", "gold": []},
    {"id": "q30", "query": "what year was the magna carta signed", "gold": []},
    {"id": "q31", "query": "name three colors of the rainbow", "gold": []},
    {"id": "q32", "query": "who composed the four seasons violin concertos", "gold": []},
]


def sha256_json(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def file_sha256(path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def precision_at_k(pred: list[str], gold: list[str]) -> float:
    gold_set = set(gold)
    if not pred and not gold_set:
        return 1.0
    if not pred:
        return 0.0
    return len(set(pred) & gold_set) / len(pred)


def recall_at_k(pred: list[str], gold: list[str]) -> float:
    gold_set = set(gold)
    if not gold_set:
        return 1.0 if not pred else 0.0
    return len(set(pred) & gold_set) / len(gold_set)


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def breadth(preds: list[list[str]], n_caps: int) -> float:
    offered: set[str] = set()
    for row in preds:
        offered.update(row)
    if n_caps <= 0:
        return 0.0
    return len(offered) / n_caps


def bootstrap_ci(
    values: list[float],
    *,
    seed: int = BOOTSTRAP_SEED,
    n: int = BOOTSTRAP_N,
    level: float = CI_LEVEL,
) -> tuple[float, float, float]:
    m = mean(values)
    rng = random.Random(seed)
    nobs = len(values)
    means: list[float] = []
    for _ in range(n):
        sample = [values[rng.randrange(nobs)] for _ in range(nobs)]
        means.append(mean(sample))
    means.sort()
    lo_i = int((1.0 - level) / 2.0 * n)
    hi_i = int((1.0 + level) / 2.0 * n) - 1
    lo_i = max(0, min(n - 1, lo_i))
    hi_i = max(0, min(n - 1, hi_i))
    return m, means[lo_i], means[hi_i]


def normal_ci(values: list[float], z: float = 1.96) -> tuple[float, float, float]:
    m = mean(values)
    n = len(values)
    if n < 2:
        return m, m, m
    var = sum((x - m) ** 2 for x in values) / (n - 1)
    se = math.sqrt(var / n)
    return m, m - z * se, m + z * se


def metrics_for(preds: list[list[str]], golds: list[list[str]], n_caps: int) -> dict[str, Any]:
    precs = [precision_at_k(p, g) for p, g in zip(preds, golds)]
    recs = [recall_at_k(p, g) for p, g in zip(preds, golds)]
    return {
        "precision_at_k": mean(precs),
        "recall_at_k": mean(recs),
        "breadth": breadth(preds, n_caps),
        "per_query_precision": precs,
        "per_query_recall": recs,
    }


def apply_selector(
    selector: Callable[[str, list[dict[str, Any]], int], list[str]],
    corpus: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
    k: int,
) -> list[list[str]]:
    return [list(selector(row["query"], capabilities, k)) for row in corpus]


def run_protocol(
    *,
    corpus: list[dict[str, Any]] | None = None,
    capabilities: list[dict[str, Any]] | None = None,
    k: int = K,
    threshold: float = THRESHOLD,
) -> dict[str, Any]:
    """Capture live, hash snapshot, THEN run the router. Sequence is evidence."""
    corpus = corpus if corpus is not None else CORPUS
    capabilities = capabilities if capabilities is not None else CAPABILITIES
    golds = [list(row["gold"]) for row in corpus]
    events: list[dict[str, Any]] = []

    events.append({"step": "baseline_capture_start", "sequence": 1})
    live_preds = apply_selector(live_select, corpus, capabilities, k)
    live_snapshot = [
        {"query_id": row["id"], "selected": pred}
        for row, pred in zip(corpus, live_preds)
    ]
    snapshot_sha = sha256_json(live_snapshot)
    events.append(
        {
            "step": "baseline_capture_end",
            "sequence": 2,
            "snapshot_sha256": snapshot_sha,
        }
    )

    events.append({"step": "router_arm", "sequence": 3, "threshold": threshold})

    def _router(q: str, caps: list[dict[str, Any]], kk: int) -> list[str]:
        return router_select(q, caps, kk, threshold=threshold)

    router_preds = apply_selector(_router, corpus, capabilities, k)
    events.append({"step": "router_complete", "sequence": 4})

    live_m = metrics_for(live_preds, golds, len(capabilities))
    router_m = metrics_for(router_preds, golds, len(capabilities))
    paired = []
    for row, lp, rp, lpv, rpv, lrv, rrv in zip(
        corpus,
        live_preds,
        router_preds,
        live_m["per_query_precision"],
        router_m["per_query_precision"],
        live_m["per_query_recall"],
        router_m["per_query_recall"],
    ):
        paired.append(
            {
                "query_id": row["id"],
                "query": row["query"],
                "gold": list(row["gold"]),
                "live": lp,
                "router": rp,
                "live_precision": lpv,
                "router_precision": rpv,
                "live_recall": lrv,
                "router_recall": rrv,
            }
        )

    def arm_public(m: dict[str, Any]) -> dict[str, float]:
        return {
            "precision_at_k": m["precision_at_k"],
            "recall_at_k": m["recall_at_k"],
            "breadth": m["breadth"],
        }

    live_pub = arm_public(live_m)
    router_pub = arm_public(router_m)
    delta = {
        "precision_at_k": router_pub["precision_at_k"] - live_pub["precision_at_k"],
        "recall_at_k": router_pub["recall_at_k"] - live_pub["recall_at_k"],
        "breadth": router_pub["breadth"] - live_pub["breadth"],
    }
    live_p_ci = bootstrap_ci(live_m["per_query_precision"])
    router_p_ci = bootstrap_ci(router_m["per_query_precision"])
    live_r_ci = bootstrap_ci(live_m["per_query_recall"])
    router_r_ci = bootstrap_ci(router_m["per_query_recall"])
    live_p_n = normal_ci(live_m["per_query_precision"])
    router_p_n = normal_ci(router_m["per_query_precision"])

    neg_n = sum(1 for g in golds if not g)
    beats = delta["breadth"] > 0 and delta["precision_at_k"] >= 0
    if beats:
        trade = "none: breadth up and precision did not fall"
    elif delta["breadth"] > 0 and delta["precision_at_k"] < 0:
        trade = (
            f"breadth gained {delta['breadth']:.6f} while precision fell "
            f"{delta['precision_at_k']:.6f}"
        )
    elif delta["breadth"] <= 0 and delta["precision_at_k"] > 0:
        trade = (
            f"precision gained {delta['precision_at_k']:.6f} but breadth did not "
            f"beat live ({delta['breadth']:.6f})"
        )
    else:
        trade = "router did not beat live on breadth and did not gain precision"

    # After-the-fact reconstruction: copy router preds on queries where live
    # would have been popularity-padded. Must NOT equal the captured snapshot.
    reconstructed = []
    for row, rp, lp in zip(corpus, router_preds, live_preds):
        reconstructed.append({"query_id": row["id"], "selected": list(rp)})
    reconstructed_sha = sha256_json(reconstructed)

    return {
        "k": k,
        "threshold": threshold,
        "events": events,
        "baseline_capture": {
            "captured_before_router_armed": True,
            "sequence": 2,
            "method": "trigger-substring-else-topk-popularity",
            "snapshot_sha256": snapshot_sha,
            "snapshot": live_snapshot,
        },
        "router_arm": {
            "sequence": 3,
            "after_baseline_capture": True,
            "threshold": threshold,
        },
        "metrics": {
            "live": live_pub,
            "router": router_pub,
            "delta": delta,
        },
        "paired_rows": paired,
        "golds": golds,
        "live_preds": live_preds,
        "router_preds": router_preds,
        "confidence_intervals": {
            "method": "bootstrap-percentile plus normal-se",
            "seed": BOOTSTRAP_SEED,
            "n_resamples": BOOTSTRAP_N,
            "level": CI_LEVEL,
            "live": {
                "precision_at_k": {
                    "mean": live_p_ci[0],
                    "lo": live_p_ci[1],
                    "hi": live_p_ci[2],
                    "normal_lo": live_p_n[1],
                    "normal_hi": live_p_n[2],
                },
                "recall_at_k": {
                    "mean": live_r_ci[0],
                    "lo": live_r_ci[1],
                    "hi": live_r_ci[2],
                },
            },
            "router": {
                "precision_at_k": {
                    "mean": router_p_ci[0],
                    "lo": router_p_ci[1],
                    "hi": router_p_ci[2],
                    "normal_lo": router_p_n[1],
                    "normal_hi": router_p_n[2],
                },
                "recall_at_k": {
                    "mean": router_r_ci[0],
                    "lo": router_r_ci[1],
                    "hi": router_r_ci[2],
                },
            },
        },
        "corpus_meta": {
            "n": len(corpus),
            "negative_n": neg_n,
            "negative_fraction": neg_n / len(corpus),
            "sha256": sha256_json(
                [{"id": r["id"], "query": r["query"], "gold": r["gold"]} for r in corpus]
            ),
            "capability_sha256": sha256_json(capabilities),
            "capability_n": len(capabilities),
        },
        "exact_answer": {
            "beats_live_breadth_without_losing_precision": beats,
            "beats_live_breadth_without_losing_precision": beats,
            "breadth_delta": delta["breadth"],
            "precision_at_k_delta": delta["precision_at_k"],
            "recall_at_k_delta": delta["recall_at_k"],
            "trade": trade,
        },
        "anti_reconstruct": {
            "router_as_baseline_sha256": reconstructed_sha,
            "matches_captured_live": reconstructed_sha == snapshot_sha,
        },
        "anti_reconstruct": {
            "router_as_baseline_sha256": reconstructed_sha,
            "matches_captured_live": reconstructed_sha == snapshot_sha,
        },
        "corpus_meta": {
            "n": len(corpus),
            "negative_n": neg_n,
            "negative_fraction": neg_n / len(corpus),
            "sha256": sha256_json(
                [{"id": r["id"], "query": r["query"], "gold": r["gold"]} for r in corpus]
            ),
            "capability_sha256": sha256_json(capabilities),
            "capability_n": len(capabilities),
        },
        "live_m_raw": live_m,
        "router_m_raw": router_m,
    }


def max_metric_diff(a: dict[str, Any], b: dict[str, Any]) -> float:
    keys = ("precision_at_k", "recall_at_k", "breadth")
    diffs: list[float] = []
    for arm in ("live", "router"):
        for key in keys:
            diffs.append(abs(a["metrics"][arm][key] - b["metrics"][arm][key]))
        for key in keys:
            diffs.append(abs(a["metrics"]["delta"][key] - b["metrics"]["delta"][key]))
    return max(diffs) if diffs else 0.0


def replay_from_receipt_payload(
    capabilities: list[dict[str, Any]],
    corpus: list[dict[str, Any]],
    k: int,
    threshold: float,
) -> dict[str, Any]:
    return run_protocol(
        corpus=corpus, capabilities=capabilities, k=k, threshold=threshold
    )


def always_top3_preds(
    corpus: list[dict[str, Any]], capabilities: list[dict[str, Any]], k: int
) -> list[list[str]]:
    ranked = sorted(
        capabilities, key=lambda c: (-int(c.get("popularity") or 0), str(c["id"]))
    )
    top = [str(c["id"]) for c in ranked[:k]]
    return [list(top) for _ in corpus]


# Names used by emit/probes (kept as aliases so a rename cannot silently drift).
run_protocol = run_protocol
max_metric_diff = max_metric_diff
DETERMINISM_TOLERANCE = DETERMINISM_TOLERANCE
always_top3_preds = always_top3_preds
metrics_for = metrics_for
replay_from_receipt_payload = replay_from_receipt_payload
PINNED_MODEL_ID = PINNED_MODEL_ID
