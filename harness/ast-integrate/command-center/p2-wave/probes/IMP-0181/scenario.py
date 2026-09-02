#!/usr/bin/env python3
"""Fixture corpus for IMP-0181: distinct mechanisms, one planted renamed copy,
and one similar-name distinct sibling (false-positive control).
"""
from __future__ import annotations

from fingerprint import mutate_one_gate, rename_workflow

PLANTED_ID = "wf.review-council.clone"
SIBLING_ID = "wf.review-council-v2"
INCUMBENT_ID = "wf.review-council"


def _wf(cid: str, name: str, stages: list[dict], **extra) -> dict:
    doc = {
        "id": cid,
        "name": name,
        "kind": "workflow_candidate",
        "stages": stages,
    }
    doc.update(extra)
    return doc


def _st(
    sid: str,
    kind: str,
    roles: list[str],
    gates: list[str],
    tools: list[str],
    nxt: list[str],
    name: str | None = None,
) -> dict:
    row = {
        "id": sid,
        "kind": kind,
        "roles": roles,
        "gates": gates,
        "tools": tools,
        "next": nxt,
    }
    if name:
        row["name"] = name
    return row


def distinct_mechanisms() -> list[dict]:
    return [
        _wf(
            INCUMBENT_ID,
            "review-council",
            [
                _st(
                    "intake",
                    "ingest",
                    ["clerk"],
                    ["payload.schema_ok"],
                    ["json-schema"],
                    ["deliberate"],
                ),
                _st(
                    "deliberate",
                    "council",
                    ["critic", "advocate"],
                    ["unresolved_p0 == 0"],
                    ["grep", "read"],
                    ["decide"],
                ),
                _st(
                    "decide",
                    "gate",
                    ["judge"],
                    ["votes.majority == true"],
                    ["ballot"],
                    [],
                ),
            ],
            description="Multi-role review council with a majority gate.",
        ),
        _wf(
            "wf.linear-scan-record",
            "linear-scan-record",
            [
                _st("scan", "static-scan", ["scanner"], ["files_scanned > 0"], ["grep"], ["record"]),
                _st("record", "write-config", ["scribe"], ["record.written == true"], ["fs-write"], []),
            ],
        ),
        _wf(
            "wf.oxford-debate",
            "oxford-debate",
            [
                _st("claim", "propose", ["proponent"], ["claim.present"], ["write"], ["rebut"]),
                _st("rebut", "rebuttal", ["opponent"], ["rebuttal.present"], ["write"], ["steelman"]),
                _st("steelman", "steelman", ["proponent"], ["steelman.precedes_rebuttal"], ["write"], ["verdict"]),
                _st("verdict", "judge", ["moderator"], ["rounds >= 2"], ["ballot"], []),
            ],
        ),
        _wf(
            "wf.jury",
            "jury-deliberation",
            [
                _st("hear", "ingest", ["juror"], ["evidence.admitted"], ["read"], ["deliberate"]),
                _st("deliberate", "deliberate", ["juror"], ["all_jurors_spoke == true"], ["note"], ["vote"]),
                _st("vote", "vote", ["juror"], ["unanimous == true"], ["ballot"], []),
            ],
        ),
        _wf(
            "wf.map-reduce-harvest",
            "map-reduce-harvest",
            [
                _st("split", "map", ["worker"], ["shards > 0"], ["chunk"], ["reduce"]),
                _st("reduce", "reduce", ["aggregator"], ["shard_results == shards"], ["merge"], []),
            ],
        ),
        _wf(
            "wf.canary-deploy",
            "canary-deploy",
            [
                _st("build", "compile", ["builder"], ["artifact.exists"], ["compiler"], ["canary"]),
                _st("canary", "deploy", ["sre"], ["error_rate < 0.01"], ["k8s"], ["promote"]),
                _st("promote", "deploy", ["sre"], ["canary.stable == true"], ["k8s"], []),
            ],
        ),
        _wf(
            "wf.red-team",
            "adversarial-red-team",
            [
                _st("attack", "red-team", ["attacker"], ["attempt.logged"], ["exploit-sim"], ["defend"]),
                _st("defend", "blue-team", ["defender"], ["mitigation.applied"], ["patch"], ["report"]),
                _st("report", "write-config", ["scribe"], ["findings >= 1"], ["fs-write"], []),
            ],
        ),
        _wf(
            "wf.license-fetch",
            "provenance-license-fetch",
            [
                _st("resolve", "fetch", ["archivist"], ["uri.resolved"], ["http"], ["classify"]),
                _st("classify", "classify", ["archivist"], ["spdx.id != unknown"], ["spdx"], []),
            ],
        ),
        _wf(
            "wf.schema-migrate",
            "schema-migrate",
            [
                _st("plan", "diff", ["migrator"], ["plan.nonempty"], ["sql"], ["apply"]),
                _st("apply", "mutate", ["migrator"], ["migration.applied"], ["sql"], ["verify"]),
                _st("verify", "gate", ["migrator"], ["rowcount_delta == expected"], ["sql"], []),
            ],
        ),
        _wf(
            "wf.quarantine-import",
            "quarantine-import",
            [
                _st("intake", "ingest", ["importer"], ["bytes > 0"], ["fs-read"], ["scan"]),
                _st("scan", "security-scan", ["guard"], ["injection.hits == 0"], ["regex"], ["admit"]),
                _st("admit", "gate", ["guard"], ["quarantine.cleared"], ["policy"], []),
            ],
        ),
        _wf(
            "wf.token-jaccard-scan",
            "token-jaccard-near-dup-scan",
            [
                _st("tokenize", "lex", ["scanner"], ["tokens > 0"], ["tokenize"], ["compare"]),
                _st("compare", "compare", ["scanner"], ["pairs_scored == pairs"], ["jaccard"], []),
            ],
        ),
        _wf(
            "wf.stage-splice-fusion",
            "stage-splice-fusion",
            [
                _st("align", "align", ["fuser"], ["contracts.compatible"], ["schema"], ["splice"]),
                _st("splice", "splice", ["fuser"], ["spliced.contract_ok"], ["ir-edit"], ["emit"]),
                _st("emit", "write-config", ["fuser"], ["fusion.emitted"], ["fs-write"], []),
            ],
        ),
    ]


