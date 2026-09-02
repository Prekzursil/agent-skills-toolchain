#!/usr/bin/env python3
"""Run finder, honest refuter, noisy refuter; third-agent survival; scores."""
from __future__ import annotations

import corpus as C
import find as F
import judge as J
import refute as R
import score as S
from util import billed_hours, sha256_file


def _judge_all(rel: str, candidates: list[dict], author: str) -> list[dict]:
    from util import REPO

    raw = (REPO / rel).read_bytes()
    judged = []
    for item in candidates:
        payload = dict(item)
        payload["author"] = author
        verdict = J.survive(raw, payload)
        rec = dict(payload)
        rec["survive"] = bool(verdict["survive"])
        rec["judge_reason"] = verdict["reason"]
        judged.append(rec)
    return judged


def _author_swap_ok(rel: str, candidates: list[dict]) -> bool:
    from util import REPO

    raw = (REPO / rel).read_bytes()
    for item in candidates:
        a = J.survive(raw, {**item, "author": "honest-refuter"})
        b = J.survive(raw, {**item, "author": "volume-finder"})
        c = J.survive(raw, {**item, "author": "left-blank"})
        if a != b or b != c:
            return False
    return True


def run_experiment() -> dict:
    rows = C.rows()
    known = C.known_correct_ids()
    hours = billed_hours(len(rows))
    agents = {
        "honest_refuter": R.honest_findings,
        "noisy_refuter": R.noisy_findings,
        "volume_finder": F.finder_findings,
    }
    by_agent: dict[str, dict] = {}
    swap_ok = True
    per_artifact: dict[str, dict] = {}

    for row in rows:
        digest, size = sha256_file(row["path"])
        per_artifact[row["id"]] = {
            "rel": row["rel"],
            "gold": row["gold"],
            "why_gold": row["why_gold"],
            "sha256": digest,
            "bytes": size,
        }

    for name, fn in agents.items():
        emitted: list[dict] = []
        survivors: list[dict] = []
        on_correct_surv = 0
        on_correct_emitted = 0
        by_art: dict[str, dict] = {}
        for row in rows:
            cands = fn(row["rel"])
            judged = _judge_all(row["rel"], cands, name)
            if not _author_swap_ok(row["rel"], cands):
                swap_ok = False
            surv = [x for x in judged if x["survive"]]
            emitted.extend(judged)
            survivors.extend(surv)
            if row["id"] in known:
                on_correct_emitted += len(judged)
                on_correct_surv += len(surv)
            by_art[row["id"]] = {
                "emitted": len(judged),
                "survivors": len(surv),
                "kinds": sorted({x["kind"] for x in judged}),
            }
        honest = S.score_honest(
            emitted=len(emitted),
            survivors=len(survivors),
            surviving_on_known_correct=on_correct_surv,
            billed_hours=hours,
        )
        volume = S.score_volume(emitted=len(emitted), billed_hours=hours)
        by_agent[name] = {
            "honest_score": honest,
            "volume_score": volume,
            "emitted_on_known_correct": on_correct_emitted,
            "per_artifact": by_art,
            "survivor_kinds": sorted({x["kind"] for x in survivors}),
        }

    honest = by_agent["honest_refuter"]["honest_score"]
    noisy = by_agent["noisy_refuter"]["honest_score"]
    finder = by_agent["volume_finder"]["honest_score"]
    vol_rank = sorted(
        agents,
        key=lambda n: by_agent[n]["volume_score"]["emitted"],
        reverse=True,
    )
    honest_rank = sorted(
        agents,
        key=lambda n: tuple(by_agent[n]["honest_score"]["rank_key"]),
        reverse=True,
    )
    return {
        "n_artifacts": len(rows),
        "billed_seconds_per_artifact": 60,
        "billed_hours": hours,
        "billed_hours_note": (
            "Declared meter: 60 billed seconds per artifact. Not LLM wall-clock."
        ),
        "author_swap_invariant": swap_ok,
        "artifacts": per_artifact,
        "agents": by_agent,
        "ranking_honest": honest_rank,
        "ranking_volume": vol_rank,
        "volume_ranking_differs": vol_rank != honest_rank,
        "negative_control": {
            "known_correct_ids": sorted(known),
            "honest_surviving": honest["surviving_on_known_correct"],
            "noisy_surviving": noisy["surviving_on_known_correct"],
            "noisy_emitted_on_known_correct": by_agent["noisy_refuter"][
                "emitted_on_known_correct"
            ],
            "honest_emitted_on_known_correct": by_agent["honest_refuter"][
                "emitted_on_known_correct"
            ],
            "pass": (
                honest["surviving_on_known_correct"] == 0
                and noisy["surviving_on_known_correct"] == 0
            ),
        },
        "comparison": {
            "honest_precision": honest["precision"],
            "noisy_precision": noisy["precision"],
            "finder_precision": finder["precision"],
            "honest_yield_per_hour": honest["yield_per_hour"],
            "noisy_yield_per_hour": noisy["yield_per_hour"],
            "finder_yield_surviving_per_hour": finder["yield_per_hour"],
            "finder_volume_per_hour": by_agent["volume_finder"]["volume_score"][
                "yield_per_hour"
            ],
            "honest_beats_noisy_on_precision": honest["precision"] > noisy["precision"],
            "honest_beats_finder_on_precision": honest["precision"]
            > finder["precision"],
        },
    }
