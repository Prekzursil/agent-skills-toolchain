"""Matched revealed vs concealed vs ceremony-mask councils for TST-0289."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from council.simulate import (  # noqa: E402
    PersonaMissing,
    mean_pairwise_distance,
    run_council,
    subsequent_pull_mean,
)
import deanonymise as D  # noqa: E402
import stats as S  # noqa: E402

N_PAIRS = 24
SEEDS = list(range(28900, 28900 + N_PAIRS))
FIX = HERE / "fixtures"
REAL_NAMES = (
    "Dr. Helena Voss",
    "Jordan Hale",
    "Sam Okonkwo",
    "Riley Chen",
)


def load_bundle() -> dict[str, Any]:
    return json.loads((FIX / "personas.json").read_text(encoding="utf-8"))


def load_spec(name: str) -> dict[str, Any]:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def load_specs() -> dict[str, dict]:
    return {
        "revealed": load_spec("council.revealed.json"),
        "concealed": load_spec("council.concealed.json"),
        "ceremony": load_spec("council.ceremony-mask-only.json"),
    }


def pairwise_from_vectors(vectors: list[list[float]]) -> float:
    return mean_pairwise_distance(vectors)


def _arm_metrics(tr: dict[str, Any]) -> dict[str, Any]:
    vecs = [list(row["vector"]) for row in tr["openings_by_speak_order"]]
    texts = [str(row["text"]) for row in tr["openings"]]
    seat_ids = [str(row["seat_id"]) for row in tr["openings"]]
    return {
        "hash": tr["hash"],
        "verdict": tr["verdict"],
        "pairwise_mean": mean_pairwise_distance(vecs),
        "pull_mean": subsequent_pull_mean(tr),
        "vectors": vecs,
        "texts": texts,
        "seat_ids": seat_ids,
        "published_names": [row["published_name"] for row in tr["openings"]],
        "real_names_in_text": any(
            n in row["text"] for row in tr["openings"] for n in REAL_NAMES
        ),
        "tool_trace_in_text": any(
            "tool://seat/" in row["text"] for row in tr["openings"]
        ),
        "first_speaker_id": tr["first_speaker_id"],
        "first_speaker_high_status": tr["first_speaker_high_status"],
        "blind_first_pass": tr["blind_first_pass"],
        "identity_published": tr["identity_published"],
        "mode": tr["mode"],
    }


def run_pair(seed: int, personas: list[dict], specs: dict[str, dict]) -> dict[str, Any]:
    revealed = run_council(specs["revealed"], personas, seed)
    concealed = run_council(specs["concealed"], personas, seed)
    ceremony = run_council(specs["ceremony"], personas, seed)
    r = _arm_metrics(revealed)
    c = _arm_metrics(concealed)
    m = _arm_metrics(ceremony)
    return {
        "seed": seed,
        "independence_delta": c["pairwise_mean"] - r["pairwise_mean"],
        "ceremony_independence_delta": m["pairwise_mean"] - r["pairwise_mean"],
        "pull_delta": r["pull_mean"] - c["pull_mean"],
        "ceremony_pull_delta": m["pull_mean"] - r["pull_mean"],
        "verdict_disagree": r["verdict"] != c["verdict"],
        "ceremony_verdict_disagree": r["verdict"] != m["verdict"],
        "revealed": r,
        "concealed": c,
        "ceremony": m,
    }


def run_experiment(*, n: int = N_PAIRS, seeds: list[int] | None = None) -> dict[str, Any]:
    bundle = load_bundle()
    personas = bundle["seats"]
    labels = bundle["labels"]
    specs = load_specs()
    for spec in specs.values():
        spec.setdefault("labels", labels)
    use_seeds = list(seeds if seeds is not None else SEEDS[:n])
    rows = [run_pair(seed, personas, specs) for seed in use_seeds]

    ind = [row["independence_delta"] for row in rows]
    pull = [row["pull_delta"] for row in rows]
    cer_ind = [row["ceremony_independence_delta"] for row in rows]
    cer_pull = [row["ceremony_pull_delta"] for row in rows]
    disagree = [1.0 if row["verdict_disagree"] else 0.0 for row in rows]
    cer_dis = [1.0 if row["ceremony_verdict_disagree"] else 0.0 for row in rows]

    ind_ci = S.bootstrap_mean_ci(ind)
    pull_ci = S.bootstrap_mean_ci(pull)
    cer_ind_ci = S.bootstrap_mean_ci(cer_ind)
    disagree_ci = S.bootstrap_mean_ci(disagree)

    concealed_items: list[tuple[str, str]] = []
    revealed_items: list[tuple[str, str]] = []
    ceremony_items: list[tuple[str, str]] = []
    for row in rows:
        concealed_items.extend(zip(row["concealed"]["texts"], row["concealed"]["seat_ids"]))
        revealed_items.extend(zip(row["revealed"]["texts"], row["revealed"]["seat_ids"]))
        ceremony_items.extend(zip(row["ceremony"]["texts"], row["ceremony"]["seat_ids"]))

    deanon_concealed = D.accuracy(concealed_items, personas)
    deanon_revealed = D.accuracy(revealed_items, personas)
    deanon_ceremony = D.accuracy(ceremony_items, personas)
    deanon_planted = D.accuracy(D.plant_traces(concealed_items), personas)

    independence_alters = S.ci_excludes_zero(ind_ci)
    pull_alters = S.ci_excludes_zero(pull_ci)
    ceremony_is_null = not S.ci_excludes_zero(cer_ind_ci)
    if independence_alters and pull_alters:
        finding = "alters_distribution"
        finding_plain = (
            "Anonymity plus a blind independent first pass alter round-1 "
            "position independence and first-speaker anchoring relative to "
            "identity-revealed sequential speaking with a high-status first "
            "speaker; final verdicts also diverge on a substantial share of "
            "matched seeds."
        )
    elif not independence_alters and not pull_alters:
        finding = "null_ceremony"
        finding_plain = (
            "Null result: under this scripted cast, identity concealment and "
            "the blind first pass did not measurably change round-1 "
            "independence or anchoring. Reported as ceremony for this "
            "configuration."
        )
    else:
        finding = "partial"
        finding_plain = (
            "Partial: one of independence or anchoring moved with a CI that "
            "excludes zero; the other is compatible with a null. Not treated "
            "as a clean protocol win."
        )

    same_seed_hash_ok = True
    for seed in use_seeds[:3]:
        a = run_council(specs["revealed"], personas, seed)
        b = run_council(specs["revealed"], personas, seed)
        if a["hash"] != b["hash"]:
            same_seed_hash_ok = False
    d0 = run_council(specs["revealed"], personas, use_seeds[0])
    d1 = run_council(specs["revealed"], personas, use_seeds[1])
    different_seed_hash_ok = d0["hash"] != d1["hash"]

    return {
        "unit_id": "TST-0289",
        "n_pairs": len(rows),
        "seeds": use_seeds,
        "finding": finding,
        "finding_plain": finding_plain,
        "independence_delta": ind_ci,
        "independence_cohens_dz": S.cohens_dz(ind),
        "pull_delta": pull_ci,
        "pull_cohens_dz": S.cohens_dz(pull),
        "verdict_disagree_rate": disagree_ci,
        "ceremony_independence_delta": cer_ind_ci,
        "ceremony_pull_delta": S.bootstrap_mean_ci(cer_pull),
        "ceremony_verdict_disagree_rate": S.bootstrap_mean_ci(cer_dis),
        "ceremony_independence_compatible_with_null": ceremony_is_null,
        "independence_ci_excludes_zero": independence_alters,
        "pull_ci_excludes_zero": pull_alters,
        "deanonymisation": {
            "concealed": deanon_concealed,
            "revealed": deanon_revealed,
            "ceremony_mask_only": deanon_ceremony,
            "planted_traces": deanon_planted,
        },
        "controls": {
            "same_seed_hash_ok": same_seed_hash_ok,
            "different_seed_hash_ok": different_seed_hash_ok,
            "names_leaked_concealed": any(
                row["concealed"]["real_names_in_text"] for row in rows
            ),
            "tool_traces_leaked_concealed": any(
                row["concealed"]["tool_trace_in_text"] for row in rows
            ),
            "high_status_first_all_revealed": all(
                row["revealed"]["first_speaker_high_status"]
                and row["revealed"]["first_speaker_id"] == "P"
                for row in rows
            ),
        },
        "rows": rows,
        "personas": personas,
        "specs": {k: specs[k]["id"] for k in specs},
    }


def loud_missing_persona() -> str:
    bundle = load_bundle()
    personas = [p for p in bundle["seats"] if p["id"] != "J"]
    spec = load_spec("council.revealed.json")
    spec["labels"] = bundle["labels"]
    try:
        run_council(spec, personas, 28900)
    except PersonaMissing as exc:
        return str(exc)
    return ""