def planted_renamed_copy() -> dict:
    """Same mechanism as the review-council incumbent; every identifier renamed."""
    base = next(w for w in distinct_mechanisms() if w["id"] == INCUMBENT_ID)
    mapping = {
        INCUMBENT_ID: PLANTED_ID,
        "review-council": "review-synod",
        "intake": "ingest",
        "deliberate": "confer",
        "decide": "rule",
    }
    renamed = rename_workflow(base, mapping)
    renamed["id"] = PLANTED_ID
    renamed["name"] = "review-synod"
    renamed["description"] = (
        "Renamed copy of the review council (trivial fork / identifier rewrite)."
    )
    renamed["planted"] = True
    renamed["plant_kind"] = "renamed-copy"
    return renamed


def similar_name_distinct_sibling() -> dict:
    """Looks like review-council-v2 by name; different kinds, gates, topology."""
    return _wf(
        SIBLING_ID,
        "review-council-v2",
        [
            _st("intake", "ingest", ["clerk"], ["payload.schema_ok"], ["json-schema"], ["triage"]),
            _st("triage", "classify", ["triage-officer"], ["severity in {p0,p1,p2}"], ["rules"], ["patch"]),
            _st("patch", "mutate", ["implementer"], ["diff.nonempty"], ["apply-patch"], ["verify"]),
            _st("verify", "test", ["tester"], ["tests.failing == 0"], ["pytest"], []),
        ],
        description="Similarly named sibling: a repair pipeline, not a review council.",
        planted=True,
        plant_kind="distinct-similar-name-sibling",
    )


def corpus(*, include_plant: bool = True, include_sibling: bool = True) -> list[dict]:
    rows = distinct_mechanisms()
    if include_plant:
        rows.append(planted_renamed_copy())
    if include_sibling:
        rows.append(similar_name_distinct_sibling())
    return rows


def rename_invariance_pairs(n: int = 12) -> list[tuple[dict, dict, dict[str, str]]]:
    base = next(w for w in distinct_mechanisms() if w["id"] == INCUMBENT_ID)
    pairs = []
    for i in range(n):
        mapping = {
            INCUMBENT_ID: f"wf.renamed.{i}",
            "review-council": f"alias-{i}",
            "intake": f"s{i}a",
            "deliberate": f"s{i}b",
            "decide": f"s{i}c",
        }
        pairs.append((base, rename_workflow(base, mapping), mapping))
    return pairs


def gate_mutation_pairs(n: int = 12) -> list[tuple[dict, dict]]:
    base = next(w for w in distinct_mechanisms() if w["id"] == INCUMBENT_ID)
    return [(base, mutate_one_gate(base, f"mutant_gate_{i} == 0")) for i in range(n)]
