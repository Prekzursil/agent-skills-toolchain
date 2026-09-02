"""Independent-evidence ranking (CC-0018 contract, consumed by CC-0019).

Rank uses source-set cardinality, cross-domain convergence, severity and
decision impact. Agent repetition of the same source does not raise rank.
"""
from __future__ import annotations

from typing import Any

IMPACT = {"NONE": 1, "SCHEDULE": 2, "CONTRACT": 3, "BLOCKER": 4}
VERIFY = {"REFUTED": 0, "UNVERIFIED": 1, "PROBED": 2, "CONFIRMED": 3}


def independent_source_paths(lineage: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for row in lineage or []:
        path = str(row.get("path") or "").replace("\\", "/")
        if path and path not in seen:
            seen.append(path)
    return seen


def rank_components(record: dict[str, Any]) -> dict[str, Any]:
    lineage = list(record.get("source_lineage") or [])
    paths = independent_source_paths(lineage)
    agents = [str(r.get("agent") or "") for r in lineage if r.get("agent")]
    impact = str(record.get("implementation_impact") or "NONE")
    verify = str(record.get("verification_status") or "UNVERIFIED")
    indep = len(paths)
    score = indep * 10 + IMPACT.get(impact, 1) * 3 + VERIFY.get(verify, 1)
    return {
        "score": score,
        "independent_source_count": indep,
        "agent_repetition_count": max(len(agents), len(lineage)),
        "formula": "independent_source_count*10 + impact*3 + verification",
        "independent_paths": paths,
    }


def attach_rank(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record["rank"] = rank_components(record)
    return record


def prove_anti_repetition() -> dict[str, Any]:
    """Adversarial controls required by CC-0018; executed, not argued."""
    base_lineage = [
        {
            "path": "command-center/p2-wave/probes/CC-0019/fixtures/planted-finding.md",
            "line": 3,
            "quote": "CC-0019-PLANTED-SYNTHETIC-FINDING-7f3a",
            "agent": "agent-a",
        }
    ]
    weak = {
        "canonical_mechanism": "weak echo",
        "implementation_impact": "NONE",
        "verification_status": "UNVERIFIED",
        "source_lineage": list(base_lineage),
    }
    echoes = {
        **weak,
        "source_lineage": base_lineage
        + [
            {**base_lineage[0], "agent": f"agent-{i}"}
            for i in range(2, 12)
        ],
    }
    strong = {
        "canonical_mechanism": "strong independent probe",
        "implementation_impact": "BLOCKER",
        "verification_status": "PROBED",
        "source_lineage": [
            {
                "path": "command-center/p2-wave/probes/CC-0019/fixtures/planted-finding.md",
                "line": 3,
                "quote": "CC-0019-PLANTED-SYNTHETIC-FINDING-7f3a",
                "agent": "probe",
            },
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": 1,
                "quote": "work_unit_fields_source",
                "agent": "catalog",
            },
        ],
    }
    same_doc_pair = {
        **weak,
        "source_lineage": [
            {**base_lineage[0], "agent": "one"},
            {**base_lineage[0], "agent": "two", "line": 5},
        ],
    }
    s_weak = rank_components(weak)["score"]
    s_echo = rank_components(echoes)["score"]
    s_strong = rank_components(strong)["score"]
    s_collapse = rank_components(same_doc_pair)["score"]
    extra = {
        **strong,
        "source_lineage": strong["source_lineage"]
        + [
            {
                "path": "command-center/schema/claim-record.schema.json",
                "line": 1,
                "quote": "PROVISIONAL",
                "agent": "schema",
            }
        ],
    }
    s_mono = rank_components(extra)["score"]
    return {
        "repetition_does_not_raise_rank": s_echo == s_weak,
        "weak_score": s_weak,
        "ten_echo_score": s_echo,
        "strong_independent_outranks_echoes": s_strong > s_echo,
        "strong_score": s_strong,
        "same_document_collapses_to_one_signal": rank_components(same_doc_pair)[
            "independent_source_count"
        ]
        == 1
        and s_collapse == s_weak,
        "monotonicity_independent_probe_raises_rank": s_mono > s_strong,
        "monotonic_score": s_mono,
    }
