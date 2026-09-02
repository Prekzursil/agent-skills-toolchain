#!/usr/bin/env python3
"""Live measurements for TST-0265 emit + probes."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import importlib.util  # noqa: E402

import fixtures as F  # noqa: E402
import ledger as L  # noqa: E402


def _load_unique_ideas():
    """Load quota/unique_ideas.py by path.

    ``import tools.council`` currently pulls a missing ``simulate`` sibling;
    this unit must not depend on that package init.
    """
    path = REPO / "tools" / "council" / "quota" / "unique_ideas.py"
    spec = importlib.util.spec_from_file_location("tst0265_unique_ideas", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


U = _load_unique_ideas()


def _pair_row(seed: str, mutant: str) -> dict[str, Any]:
    raw_j = U.jaccard(U.raw_tokens(seed), U.raw_tokens(mutant))
    keys_eq = U.mechanism_key(seed) == U.mechanism_key(mutant)
    observed = U.pair_decision(seed, mutant)
    return {
        "raw_jaccard": round(raw_j, 6),
        "keys_equal": keys_eq,
        "s1_fires": raw_j >= U.JACCARD_THRESHOLD,
        "s2_fires": keys_eq,
        "observed": observed,
        "author_unique_count": U.unique_count_union_find([seed, mutant]),
        "reviewer_unique_count": U.unique_count_connected_components([seed, mutant]),
    }


def _corpus_row(name: str, ideas: list[str]) -> dict[str, Any]:
    raw = U.naive_unique(ideas)
    post = U.stopping_unique_count(ideas)
    reviewer = U.unique_count_connected_components(ideas)
    ratio = U.collapse_ratio(raw, post)
    return {
        "name": name,
        "n_strings": len(ideas),
        "raw_count": raw,
        "post_dedup_count": post,
        "reviewer_connected_components": reviewer,
        "collapse_ratio": round(ratio, 6),
        "naive_gate_ge_100": U.naive_unique(ideas) >= U.UNIQUE_IDEAS_FLOOR,
        "stopping_gate_ge_100": U.gate_unique_ideas_ge(ideas),
        "author_reviewer_agree": post == reviewer,
    }


def _run_row(run: dict[str, Any]) -> dict[str, Any]:
    texts = L.ledger_texts(run)
    stats = _corpus_row(run["run_id"], texts)
    stats["cast"] = list(run["cast"])
    stats["instruction"] = run["instruction"]
    stats["n_ledger_rows"] = len(run["ledger"])
    stats["authors_seen"] = sorted({row["author"] for row in run["ledger"]})
    return stats


def run() -> dict[str, Any]:
    mutants_out = []
    for m in F.planted_mutants():
        pair = _pair_row(m["seed"], m["mutant"])
        mutants_out.append(
            {
                **m,
                **pair,
                "passed": pair["observed"] == m["want"],
            }
        )

    blind = F.blind_class()
    blind_pair = _pair_row(blind["seed"], blind["mutant"])
    blind_out = {
        **blind,
        **blind_pair,
        "passed": blind_pair["observed"] == blind["want"],
    }
    distinct_ctrl = _pair_row(F.SEED, F.DISTINCT_CONTROL)

    distinct = F.distinct_ideas()
    gamed = F.gamed_pad()
    good = _corpus_row("known-good-distinct-100", distinct)
    bad = _corpus_row("known-broken-gamed-100", gamed)

    fires_on_gamed = bad["post_dedup_count"] < U.UNIQUE_IDEAS_FLOOR
    silent_on_distinct = (
        good["collapse_ratio"] < U.DISTINCT_COLLAPSE_TOLERANCE
        and good["post_dedup_count"] >= U.UNIQUE_IDEAS_FLOOR
    )

    brainstorms = [_run_row(r) for r in L.three_runs()]
    gaming_run = next(r for r in brainstorms if r["name"] == "brainstorm-gaming-pad")

    return {
        "similarity_method": U.SIMILARITY_METHOD,
        "jaccard_threshold": U.JACCARD_THRESHOLD,
        "unique_ideas_floor": U.UNIQUE_IDEAS_FLOOR,
        "distinct_collapse_tolerance": U.DISTINCT_COLLAPSE_TOLERANCE,
        "stopping_rule": (
            "unique_ideas >= 100 may be satisfied only by stopping_unique_count "
            "(post-dedup). naive_unique is evidence-only and must not gate."
        ),
        "planted_mutants": mutants_out,
        "blind_class": blind_out,
        "distinct_control_pair": {
            "seed": F.SEED,
            "other": F.DISTINCT_CONTROL,
            **distinct_ctrl,
            "want": "SILENT",
            "passed": distinct_ctrl["observed"] == "SILENT",
        },
        "both_states": {
            "planted_bad": {
                **bad,
                "observed": "FIRE" if fires_on_gamed else "SILENT",
                "want": "FIRE",
                "passed": fires_on_gamed,
                "verbatim": (
                    f"gamed n={bad['n_strings']} raw={bad['raw_count']} "
                    f"post_dedup={bad['post_dedup_count']} "
                    f"reviewer={bad['reviewer_connected_components']} "
                    f"collapse_ratio={bad['collapse_ratio']} "
                    f"naive_gate={bad['naive_gate_ge_100']} "
                    f"stopping_gate={bad['stopping_gate_ge_100']}"
                ),
            },
            "known_good": {
                **good,
                "observed": "SILENT" if silent_on_distinct else "FIRE",
                "want": "SILENT",
                "passed": silent_on_distinct,
                "verbatim": (
                    f"distinct n={good['n_strings']} raw={good['raw_count']} "
                    f"post_dedup={good['post_dedup_count']} "
                    f"reviewer={good['reviewer_connected_components']} "
                    f"collapse_ratio={good['collapse_ratio']} "
                    f"tolerance={U.DISTINCT_COLLAPSE_TOLERANCE} "
                    f"stopping_gate={good['stopping_gate_ge_100']}"
                ),
            },
            "discriminates": fires_on_gamed and silent_on_distinct,
        },
        "gaming_simulation": {
            "run_id": gaming_run["name"],
            "instruction": gaming_run["instruction"],
            "raw_count": gaming_run["raw_count"],
            "post_dedup_count": gaming_run["post_dedup_count"],
            "collapse_ratio": gaming_run["collapse_ratio"],
            "naive_would_satisfy_floor": gaming_run["naive_gate_ge_100"],
            "post_dedup_satisfies_floor": gaming_run["stopping_gate_ge_100"],
            "caught": (
                gaming_run["naive_gate_ge_100"] is True
                and gaming_run["stopping_gate_ge_100"] is False
            ),
            "verbatim": (
                f"gaming raw={gaming_run['raw_count']} "
                f"post_dedup={gaming_run['post_dedup_count']} "
                f"naive_gate={gaming_run['naive_gate_ge_100']} "
                f"stopping_gate={gaming_run['stopping_gate_ge_100']}"
            ),
        },
        "brainstorm_runs": brainstorms,
        "reviewer_agreement": all(
            r["author_reviewer_agree"] for r in [good, bad, *brainstorms]
        )
        and all(m["author_unique_count"] == m["reviewer_unique_count"] for m in mutants_out)
        and blind_out["author_unique_count"] == blind_out["reviewer_unique_count"],
    }
