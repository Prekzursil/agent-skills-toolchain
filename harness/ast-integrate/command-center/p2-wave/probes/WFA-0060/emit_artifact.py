#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0060-mechanism-leverage-ranking.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import ranker as R  # noqa: E402

OUT = "command-center/wfa/WFA-0060-mechanism-leverage-ranking.json"
SENTINEL = "SUCCESS:WFA-0060"


def build_document() -> dict:
    mechs, upstream = C.mechanisms()
    ranked = R.rank_mechanisms(mechs)
    echo = ranked["by_id"][R.ECHO_ID]
    fanin = ranked["by_id"][R.FANIN_ID]
    single = ranked["by_id"][R.SINGLE_ID]
    partial = ranked["by_id"][R.PARTIAL_ID]
    replay = ranked["by_id"][R.REPLAY_ID]
    records = []
    for row in ranked["records"]:
        rec = {
            "cross_domain_convergence": row["cross_domain_convergence"],
            "decision_impact": row["decision_impact"],
            "definition": row["definition"],
            "domains": row["domains"],
            "echo_vs_signal": row["echo_vs_signal"],
            "evidence_sources": row["evidence_sources"],
            "frequency": row["frequency"],
            "frequency_rank": row["frequency_rank"],
            "id": row["id"],
            "independence_asserted": True,
            "independent_evidence": row["independent_evidence"],
            "independent_sources": row["independent_sources"],
            "leverage_rank": row["leverage_rank"],
            "leverage_score": row["leverage_score"],
            "mechanism_id": row["mechanism_id"],
            "severity": row["severity"],
            "sharp_disagreement": row["sharp_disagreement"],
            "single_source": row["single_source"],
            "tags": row["tags"],
        }
        records.append(rec)
    planted = {
        "collapsed_independent_evidence": echo["independent_evidence"],
        "frequency": echo["frequency"],
        "frequency_rank": echo["frequency_rank"],
        "leverage_rank": echo["leverage_rank"],
        "leverage_score": echo["leverage_score"],
        "mechanism_id": R.ECHO_ID,
        "naive_frequency_as_evidence_rank": echo["naive_frequency_as_evidence_rank"],
        "naive_frequency_as_evidence_score": echo["naive_frequency_as_evidence_score"],
        "shared_upstream_id": echo["independent_sources"][0]["upstream_id"],
        "tags": echo["tags"],
        "works": (
            echo["frequency"] == 10
            and echo["independent_evidence"] == 1
            and echo["echo_vs_signal"] == "ECHO"
            and "SINGLE-SOURCE" in echo["tags"]
            and echo["naive_frequency_as_evidence_score"]
            > replay["leverage_score"]
            and echo["leverage_score"] < replay["leverage_score"]
        ),
    }
    return {
        "completion_sentinel": SENTINEL,
        "disagreements": ranked["disagreements"],
        "estate_extraction": upstream,
        "evidence": {
            "A": (
                "Each mechanism lists evidence_sources and independent_sources. "
                "Two artifacts sharing one upstream_id count once "
                "(counts_as_independent_evidence=1)."
            ),
            "B": (
                "frequency_ranking is published beside leverage_ranking. "
                "Where they disagree sharply the finding is listed; a high-"
                "frequency low-independence mechanism is tagged ECHO."
            ),
        },
        "frequency_ranking": ranked["frequency_ranking"],
        "leverage_ranking": ranked["leverage_ranking"],
        "output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/MechanismRecord"
        ),
        "planted_echo_cluster": planted,
        "question_or_target": (
            "Which mechanisms carry the most decision impact - ranked by "
            "independent evidence, cross-domain convergence, severity and "
            "decision impact - rather than by frequency?"
        ),
        "ranking_function": {
            "excludes": list(R.LEVERAGE_EXCLUDES),
            "formula": (
                "independent_evidence * cross_domain_convergence * "
                "severity * decision_impact"
            ),
            "inputs": list(R.LEVERAGE_INPUTS),
            "name": "independent-evidence-leverage",
        },
        "records": records,
        "sentinel": (
            "SUCCESS:WFA-0060 independent-evidence leverage ranking; "
            "frequency ranking published; planted echo collapsed to one "
            "independent source; SINGLE-SOURCE tagged"
        ),
        "state": "SUCCESS",
        "tests": [
            {
                "id": "two-rankings-published",
                "pass": bool(
                    ranked["leverage_ranking"] and ranked["frequency_ranking"]
                ),
            },
            {
                "id": "planted-echo-cluster-collapses",
                "pass": planted["works"],
            },
            {
                "id": "single-source-tagged",
                "pass": all(
                    ("SINGLE-SOURCE" in r["tags"]) == (r["independent_evidence"] == 1)
                    for r in records
                ),
            },
            {
                "id": "single-strong-outranks-weaker-echo",
                "pass": single["leverage_score"] > echo["leverage_score"],
            },
            {
                "id": "fanin-leverage-rank-1",
                "pass": fanin["leverage_rank"] == 1,
            },
            {
                "id": "partial-collapse-3-to-2",
                "pass": (
                    partial["frequency"] == 3
                    and partial["independent_evidence"] == 2
                ),
            },
        ],
        "unit_id": "WFA-0060",
    }


def main() -> int:
    doc = build_document()
    failed = [t["id"] for t in doc["tests"] if not t["pass"]]
    if failed:
        print(f"FAILED:WFA-0060 emit tests {failed}")
        return 1
    if SENTINEL not in json.dumps(doc):
        print("FAILED:WFA-0060 sentinel missing from document")
        return 1
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
